"""Tests for batch settlement verification and decomposition (Phase 4)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from backend.models.canonical import PaymentStatus
from backend.reconciliation.batch import (
    DecompositionResult,
    decompose_settlement,
    verify_settlement_arithmetic,
)
from backend.reconciliation.matching import normalize_payment, normalize_settlement
from backend.reconciliation.models import (
    NormalizedPayment,
    NormalizedSettlement,
    SignalType,
)

TZ = timezone.utc
WINDOW = 3 * 86400  # 3 days in seconds


def _pay(pid="PAY-0001", order="ORD-0001", amount=10000,
         status="captured", ts="2026-08-20T08:00:00Z") -> NormalizedPayment:
    return normalize_payment({
        "payment_id": pid, "order_id": order, "customer_ref": "CUST-0001",
        "amount_paise": amount, "currency": "INR",
        "payment_timestamp": ts, "payment_status": status,
        "gateway_reference": f"GW-{pid.split(chr(45))[1]}",
    })


def _setl(sid="SETL-0001", amount=10000, fee=200,
          refs=None, ts="2026-08-21T08:00:00Z") -> NormalizedSettlement:
    return normalize_settlement({
        "settlement_id": sid, "settlement_timestamp": ts,
        "amount_paise": amount, "currency": "INR",
        "fee_paise": fee, "net_amount_paise": amount - fee,
        "payment_refs": refs or [], "settlement_status": "settled",
        "gateway_settlement_reference": f"GWSETL-{sid.split(chr(45))[1]}",
        "is_known_exception": False,
    })


# -----------------------------------------------------------------------
# 1: Valid settlement arithmetic
# -----------------------------------------------------------------------
def test_arithmetic_valid():
    s = _setl(amount=10000, fee=200)
    p = _pay(amount=10000)
    valid, evidence = verify_settlement_arithmetic(s, [p])
    assert valid is True
    fee_ev = [e for e in evidence if "10000-200==9800" in e.observed_value]
    assert len(fee_ev) == 1


# -----------------------------------------------------------------------
# 2: Invalid fee/net arithmetic
# -----------------------------------------------------------------------
def test_arithmetic_invalid_fee():
    s = _setl(amount=10000, fee=200)
    # Manually create settlement with wrong net
    from dataclasses import replace
    bad_s = replace(s, net_amount_paise=9500)
    p = _pay(amount=10000)
    valid, evidence = verify_settlement_arithmetic(bad_s, [p])
    assert valid is False
    mismatch_ev = [e for e in evidence if "!=" in e.observed_value and e.signal_type == SignalType.EXACT_AMOUNT]
    assert len(mismatch_ev) >= 1


# -----------------------------------------------------------------------
# 3: Valid batch sum
# -----------------------------------------------------------------------
def test_batch_sum_valid():
    s = _setl(amount=15000, fee=300)
    p1 = _pay("PAY-0001", amount=8000)
    p2 = _pay("PAY-0002", "ORD-0002", amount=7000)
    valid, evidence = verify_settlement_arithmetic(s, [p1, p2])
    assert valid is True
    batch_ev = [e for e in evidence if e.signal_type == SignalType.BATCH_AMOUNT_MATCH]
    assert len(batch_ev) == 1
    assert "15000==15000" in batch_ev[0].observed_value


# -----------------------------------------------------------------------
# 4: Invalid batch sum
# -----------------------------------------------------------------------
def test_batch_sum_invalid():
    s = _setl(amount=15000, fee=300)
    p1 = _pay("PAY-0001", amount=8000)
    p2 = _pay("PAY-0002", "ORD-0002", amount=5000)
    valid, evidence = verify_settlement_arithmetic(s, [p1, p2])
    assert valid is False
    mismatch_ev = [e for e in evidence if "13000!=" in e.observed_value]
    assert len(mismatch_ev) == 1


# -----------------------------------------------------------------------
# 5: Exact single-payment decomposition
# -----------------------------------------------------------------------
def test_decompose_single_exact():
    s = _setl(amount=10000, fee=200, ts="2026-08-22T08:00:00Z")
    p = _pay(amount=10000, ts="2026-08-21T08:00:00Z")
    result = decompose_settlement(s, [p], WINDOW)
    assert result.status == "matched"
    assert len(result.matched_payments) == 1
    assert result.matched_payments[0].payment_id == "PAY-0001"
    ref_ev = [e for e in result.evidence if e.signal_type == SignalType.PAYMENT_REFERENCE]
    assert len(ref_ev) == 1


# -----------------------------------------------------------------------
# 6: Exact multi-payment decomposition
# -----------------------------------------------------------------------
def test_decompose_batch_exact():
    s = _setl(amount=15000, fee=300, ts="2026-08-22T08:00:00Z")
    p1 = _pay("PAY-0001", amount=8000, ts="2026-08-21T08:00:00Z")
    p2 = _pay("PAY-0002", "ORD-0002", amount=7000, ts="2026-08-21T08:00:00Z")
    result = decompose_settlement(s, [p1, p2], WINDOW)
    assert result.status == "matched"
    assert len(result.matched_payments) == 2
    batch_ev = [e for e in result.evidence if e.signal_type == SignalType.BATCH_AMOUNT_MATCH]
    assert len(batch_ev) == 1


# -----------------------------------------------------------------------
# 7: No matching subset
# -----------------------------------------------------------------------
def test_decompose_no_match():
    s = _setl(amount=25000, fee=500, ts="2026-08-22T08:00:00Z")
    p1 = _pay("PAY-0001", amount=8000, ts="2026-08-21T08:00:00Z")
    p2 = _pay("PAY-0002", "ORD-0002", amount=7000, ts="2026-08-21T08:00:00Z")
    result = decompose_settlement(s, [p1, p2], WINDOW)
    assert result.status == "no_match"
    assert len(result.matched_payments) == 0
    missing_ev = [e for e in result.evidence if "no_valid_subset" in e.observed_value]
    assert len(missing_ev) == 1


# -----------------------------------------------------------------------
# 8: Ambiguous decomposition
# -----------------------------------------------------------------------
def test_decompose_ambiguous():
    s = _setl(amount=10000, fee=200, ts="2026-08-22T08:00:00Z")
    p1 = _pay("PAY-0001", amount=10000, ts="2026-08-21T08:00:00Z")
    p2 = _pay("PAY-0002", "ORD-0002", amount=10000, ts="2026-08-21T08:00:00Z")
    result = decompose_settlement(s, [p1, p2], WINDOW)
    assert result.status == "ambiguous"
    assert len(result.matched_payments) == 0
    ambiguous_ev = [e for e in result.evidence if "2_valid_subsets" in e.observed_value]
    assert len(ambiguous_ev) == 1


# -----------------------------------------------------------------------
# 9: Timing violation
# -----------------------------------------------------------------------
def test_decompose_timing_violation():
    s = _setl(amount=10000, fee=200, ts="2026-08-25T08:00:00Z")
    # Payment 5 days before settlement -> exceeds 3-day window
    p = _pay(amount=10000, ts="2026-08-20T08:00:00Z")
    result = decompose_settlement(s, [p], WINDOW)
    assert result.status == "timing_mismatch"
    assert len(result.matched_payments) == 1
    exceeded_ev = [e for e in result.evidence if e.signal_type == SignalType.TIMESTAMP_EXCEEDED]
    assert len(exceeded_ev) == 1
    assert "5.0d" in exceeded_ev[0].observed_value


# -----------------------------------------------------------------------
# 10: Payment after settlement
# -----------------------------------------------------------------------
def test_decompose_payment_after_settlement():
    s = _setl(amount=10000, fee=200, ts="2026-08-20T08:00:00Z")
    # Payment after settlement -> excluded from eligible
    p = _pay(amount=10000, ts="2026-08-21T08:00:00Z")
    result = decompose_settlement(s, [p], WINDOW)
    assert result.status == "no_match"
    assert len(result.matched_payments) == 0


# -----------------------------------------------------------------------
# 11: Currency filtering
# -----------------------------------------------------------------------
def test_decompose_currency_filter():
    s = _setl(amount=10000, fee=200, ts="2026-08-22T08:00:00Z")
    # Create a USD payment (different currency)
    usd_pay = normalize_payment({
        "payment_id": "PAY-USD", "order_id": "ORD-USD",
        "customer_ref": "CUST-0001",
        "amount_paise": 10000, "currency": "USD",
        "payment_timestamp": "2026-08-21T08:00:00Z",
        "payment_status": "captured",
        "gateway_reference": "GW-USD",
    })
    result = decompose_settlement(s, [usd_pay], WINDOW)
    assert result.status == "no_match"
    assert len(result.matched_payments) == 0


# -----------------------------------------------------------------------
# 12: Failed-payment filtering
# -----------------------------------------------------------------------
def test_decompose_status_filter():
    s = _setl(amount=10000, fee=200, ts="2026-08-22T08:00:00Z")
    p = _pay(amount=10000, status="failed", ts="2026-08-21T08:00:00Z")
    result = decompose_settlement(s, [p], WINDOW)
    assert result.status == "no_match"
    assert len(result.matched_payments) == 0


# -----------------------------------------------------------------------
# 13: Timing-valid subset despite unrelated timing-invalid candidates
# -----------------------------------------------------------------------
def test_decompose_timing_valid_subset_exists():
    s = _setl(amount=10000, fee=200, ts="2026-08-22T08:00:00Z")
    # Timing-valid candidate
    p_valid = _pay("PAY-V", amount=10000, ts="2026-08-21T08:00:00Z")
    # Timing-invalid candidate (5 days before)
    p_invalid = _pay("PAY-I", "ORD-I", amount=10000, ts="2026-08-17T08:00:00Z")
    result = decompose_settlement(s, [p_valid, p_invalid], WINDOW)
    assert result.status == "matched"
    assert len(result.matched_payments) == 1
    assert result.matched_payments[0].payment_id == "PAY-V"


# -----------------------------------------------------------------------
# 14: Only timing-invalid subset
# -----------------------------------------------------------------------
def test_decompose_only_timing_violating():
    s = _setl(amount=10000, fee=200, ts="2026-08-22T08:00:00Z")
    # Only timing-invalid candidate that matches amount
    p = _pay(amount=10000, ts="2026-08-17T08:00:00Z")
    result = decompose_settlement(s, [p], WINDOW)
    assert result.status == "timing_mismatch"
    assert len(result.matched_payments) == 1
    exceeded_ev = [e for e in result.evidence if e.signal_type == SignalType.TIMESTAMP_EXCEEDED]
    assert len(exceeded_ev) == 1


# -----------------------------------------------------------------------
# 15: Fee evidence
# -----------------------------------------------------------------------
def test_single_payment_fee_evidence():
    s = _setl(amount=10000, fee=200)
    p = _pay(amount=10000)
    valid, evidence = verify_settlement_arithmetic(s, [p])
    assert valid is True
    # Should have fee evidence (amount-fee==net)
    fee_ev = [e for e in evidence if "10000-200==9800" in e.observed_value]
    assert len(fee_ev) == 1
    assert fee_ev[0].signal_type == SignalType.EXACT_AMOUNT
    # Should have single-payment amount evidence
    amt_ev = [e for e in evidence if e.observed_value == "10000" and e.source_record_id == "PAY-0001"]
    assert len(amt_ev) == 1
