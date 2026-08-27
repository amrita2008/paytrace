"""Normalization and pure helper functions for deterministic reconciliation.

Converts raw JSON records into typed Phase 3A models. Provides index
builders and evidence construction helpers. No business logic beyond
data transformation.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from backend.models.canonical import (
    BankEntryType,
    BankLedgerStatus,
    PaymentStatus,
    SettlementStatus,
)
from backend.reconciliation.models import (
    MatchEvidence,
    NormalizedBankEntry,
    NormalizedPayment,
    NormalizedSettlement,
    SignalType,
)


# ---------------------------------------------------------------------------
# Normalization: raw JSON dict -> Phase 3A model
# ---------------------------------------------------------------------------

def normalize_payment(raw: dict[str, Any]) -> NormalizedPayment:
    """Convert a raw payment_gateway.json record to NormalizedPayment."""
    return NormalizedPayment(
        payment_id=raw["payment_id"],
        order_id=raw["order_id"],
        amount_paise=int(raw["amount_paise"]),
        fee_paise=0,
        net_amount_paise=int(raw["amount_paise"]),
        currency=raw["currency"],
        status=PaymentStatus(raw["payment_status"]),
        timestamp=_parse_ts(raw["payment_timestamp"]),
        gateway_reference=raw["gateway_reference"],
    )


def normalize_settlement(raw: dict[str, Any]) -> NormalizedSettlement:
    """Convert a raw settlements.json record to NormalizedSettlement."""
    return NormalizedSettlement(
        settlement_id=raw["settlement_id"],
        amount_paise=int(raw["amount_paise"]),
        fee_paise=int(raw["fee_paise"]),
        net_amount_paise=int(raw["net_amount_paise"]),
        currency=raw["currency"],
        status=SettlementStatus(raw["settlement_status"]),
        timestamp=_parse_ts(raw["settlement_timestamp"]),
        payment_refs=list(raw.get("payment_refs", [])),
        gateway_settlement_reference=raw["gateway_settlement_reference"],
        is_known_exception=raw.get("is_known_exception", False),
    )


def normalize_bank_entry(raw: dict[str, Any]) -> NormalizedBankEntry:
    """Convert a raw bank_ledger.json record to NormalizedBankEntry."""
    return NormalizedBankEntry(
        bank_entry_id=raw["bank_entry_id"],
        amount_paise=int(raw["amount_paise"]),
        currency=raw["currency"],
        entry_type=BankEntryType(raw["entry_type"]),
        ledger_status=BankLedgerStatus(raw["ledger_status"]),
        timestamp=_parse_ts(raw["entry_timestamp"]),
        reference=raw["reference"],
    )


# ---------------------------------------------------------------------------
# Index builders
# ---------------------------------------------------------------------------

def build_payment_index(
    payments: list[NormalizedPayment],
) -> dict[str, NormalizedPayment]:
    """payment_id -> NormalizedPayment."""
    return {p.payment_id: p for p in payments}


def build_settlement_index(
    settlements: list[NormalizedSettlement],
) -> dict[str, NormalizedSettlement]:
    """settlement_id -> NormalizedSettlement."""
    return {s.settlement_id: s for s in settlements}


def build_settlement_by_payment(
    settlements: list[NormalizedSettlement],
) -> dict[str, str]:
    """payment_id -> settlement_id (from payment_refs)."""
    index: dict[str, str] = {}
    for s in settlements:
        for ref in s.payment_refs:
            index[ref] = s.settlement_id
    return index


def build_order_to_payments(
    payments: list[NormalizedPayment],
) -> dict[str, list[str]]:
    """order_id -> [payment_ids] for captured payments only."""
    index: dict[str, list[str]] = defaultdict(list)
    for p in payments:
        if p.status == PaymentStatus.CAPTURED:
            index[p.order_id].append(p.payment_id)
    return dict(index)


def build_bank_by_ref(
    bank_entries: list[NormalizedBankEntry],
) -> dict[str, NormalizedBankEntry]:
    """reference -> NormalizedBankEntry."""
    return {b.reference: b for b in bank_entries}


# ---------------------------------------------------------------------------
# Duplicate detection
# ---------------------------------------------------------------------------

def detect_payment_duplicates(
    payments: list[NormalizedPayment],
) -> dict[str, list[str]]:
    """Return order_id -> [payment_ids] for captured payments sharing an order_id."""
    order_map = build_order_to_payments(payments)
    return {
        order_id: pids
        for order_id, pids in order_map.items()
        if len(pids) > 1
    }


# ---------------------------------------------------------------------------
# Evidence helper
# ---------------------------------------------------------------------------

def make_evidence(
    signal_type: SignalType,
    source_record_id: str,
    observed_value: str,
    points: int,
    signal_id: str,
) -> MatchEvidence:
    """Construct a MatchEvidence instance."""
    return MatchEvidence(
        signal_id=signal_id,
        source_record_id=source_record_id,
        signal_type=signal_type,
        observed_value=observed_value,
        points=points,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _parse_ts(ts_str: str) -> datetime:
    """Parse ISO-8601 timestamp to timezone-aware datetime (UTC)."""
    ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts
