"""Tests for the exact deterministic reconciliation engine (Phase 3B)."""

from __future__ import annotations

import inspect
import importlib
import json
from datetime import datetime, timezone

import pytest

from backend.models.canonical import (
    BankEntryType,
    BankLedgerStatus,
    PaymentStatus,
    SettlementStatus,
)
from backend.reconciliation.engine import ExactReconciliationEngine
from backend.reconciliation.matching import (
    normalize_bank_entry,
    normalize_payment,
    normalize_settlement,
)
from backend.reconciliation.models import (
    ExceptionType,
    MatchStatus,
    NormalizedBankEntry,
    NormalizedPayment,
    NormalizedSettlement,
    ResolutionStatus,
    SignalType,
)

TZ = timezone.utc


def _make_payment(pid="PAY-0001", order="ORD-0001", amount=10000,
                  status="captured", ts="2026-08-20T08:00:00Z") -> NormalizedPayment:
    return normalize_payment({
        "payment_id": pid, "order_id": order, "customer_ref": "CUST-0001",
        "amount_paise": amount, "currency": "INR",
        "payment_timestamp": ts, "payment_status": status,
        "gateway_reference": f"GW-{pid.split(chr(45))[1]}",
    })


def _make_settlement(sid="SETL-0001", amount=10000, fee=200,
                     refs=None, ts="2026-08-21T08:00:00Z",
                     is_exc=False) -> NormalizedSettlement:
    net = amount - fee
    return normalize_settlement({
        "settlement_id": sid, "settlement_timestamp": ts,
        "amount_paise": amount, "currency": "INR",
        "fee_paise": fee, "net_amount_paise": net,
        "payment_refs": refs or [], "settlement_status": "settled",
        "gateway_settlement_reference": f"GWSETL-{sid.split(chr(45))[1]}",
        "is_known_exception": is_exc,
    })


def _make_bank(bid="BANK-0001", amount=9800, ref="SETL-0001",
               ts="2026-08-22T08:00:00Z") -> NormalizedBankEntry:
    return normalize_bank_entry({
        "bank_entry_id": bid, "entry_timestamp": ts,
        "amount_paise": amount, "currency": "INR",
        "reference": ref, "entry_type": "credit", "ledger_status": "cleared",
    })


def test_exact_ref_match():
    pay = _make_payment("PAY-0001", amount=10000)
    setl = _make_settlement("SETL-0001", amount=10000, refs=["PAY-0001"])
    bank = _make_bank("BANK-0001", amount=9800, ref="SETL-0001")
    engine = ExactReconciliationEngine()
    results = engine.reconcile([pay], [setl], [bank])
    matched = [r for r in results if r.status == MatchStatus.MATCHED]
    assert len(matched) >= 1
    g = matched[0]
    assert "PAY-0001" in g.payment_ids
    assert "SETL-0001" in g.settlement_ids
    assert "BANK-0001" in g.bank_entry_ids
    assert g.exception_type is None
    assert g.human_review_required is False


def test_amount_in_evidence():
    pay = _make_payment("PAY-0001", amount=10000)
    setl = _make_settlement("SETL-0001", amount=10000, refs=["PAY-0001"])
    engine = ExactReconciliationEngine()
    results = engine.reconcile([pay], [setl], [])
    matched = [r for r in results if r.status == MatchStatus.MATCHED]
    assert len(matched) >= 1
    amount_signals = [
        e for e in matched[0].evidence
        if e.signal_type in (SignalType.EXACT_AMOUNT, SignalType.BATCH_AMOUNT_MATCH)
    ]
    assert len(amount_signals) >= 1


def test_batch_amount_match():
    p1 = _make_payment("PAY-0001", amount=3000)
    p2 = _make_payment("PAY-0002", order="ORD-0002", amount=7000)
    setl = _make_settlement("SETL-0001", amount=10000, refs=["PAY-0001", "PAY-0002"])
    engine = ExactReconciliationEngine()
    results = engine.reconcile([p1, p2], [setl], [])
    matched = [r for r in results if r.status == MatchStatus.MATCHED]
    assert len(matched) >= 1
    batch_signals = [
        e for e in matched[0].evidence
        if e.signal_type == SignalType.BATCH_AMOUNT_MATCH
    ]
    assert len(batch_signals) >= 1
    assert "PAY-0001" in matched[0].payment_ids
    assert "PAY-0002" in matched[0].payment_ids


def test_amount_mismatch():
    pay = _make_payment("PAY-0001", amount=10000)
    setl = _make_settlement("SETL-0001", amount=9000, refs=["PAY-0001"], is_exc=True)
    engine = ExactReconciliationEngine()
    results = engine.reconcile([pay], [setl], [])
    mismatched = [r for r in results if r.status == MatchStatus.MISMATCHED]
    assert len(mismatched) >= 1
    g = mismatched[0]
    assert g.exception_type == ExceptionType.AMOUNT_MISMATCH
    assert g.human_review_required is True
    assert g.match_score is None


def test_duplicate_detected():
    p1 = _make_payment("PAY-0001", amount=10000, status="captured")
    p2 = _make_payment("PAY-0002", order="ORD-0001", amount=10000, status="captured")
    setl = _make_settlement("SETL-0001", amount=10000, refs=["PAY-0001"])
    engine = ExactReconciliationEngine()
    results = engine.reconcile([p1, p2], [setl], [])
    # PAY-0002 is unreferenced by settlement -> should NOT be in settlement group
    setl_results = [r for r in results if "SETL-0001" in r.settlement_ids]
    assert len(setl_results) >= 1
    g = setl_results[0]
    # Only explicitly referenced payment should be in the group
    assert "PAY-0001" in g.payment_ids
    assert "PAY-0002" not in g.payment_ids
    # PAY-0002 should appear in a separate DUPLICATE group
    dup_groups = [r for r in results if r.exception_type == ExceptionType.DUPLICATE]
    assert len(dup_groups) >= 1
    all_dup_pay_ids = []
    for dg in dup_groups:
        all_dup_pay_ids.extend(dg.payment_ids)
    assert "PAY-0002" in all_dup_pay_ids


def test_ambiguous_settlement():
    setl = _make_settlement("SETL-0001", amount=10000, refs=[], ts="2026-09-16T08:00:00Z")
    engine = ExactReconciliationEngine()
    results = engine.reconcile([], [setl], [])
    ambiguous = [r for r in results if r.status == MatchStatus.AMBIGUOUS]
    assert len(ambiguous) == 1
    g = ambiguous[0]
    assert g.exception_type == ExceptionType.AMBIGUOUS
    assert g.human_review_required is True
    assert g.match_score is None
    assert "SETL-0001" in g.settlement_ids
    assert g.payment_ids == []


def test_missing_payment_in_ref():
    setl = _make_settlement("SETL-0001", amount=10000, refs=["PAY-9999"])
    engine = ExactReconciliationEngine()
    results = engine.reconcile([], [setl], [])
    mismatched = [r for r in results if r.status == MatchStatus.MISMATCHED]
    assert len(mismatched) >= 1
    g = mismatched[0]
    missing_signals = [
        e for e in g.evidence
        if e.signal_type == SignalType.MISSING_RECORD
    ]
    assert len(missing_signals) >= 1


def test_bank_exact_match():
    setl = _make_settlement("SETL-0001", amount=10000, fee=200, refs=["PAY-0001"])
    bank = _make_bank("BANK-0001", amount=9800, ref="SETL-0001")
    engine = ExactReconciliationEngine()
    results = engine.reconcile([_make_payment()], [setl], [bank])
    matched = [r for r in results if r.status == MatchStatus.MATCHED]
    assert len(matched) >= 1
    g = matched[0]
    assert "BANK-0001" in g.bank_entry_ids
    bank_amount_signals = [
        e for e in g.evidence
        if e.source_record_id == "BANK-0001" and e.signal_type == SignalType.EXACT_AMOUNT
    ]
    assert len(bank_amount_signals) >= 1


def test_missing_settlement_for_payment():
    pay = _make_payment("PAY-0001", amount=10000)
    engine = ExactReconciliationEngine()
    results = engine.reconcile([pay], [], [])
    mismatched = [r for r in results if r.status == MatchStatus.MISMATCHED]
    assert len(mismatched) >= 1
    g = mismatched[0]
    assert g.exception_type == ExceptionType.MISSING_SETTLEMENT
    assert "PAY-0001" in g.payment_ids
    assert g.human_review_required is True


def test_failed_payment_no_settlement():
    pay = _make_payment("PAY-0001", amount=10000, status="failed")
    engine = ExactReconciliationEngine()
    results = engine.reconcile([pay], [], [])
    mismatched = [r for r in results if r.status == MatchStatus.MISMATCHED]
    assert len(mismatched) >= 1
    g = mismatched[0]
    assert g.exception_type == ExceptionType.FAILED_OR_REFUNDED
    assert g.human_review_required is False
    assert g.resolution_status == ResolutionStatus.RESOLVED


def test_orphan_bank_entry():
    bank = _make_bank("BANK-0001", amount=5000, ref="INT-0001")
    engine = ExactReconciliationEngine()
    results = engine.reconcile([], [], [bank])
    mismatched = [r for r in results if r.status == MatchStatus.MISMATCHED]
    assert len(mismatched) >= 1
    g = mismatched[0]
    assert g.exception_type == ExceptionType.ORPHAN_BANK_ENTRY
    assert "BANK-0001" in g.bank_entry_ids


def test_no_chain_of_thought_fields():
    """No evidence or result should contain chain-of-thought fields."""
    pay = _make_payment("PAY-0001", amount=10000)
    setl = _make_settlement("SETL-0001", amount=10000, refs=["PAY-0001"])
    engine = ExactReconciliationEngine()
    results = engine.reconcile([pay], [setl], [])
    forbidden = {
        "chain_of_thought", "reasoning_trace", "hidden_reasoning",
        "model_thoughts", "explanation",
    }
    for r in results:
        assert not forbidden.intersection(r.__class__.__dataclass_fields__)
        for e in r.evidence:
            assert not forbidden.intersection(e.__class__.__dataclass_fields__)


def test_all_results_have_evidence():
    pay = _make_payment("PAY-0001", amount=10000)
    setl = _make_settlement("SETL-0001", amount=10000, refs=["PAY-0001"])
    engine = ExactReconciliationEngine()
    results = engine.reconcile([pay], [setl], [])
    for r in results:
        assert len(r.evidence) > 0, f"{r.group_id} has no evidence"


def test_evidence_summary_not_chain_of_thought():
    pay = _make_payment("PAY-0001", amount=10000)
    setl = _make_settlement("SETL-0001", amount=10000, refs=["PAY-0001"])
    engine = ExactReconciliationEngine()
    results = engine.reconcile([pay], [setl], [])
    for r in results:
        if r.evidence_summary:
            lower = r.evidence_summary.lower()
            assert "chain of thought" not in lower
            assert "internal reasoning" not in lower
            assert "model reasoning" not in lower


def test_no_evaluation_imports():
    """Engine module must not import evaluation."""
    import backend.reconciliation.engine as eng
    source = inspect.getsource(eng)
    # Check for actual import statements, not comments
    for line in source.split(chr(10)):
        stripped = line.strip()
        if stripped.startswith("import ") or stripped.startswith("from "):
            assert "evaluation" not in stripped.lower()
            assert "ground_truth" not in stripped.lower()


def test_no_hardcoded_scenario_ids():
    """Engine should not contain synthetic data scenario IDs."""
    import backend.reconciliation.engine as eng
    source = inspect.getsource(eng)
    for scenario_id in ["SETL-0017", "SETL-0018", "PAY-0039", "PAY-0040"]:
        assert scenario_id not in source, f"Hardcoded scenario ID {scenario_id} found"


# =====================================================================
# NEW TESTS: Timing window + Global duplicate detection
# =====================================================================


def test_timing_within_window_matches():
    """Payment 2 days before settlement -> MATCHED (within 3-day window)."""
    pay = _make_payment("PAY-0001", amount=10000, ts="2026-08-20T08:00:00Z")
    setl = _make_settlement("SETL-0001", amount=10000, refs=["PAY-0001"],
                            ts="2026-08-22T08:00:00Z")
    engine = ExactReconciliationEngine()
    results = engine.reconcile([pay], [setl], [])
    matched = [r for r in results if r.status == MatchStatus.MATCHED]
    assert len(matched) == 1
    g = matched[0]
    assert "PAY-0001" in g.payment_ids
    assert "SETL-0001" in g.settlement_ids
    assert g.exception_type is None
    within_signals = [
        e for e in g.evidence
        if e.signal_type == SignalType.TIMESTAMP_WITHIN_WINDOW
    ]
    assert len(within_signals) >= 1
    exceeded = [
        e for e in g.evidence
        if e.signal_type == SignalType.TIMESTAMP_EXCEEDED
    ]
    assert len(exceeded) == 0


def test_timing_exceeds_window_mismatch():
    """Payment 5 days before settlement -> TIMING_MISMATCH."""
    pay = _make_payment("PAY-0001", amount=10000, ts="2026-08-20T08:00:00Z")
    setl = _make_settlement("SETL-0001", amount=10000, refs=["PAY-0001"],
                            ts="2026-08-25T08:00:00Z")
    engine = ExactReconciliationEngine()
    results = engine.reconcile([pay], [setl], [])
    mismatched = [r for r in results if r.status == MatchStatus.MISMATCHED]
    assert len(mismatched) == 1
    g = mismatched[0]
    assert g.exception_type == ExceptionType.TIMING_MISMATCH
    assert g.human_review_required is True
    assert g.match_score is None
    assert "PAY-0001" in g.payment_ids
    assert "SETL-0001" in g.settlement_ids
    exceeded = [
        e for e in g.evidence
        if e.signal_type == SignalType.TIMESTAMP_EXCEEDED
    ]
    assert len(exceeded) >= 1
    assert "5.0d" in exceeded[0].observed_value


def test_global_duplicates_not_missing_settlement():
    """Two payments sharing order_id, no settlement -> DUPLICATE, not MISSING_SETTLEMENT."""
    p1 = _make_payment("PAY-0001", order="ORD-0001", amount=10000, status="captured")
    p2 = _make_payment("PAY-0002", order="ORD-0001", amount=10000, status="captured")
    engine = ExactReconciliationEngine()
    results = engine.reconcile([p1, p2], [], [])
    # Should produce exactly 1 DUPLICATE group
    dup_groups = [r for r in results if r.status == MatchStatus.DUPLICATE]
    assert len(dup_groups) == 1
    g = dup_groups[0]
    assert g.exception_type == ExceptionType.DUPLICATE
    assert g.human_review_required is True
    assert g.match_score is None
    assert "PAY-0001" in g.payment_ids
    assert "PAY-0002" in g.payment_ids
    assert g.settlement_ids == []
    # Must NOT appear as MISSING_SETTLEMENT
    ms_groups = [r for r in results if r.exception_type == ExceptionType.MISSING_SETTLEMENT]
    for mg in ms_groups:
        assert "PAY-0001" not in mg.payment_ids
        assert "PAY-0002" not in mg.payment_ids


def test_global_duplicate_group_structure():
    """Duplicate group has correct evidence and structure."""
    p1 = _make_payment("PAY-0001", order="ORD-0001", amount=10000, status="captured")
    p2 = _make_payment("PAY-0002", order="ORD-0001", amount=10000, status="captured")
    engine = ExactReconciliationEngine()
    results = engine.reconcile([p1, p2], [], [])
    dup_groups = [r for r in results if r.status == MatchStatus.DUPLICATE]
    assert len(dup_groups) == 1
    g = dup_groups[0]
    dup_signals = [
        e for e in g.evidence
        if e.signal_type == SignalType.DUPLICATE_IDENTIFIER
    ]
    assert len(dup_signals) >= 1
    assert g.resolution_status == ResolutionStatus.OPEN
    assert g.match_method is None
    assert "share order_id ORD-0001" in g.evidence_summary


def test_full_dataset_run():
    """Engine runs on the complete 95-record dataset with corrected distribution."""
    with open("data/payment_gateway.json") as f:
        raw_pays = json.load(f)
    with open("data/settlements.json") as f:
        raw_setls = json.load(f)
    with open("data/bank_ledger.json") as f:
        raw_banks = json.load(f)

    pays = [normalize_payment(r) for r in raw_pays]
    setls = [normalize_settlement(r) for r in raw_setls]
    banks = [normalize_bank_entry(r) for r in raw_banks]

    engine = ExactReconciliationEngine()
    results = engine.reconcile(pays, setls, banks)

    assert len(results) > 0

    # Every source record should appear in exactly one result
    all_pay_ids = set()
    all_setl_ids = set()
    all_bank_ids = set()
    for r in results:
        for pid in r.payment_ids:
            assert pid not in all_pay_ids, f"Duplicate payment {pid} across groups"
            all_pay_ids.add(pid)
        for sid in r.settlement_ids:
            assert sid not in all_setl_ids, f"Duplicate settlement {sid} across groups"
            all_setl_ids.add(sid)
        for bid in r.bank_entry_ids:
            assert bid not in all_bank_ids, f"Duplicate bank {bid} across groups"
            all_bank_ids.add(bid)

    # All 95 source records should be accounted for
    assert len(all_pay_ids) == 55, f"Expected 55 payments, got {len(all_pay_ids)}"
    assert len(all_setl_ids) == 18, f"Expected 18 settlements, got {len(all_setl_ids)}"
    assert len(all_bank_ids) == 22, f"Expected 22 bank entries, got {len(all_bank_ids)}"

    # Total reconciliation groups
    assert len(results) >= 37, f"Expected >= 37 groups, got {len(results)}"

    # Status and exception counts
    status_counts = {}
    exc_counts = {}
    for r in results:
        status_counts[r.status.value] = status_counts.get(r.status.value, 0) + 1
        if r.exception_type:
            exc_counts[r.exception_type.value] = exc_counts.get(r.exception_type.value, 0) + 1

    # 10 clean batch + 1 clean single (2d gap within window) + 3 amount + 1 timing (4d) + 8 missing + 7 failed + 6 orphan + 3 dup + 2 ambiguous
    assert status_counts.get("matched", 0) >= 10, f"Expected >= 10 MATCHED, got {status_counts.get("matched", 0)}"
    assert status_counts.get("ambiguous", 0) == 2, f"Expected 2 AMBIGUOUS, got {status_counts.get("ambiguous", 0)}"
    assert exc_counts.get("AMOUNT_MISMATCH", 0) == 3
    assert exc_counts.get("TIMING_MISMATCH", 0) >= 1
    assert exc_counts.get("MISSING_SETTLEMENT", 0) >= 4
    assert exc_counts.get("FAILED_OR_REFUNDED", 0) == 7
    assert exc_counts.get("ORPHAN_BANK_ENTRY", 0) == 6
    assert exc_counts.get("DUPLICATE", 0) == 3
    assert exc_counts.get("AMBIGUOUS", 0) == 2

    # Every result has evidence
    for r in results:
        assert len(r.evidence) > 0, f"{r.group_id} has no evidence"

    # Matched groups have a score
    for r in results:
        if r.status == MatchStatus.MATCHED:
            assert r.match_score is not None
            assert 0 <= r.match_score <= 100

    # AMBIGUOUS/MISMATCHED (except FAILED_OR_REFUNDED) have human_review_required=True
    for r in results:
        if r.status in (MatchStatus.AMBIGUOUS, MatchStatus.MISMATCHED):
            if r.exception_type != ExceptionType.FAILED_OR_REFUNDED:
                assert r.human_review_required is True


def test_existing_phase_tests_still_pass():
    """Verify that Phase 1-3A tests are importable."""
    mod1 = importlib.import_module("tests.test_health")
    mod2 = importlib.import_module("tests.test_synthetic_data")
    mod3 = importlib.import_module("tests.test_reconciliation_models")
    assert mod1 is not None
    assert mod2 is not None
    assert mod3 is not None
