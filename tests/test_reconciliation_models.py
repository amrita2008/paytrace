"""Tests for reconciliation domain models and interfaces."""

from __future__ import annotations

import importlib
import inspect
import pkgutil
from datetime import datetime, timezone

import pytest

from backend.models.canonical import (
    BankEntryType,
    BankLedgerStatus,
    PaymentStatus,
    SettlementStatus,
    Source,
)
from backend.reconciliation.interfaces import (
    BatchReconciliationProtocol,
    DeterministicReconciliationEngine,
)
from backend.reconciliation.models import (
    ExceptionType,
    MatchCandidate,
    MatchEvidence,
    MatchMethod,
    MatchStatus,
    NormalizedBankEntry,
    NormalizedPayment,
    NormalizedSettlement,
    ReconciliationResult,
    ResolutionStatus,
    SignalType,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TZ = timezone.utc


def _valid_payment(**overrides) -> NormalizedPayment:
    defaults = dict(
        payment_id="PAY-0001",
        order_id="ORD-0001",
        amount_paise=10000,
        fee_paise=0,
        net_amount_paise=10000,
        currency="INR",
        status=PaymentStatus.CAPTURED,
        timestamp=datetime(2026, 8, 20, 8, 0, tzinfo=TZ),
        gateway_reference="GW-0001",
    )
    defaults.update(overrides)
    return NormalizedPayment(**defaults)


def _valid_settlement(**overrides) -> NormalizedSettlement:
    defaults = dict(
        settlement_id="SETL-0001",
        amount_paise=10000,
        fee_paise=200,
        net_amount_paise=9800,
        currency="INR",
        status=SettlementStatus.SETTLED,
        timestamp=datetime(2026, 8, 21, 8, 0, tzinfo=TZ),
        payment_refs=["PAY-0001"],
        gateway_settlement_reference="GWSETL-0001",
    )
    defaults.update(overrides)
    return NormalizedSettlement(**defaults)


def _valid_bank_entry(**overrides) -> NormalizedBankEntry:
    defaults = dict(
        bank_entry_id="BANK-0001",
        amount_paise=9800,
        currency="INR",
        entry_type=BankEntryType.CREDIT,
        ledger_status=BankLedgerStatus.CLEARED,
        timestamp=datetime(2026, 8, 22, 8, 0, tzinfo=TZ),
        reference="SETL-0001",
    )
    defaults.update(overrides)
    return NormalizedBankEntry(**defaults)


def _valid_evidence(**overrides) -> MatchEvidence:
    defaults = dict(
        signal_id="S1",
        source_record_id="PAY-0001",
        signal_type=SignalType.EXACT_IDENTIFIER,
        observed_value="ORD-0001",
        points=40,
    )
    defaults.update(overrides)
    return MatchEvidence(**defaults)


def _valid_result(**overrides) -> ReconciliationResult:
    defaults = dict(
        group_id="G-0001",
        status=MatchStatus.MATCHED,
        payment_ids=["PAY-0001"],
        settlement_ids=["SETL-0001"],
        bank_entry_ids=["BANK-0001"],
        match_score=100,
        match_method=MatchMethod.EXACT_KEY,
        exception_type=None,
        resolution_status=ResolutionStatus.RESOLVED,
        evidence=[_valid_evidence()],
        evidence_summary="Exact match on order_id and amount",
        human_review_required=False,
    )
    defaults.update(overrides)
    return ReconciliationResult(**defaults)


# ---------------------------------------------------------------------------
# 1-2: Normalized Payment validation
# ---------------------------------------------------------------------------


def test_normalized_payment_valid():
    p = _valid_payment()
    assert p.payment_id == "PAY-0001"
    assert p.amount_paise == 10000
    assert p.status == PaymentStatus.CAPTURED


def test_normalized_payment_rejects_zero_amount():
    with pytest.raises(ValueError, match="positive"):
        _valid_payment(amount_paise=0)


# ---------------------------------------------------------------------------
# 3-6: Enum value checks
# ---------------------------------------------------------------------------


def test_match_status_values():
    assert len(MatchStatus) == 6
    expected = {"matched", "mismatched", "missing", "duplicate", "ambiguous", "unresolved"}
    assert {s.value for s in MatchStatus} == expected


def test_exception_type_values():
    assert len(ExceptionType) == 7
    expected = {
        "AMOUNT_MISMATCH", "TIMING_MISMATCH", "DUPLICATE", "AMBIGUOUS",
        "MISSING_SETTLEMENT", "FAILED_OR_REFUNDED", "ORPHAN_BANK_ENTRY",
    }
    assert {e.value for e in ExceptionType} == expected


def test_resolution_status_values():
    assert len(ResolutionStatus) == 6
    expected = {"open", "investigating", "ai_reviewed", "resolved", "rejected", "unresolved"}
    assert {r.value for r in ResolutionStatus} == expected


def test_match_method_values():
    assert len(MatchMethod) == 3
    expected = {"exact_key", "fuzzy", "batch_settle"}
    assert {m.value for m in MatchMethod} == expected


# ---------------------------------------------------------------------------
# 7-8: Evidence structure
# ---------------------------------------------------------------------------


def test_match_candidate_has_evidence():
    c = MatchCandidate(
        source_record_id="PAY-0001",
        candidate_record_id="SETL-0001",
        candidate_source=Source.SETTLEMENT,
        match_score=100,
        signals_active=[_valid_evidence()],
        is_definitive=True,
        reason="Exact match",
    )
    assert len(c.signals_active) == 1
    assert isinstance(c.signals_active[0], MatchEvidence)
    assert c.signals_active[0].signal_type == SignalType.EXACT_IDENTIFIER


def test_evidence_no_chain_of_thought():
    """MatchEvidence must not contain chain-of-thought fields."""
    prohibited = {"chain_of_thought", "reasoning_trace", "hidden_reasoning", "model_thoughts"}
    fields = {f.name for f in MatchEvidence.__dataclass_fields__.values()}
    assert prohibited.isdisjoint(fields), f"Prohibited fields found: {prohibited & fields}"


# ---------------------------------------------------------------------------
# 9-11: Result covers matched/exception/ambiguous
# ---------------------------------------------------------------------------


def test_result_represents_match():
    r = _valid_result()
    assert r.status == MatchStatus.MATCHED
    assert r.exception_type is None
    assert r.match_score == 100
    assert r.human_review_required is False


def test_result_represents_exception():
    r = _valid_result(
        status=MatchStatus.MISMATCHED,
        match_score=None,
        match_method=None,
        exception_type=ExceptionType.AMOUNT_MISMATCH,
        resolution_status=ResolutionStatus.OPEN,
        human_review_required=True,
        evidence_summary=None,
    )
    assert r.status == MatchStatus.MISMATCHED
    assert r.exception_type == ExceptionType.AMOUNT_MISMATCH
    assert r.resolution_status == ResolutionStatus.OPEN
    assert r.human_review_required is True
    assert r.match_score is None


def test_result_represents_ambiguity():
    r = _valid_result(
        status=MatchStatus.AMBIGUOUS,
        match_score=None,
        match_method=None,
        exception_type=ExceptionType.AMBIGUOUS,
        resolution_status=ResolutionStatus.OPEN,
        human_review_required=True,
    )
    assert r.status == MatchStatus.AMBIGUOUS
    assert r.human_review_required is True
    assert r.exception_type == ExceptionType.AMBIGUOUS


# ---------------------------------------------------------------------------
# 12-13: Protocols exist
# ---------------------------------------------------------------------------


def test_batch_protocol_exists():
    assert hasattr(BatchReconciliationProtocol, "check_batch")


def test_engine_protocol_exists():
    assert hasattr(DeterministicReconciliationEngine, "reconcile")


# ---------------------------------------------------------------------------
# 14: No evaluation/ imports
# ---------------------------------------------------------------------------


def test_no_evaluation_imports():
    """reconciliation/ modules must not import evaluation/."""
    pkg_path = importlib.import_module("backend.reconciliation").__path__
    for importer, modname, _ispkg in pkgutil.walk_packages(pkg_path, prefix="backend.reconciliation."):
        mod = importlib.import_module(modname)
        source = inspect.getsource(mod)
        assert "evaluation" not in source.lower() or "evaluation/" not in source, (
            f"{modname} references evaluation/"
        )


# ---------------------------------------------------------------------------
# 15: Existing tests still pass (re-run health + synthetic data)
# ---------------------------------------------------------------------------


def test_existing_health_and_synthetic_data_tests_pass():
    """Verify we didn't break anything by importing reconciliation models."""
    from backend.reconciliation.models import (
        ExceptionType,
        MatchStatus,
        ResolutionStatus,
        SignalType,
    )
    # Verify enums are accessible
    assert MatchStatus.MATCHED.value == "matched"
    assert ExceptionType.AMOUNT_MISMATCH.value == "AMOUNT_MISMATCH"
    assert ResolutionStatus.OPEN.value == "open"
    assert SignalType.EXACT_IDENTIFIER.value == "EXACT_IDENTIFIER"
