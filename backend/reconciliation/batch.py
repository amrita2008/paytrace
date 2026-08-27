"""Batch settlement verification and bounded deterministic decomposition."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

from backend.reconciliation.models import (
    MatchEvidence,
    NormalizedPayment,
    NormalizedSettlement,
    SignalType,
)
from backend.reconciliation.matching import make_evidence


@dataclass(frozen=True)
class DecompositionResult:
    """Result of attempting batch decomposition on a settlement."""
    status: str  # matched | ambiguous | no_match | timing_mismatch
    matched_payments: list[NormalizedPayment]
    evidence: list[MatchEvidence]


def verify_settlement_arithmetic(
    settlement: NormalizedSettlement,
    payments: list[NormalizedPayment],
) -> tuple[bool, list[MatchEvidence]]:
    """Verify settlement arithmetic and batch sum."""
    evidence: list[MatchEvidence] = []
    is_valid = True
    eid = 0

    def _n() -> str:
        nonlocal eid
        eid += 1
        return f"V{eid}"

    # 1. Internal: amount - fee == net
    expected_net = settlement.amount_paise - settlement.fee_paise
    if expected_net == settlement.net_amount_paise:
        evidence.append(make_evidence(
            SignalType.EXACT_AMOUNT, settlement.settlement_id,
            f"{settlement.amount_paise}-{settlement.fee_paise}=={settlement.net_amount_paise}",
            20, _n(),
        ))
    else:
        is_valid = False
        evidence.append(make_evidence(
            SignalType.EXACT_AMOUNT, settlement.settlement_id,
            f"{settlement.amount_paise}-{settlement.fee_paise}!={settlement.net_amount_paise}",
            0, _n(),
        ))

    # 2. Batch sum
    if payments:
        ref_sum = sum(p.amount_paise for p in payments)
        if ref_sum == settlement.amount_paise:
            evidence.append(make_evidence(
                SignalType.BATCH_AMOUNT_MATCH, settlement.settlement_id,
                f"{ref_sum}=={settlement.amount_paise}",
                20, _n(),
            ))
        else:
            is_valid = False
            evidence.append(make_evidence(
                SignalType.EXACT_AMOUNT, settlement.settlement_id,
                f"{ref_sum}!={settlement.amount_paise}",
                0, _n(),
            ))

    # 3. Single-payment amount
    if len(payments) == 1:
        p = payments[0]
        if p.amount_paise == settlement.amount_paise:
            evidence.append(make_evidence(
                SignalType.EXACT_AMOUNT, p.payment_id,
                str(p.amount_paise), 20, _n(),
            ))

    # 4. Currency consistency
    if payments:
        if all(p.currency == settlement.currency for p in payments):
            evidence.append(make_evidence(
                SignalType.CURRENCY_MATCH, settlement.settlement_id,
                settlement.currency, 10, _n(),
            ))
        else:
            is_valid = False

    return is_valid, evidence


def decompose_settlement(
    settlement: NormalizedSettlement,
    candidate_payments: list[NormalizedPayment],
    timing_window_seconds: float,
) -> DecompositionResult:
    """Bounded deterministic subset-sum decomposition."""
    eid = [0]
    def _e() -> str:
        eid[0] += 1
        return f"D{eid[0]}"

    evidence: list[MatchEvidence] = []

    # Filter eligible: captured, currency match, amount <= settlement, precedes settlement
    eligible: list[NormalizedPayment] = []
    for p in candidate_payments:
        if p.status.value != "captured":
            continue
        if p.currency != settlement.currency:
            continue
        if p.amount_paise > settlement.amount_paise:
            continue
        if p.timestamp > settlement.timestamp:
            continue
        eligible.append(p)

    # Separate timing-valid from timing-violating
    timing_valid: list[NormalizedPayment] = []
    timing_violating: list[NormalizedPayment] = []
    for p in eligible:
        elapsed = (settlement.timestamp - p.timestamp).total_seconds()
        if elapsed < 0 or elapsed > timing_window_seconds:
            timing_violating.append(p)
        else:
            timing_valid.append(p)

    # Attempt with timing-valid candidates
    valid_subsets = _find_subsets(timing_valid, settlement.amount_paise)

    if len(valid_subsets) == 1:
        subset = valid_subsets[0]
        for p in subset:
            evidence.append(make_evidence(
                SignalType.PAYMENT_REFERENCE, settlement.settlement_id,
                p.payment_id, 25, _e(),
            ))
            evidence.append(make_evidence(
                SignalType.CURRENCY_MATCH, settlement.settlement_id,
                p.currency, 10, _e(),
            ))
            evidence.append(make_evidence(
                SignalType.TIMESTAMP_WITHIN_WINDOW, p.payment_id,
                str(p.timestamp.date()), 15, _e(),
            ))
        evidence.append(make_evidence(
            SignalType.BATCH_AMOUNT_MATCH, settlement.settlement_id,
            f"{settlement.amount_paise}=={settlement.amount_paise}",
            20, _e(),
        ))
        return DecompositionResult(status="matched", matched_payments=list(subset), evidence=evidence)

    if len(valid_subsets) > 1:
        evidence.append(make_evidence(
            SignalType.PAYMENT_REFERENCE, settlement.settlement_id,
            "NONE", 0, _e(),
        ))
        evidence.append(make_evidence(
            SignalType.MISSING_RECORD, settlement.settlement_id,
            f"{len(valid_subsets)}_valid_subsets", 0, _e(),
        ))
        return DecompositionResult(status="ambiguous", matched_payments=[], evidence=evidence)

    # No timing-valid subset. Check timing-violating candidates.
    tv_subsets = _find_subsets(timing_violating, settlement.amount_paise)
    if tv_subsets:
        subset = tv_subsets[0]
        for p in subset:
            elapsed = (settlement.timestamp - p.timestamp).total_seconds()
            days = elapsed / 86400
            evidence.append(make_evidence(
                SignalType.TIMESTAMP_EXCEEDED, p.payment_id,
                f"{days:.1f}d>3d", 0, _e(),
            ))
        evidence.append(make_evidence(
            SignalType.MISSING_RECORD, settlement.settlement_id,
            "timing_violation", 0, _e(),
        ))
        return DecompositionResult(status="timing_mismatch", matched_payments=list(subset), evidence=evidence)

    # No subset at all
    evidence.append(make_evidence(
        SignalType.PAYMENT_REFERENCE, settlement.settlement_id,
        "NONE", 0, _e(),
    ))
    evidence.append(make_evidence(
        SignalType.MISSING_RECORD, settlement.settlement_id,
        "no_valid_subset", 0, _e(),
    ))
    return DecompositionResult(status="no_match", matched_payments=[], evidence=evidence)


def _find_subsets(
    candidates: list[NormalizedPayment],
    target: int,
) -> list[tuple[NormalizedPayment, ...]]:
    """Find all subsets of candidates that sum to target."""
    if not candidates or target <= 0:
        return []
    sorted_cands = sorted(candidates, key=lambda p: p.amount_paise, reverse=True)
    min_amount = sorted_cands[-1].amount_paise
    max_size = min(len(sorted_cands), target // min_amount)
    results: list[tuple[NormalizedPayment, ...]] = []
    for size in range(1, max_size + 1):
        for subset in combinations(sorted_cands, size):
            if sum(p.amount_paise for p in subset) == target:
                results.append(subset)
    return results

