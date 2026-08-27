"""Exact deterministic reconciliation engine.

Implements the DeterministicReconciliationEngine protocol using
exact matching only. All decisions are based on observable
source-data evidence. No AI, no fuzzy matching, no ground truth access.
"""

from __future__ import annotations

import itertools
from collections import defaultdict

from backend.models.canonical import PaymentStatus
from backend.reconciliation.matching import (
    build_bank_by_ref,
    build_payment_index,
    build_settlement_by_payment,
    build_settlement_index,
    detect_payment_duplicates,
    make_evidence,
)
from backend.reconciliation.models import (
    ExceptionType,
    MatchMethod,
    MatchStatus,
    NormalizedBankEntry,
    NormalizedPayment,
    NormalizedSettlement,
    ResolutionStatus,
    ReconciliationResult,
    SignalType,
)

_PTS_PAYMENT_REF = 25
_PTS_EXACT_AMOUNT = 20
_PTS_CURRENCY = 10
_PTS_TIMESTAMP = 15
_PTS_BATCH_AMOUNT = 20
_PTS_MISSING = 0
_PTS_DUPLICATE = 0
_MAX_SCORE = 100

# Timing window: derived from docs/architecture.md S4/S5 signals and severity thresholds.
SETTLEMENT_TIMING_WINDOW_DAYS: int = 3
_SETTLEMENT_TIMING_WINDOW_SECONDS: float = SETTLEMENT_TIMING_WINDOW_DAYS * 86400


class ExactReconciliationEngine:
    """Deterministic reconciliation engine using exact matching only.

    Satisfies the DeterministicReconciliationEngine protocol.
    All decisions are based on observable deterministic evidence.
    """

    def reconcile(
        self,
        payments: list[NormalizedPayment],
        settlements: list[NormalizedSettlement],
        bank_entries: list[NormalizedBankEntry],
    ) -> list[ReconciliationResult]:
        pay_idx = build_payment_index(payments)
        setl_idx = build_settlement_index(settlements)
        setl_by_pay = build_settlement_by_payment(settlements)
        bank_by_ref = build_bank_by_ref(bank_entries)

        # Step 0: Detect global duplicate payment groups (store only, do not classify).
        dupes = detect_payment_duplicates(payments)

        assigned_payments: set[str] = set()
        assigned_settlements: set[str] = set()
        assigned_banks: set[str] = set()

        results: list[ReconciliationResult] = []
        group_counter = itertools.count(1)
        # Step 1: Process settlements with non-empty payment_refs.
        for s in settlements:
            if not s.payment_refs:
                continue

            evidence_list = []
            referenced_payments: list[NormalizedPayment] = []
            missing_refs: list[str] = []
            has_amount_mismatch = False
            has_timing_violation = False

            for ref_id in s.payment_refs:
                if ref_id in pay_idx:
                    pay = pay_idx[ref_id]
                    referenced_payments.append(pay)
                    evidence_list.append(make_evidence(
                        SignalType.PAYMENT_REFERENCE, s.settlement_id,
                        ref_id, _PTS_PAYMENT_REF, f"E{len(evidence_list)+1}",
                    ))
                    if pay.currency == s.currency:
                        evidence_list.append(make_evidence(
                            SignalType.CURRENCY_MATCH, s.settlement_id,
                            s.currency, _PTS_CURRENCY, f"E{len(evidence_list)+1}",
                        ))
                    # Precise timing check using total_seconds()
                    elapsed_seconds = (s.timestamp - pay.timestamp).total_seconds()
                    if elapsed_seconds < 0:
                        has_timing_violation = True
                        evidence_list.append(make_evidence(
                            SignalType.TIMESTAMP_EXCEEDED, pay.payment_id,
                            "payment_after_settlement", 0,
                            f"E{len(evidence_list)+1}",
                        ))
                    elif elapsed_seconds > _SETTLEMENT_TIMING_WINDOW_SECONDS:
                        has_timing_violation = True
                        days = elapsed_seconds / 86400
                        evidence_list.append(make_evidence(
                            SignalType.TIMESTAMP_EXCEEDED, pay.payment_id,
                            f"{days:.1f}d>{SETTLEMENT_TIMING_WINDOW_DAYS}d", 0,
                            f"E{len(evidence_list)+1}",
                        ))
                    else:
                        evidence_list.append(make_evidence(
                            SignalType.TIMESTAMP_WITHIN_WINDOW, pay.payment_id,
                            str(pay.timestamp.date()), _PTS_TIMESTAMP,
                            f"E{len(evidence_list)+1}",
                        ))
                else:
                    missing_refs.append(ref_id)
                    evidence_list.append(make_evidence(
                        SignalType.MISSING_RECORD, s.settlement_id,
                        ref_id, _PTS_MISSING, f"E{len(evidence_list)+1}",
                    ))

            # Amount verification
            ref_sum = sum(p.amount_paise for p in referenced_payments)
            if ref_sum == s.amount_paise:
                signal = SignalType.BATCH_AMOUNT_MATCH if len(referenced_payments) > 1 else SignalType.EXACT_AMOUNT
                pts = _PTS_BATCH_AMOUNT if len(referenced_payments) > 1 else _PTS_EXACT_AMOUNT
                evidence_list.append(make_evidence(
                    signal, s.settlement_id,
                    f"{ref_sum}=={s.amount_paise}", pts,
                    f"E{len(evidence_list)+1}",
                ))
            elif referenced_payments:
                has_amount_mismatch = True
                evidence_list.append(make_evidence(
                    SignalType.EXACT_AMOUNT, s.settlement_id,
                    f"{ref_sum}!={s.amount_paise}", _PTS_MISSING,
                    f"E{len(evidence_list)+1}",
                ))

            # Single-payment amount verification
            if len(referenced_payments) == 1:
                pay = referenced_payments[0]
                if pay.amount_paise == s.amount_paise:
                    evidence_list.append(make_evidence(
                        SignalType.EXACT_AMOUNT, pay.payment_id,
                        str(pay.amount_paise), _PTS_EXACT_AMOUNT,
                        f"E{len(evidence_list)+1}",
                    ))

            # Duplicate evidence for referenced payments (DO NOT add unreferenced partners)
            for pay in referenced_payments:
                if pay.order_id in dupes and len(dupes[pay.order_id]) > 1:
                    evidence_list.append(make_evidence(
                        SignalType.DUPLICATE_IDENTIFIER, pay.payment_id,
                        f"order_id={pay.order_id}", _PTS_DUPLICATE,
                        f"E{len(evidence_list)+1}",
                    ))

            # Bank entry verification
            bank = bank_by_ref.get(s.settlement_id)
            if bank:
                assigned_banks.add(bank.bank_entry_id)
                if bank.amount_paise == s.net_amount_paise:
                    evidence_list.append(make_evidence(
                        SignalType.EXACT_AMOUNT, bank.bank_entry_id,
                        str(bank.amount_paise), _PTS_EXACT_AMOUNT,
                        f"E{len(evidence_list)+1}",
                    ))
                else:
                    has_amount_mismatch = True
                    evidence_list.append(make_evidence(
                        SignalType.EXACT_AMOUNT, bank.bank_entry_id,
                        f"{bank.amount_paise}!={s.net_amount_paise}", _PTS_MISSING,
                        f"E{len(evidence_list)+1}",
                    ))

            # Only explicitly referenced payment IDs are assigned to this group
            all_pay_ids = [p.payment_id for p in referenced_payments]
            setl_ids = [s.settlement_id]
            bank_ids = [bank.bank_entry_id] if bank else []

            for pid in all_pay_ids:
                assigned_payments.add(pid)
            assigned_settlements.add(s.settlement_id)

            # Classification: amount > timing > duplicate > matched
            if has_amount_mismatch or missing_refs:
                status = MatchStatus.MISMATCHED
                exc = ExceptionType.AMOUNT_MISMATCH
                resolution = ResolutionStatus.OPEN
                human_review = True
                score = None
                method = None
            elif has_timing_violation:
                status = MatchStatus.MISMATCHED
                exc = ExceptionType.TIMING_MISMATCH
                resolution = ResolutionStatus.OPEN
                human_review = True
                score = None
                method = None
            else:
                status = MatchStatus.MATCHED
                exc = None
                resolution = ResolutionStatus.RESOLVED
                human_review = False
                score = min(sum(e.points for e in evidence_list), _MAX_SCORE)
                method = MatchMethod.EXACT_KEY

            summary_parts = []
            if status == MatchStatus.MATCHED:
                summary_parts.append(f"Matched {len(referenced_payments)} payment(s) to {s.settlement_id} via exact references.")
            elif exc == ExceptionType.AMOUNT_MISMATCH:
                summary_parts.append(f"Mismatch detected for {s.settlement_id}: amounts do not align.")
            elif exc == ExceptionType.TIMING_MISMATCH:
                summary_parts.append(f"Timing violation for {s.settlement_id}: settlement too late.")

            if bank:
                if bank.amount_paise == s.net_amount_paise:
                    summary_parts.append(f"Bank entry {bank.bank_entry_id} matches net amount.")
                else:
                    summary_parts.append(f"Bank entry {bank.bank_entry_id} amount differs from net amount.")

            results.append(ReconciliationResult(
                group_id=f"GRP-{next(group_counter):04d}",
                status=status,
                payment_ids=all_pay_ids,
                settlement_ids=setl_ids,
                bank_entry_ids=bank_ids,
                match_score=score,
                match_method=method,
                exception_type=exc,
                resolution_status=resolution,
                evidence=evidence_list,
                evidence_summary=" ".join(summary_parts) if summary_parts else None,
                human_review_required=human_review,
            ))

        # Step 2: Settlements with empty payment_refs -> AMBIGUOUS
        for s in settlements:
            if s.settlement_id in assigned_settlements:
                continue
            if s.payment_refs:
                continue

            evidence_list = [
                make_evidence(
                    SignalType.PAYMENT_REFERENCE, s.settlement_id,
                    "NONE", _PTS_MISSING, "E1",
                ),
            ]

            bank = bank_by_ref.get(s.settlement_id)
            bank_ids = []
            if bank:
                assigned_banks.add(bank.bank_entry_id)
                bank_ids = [bank.bank_entry_id]
                evidence_list.append(make_evidence(
                    SignalType.EXACT_AMOUNT, bank.bank_entry_id,
                    str(bank.amount_paise), _PTS_EXACT_AMOUNT, "E2",
                ))

            assigned_settlements.add(s.settlement_id)
            results.append(ReconciliationResult(
                group_id=f"GRP-{next(group_counter):04d}",
                status=MatchStatus.AMBIGUOUS,
                payment_ids=[],
                settlement_ids=[s.settlement_id],
                bank_entry_ids=bank_ids,
                match_score=None,
                match_method=None,
                exception_type=ExceptionType.AMBIGUOUS,
                resolution_status=ResolutionStatus.OPEN,
                evidence=evidence_list,
                evidence_summary=f"Settlement {s.settlement_id} has no payment references. Cannot determine correct payment match.",
                human_review_required=True,
            ))

        # Step 3: Unmatched payments -> DUPLICATE, FAILED_OR_REFUNDED, or MISSING_SETTLEMENT
        for p in payments:
            if p.payment_id in assigned_payments:
                continue

            if p.status in (PaymentStatus.FAILED, PaymentStatus.REFUNDED):
                evidence_list = [
                    make_evidence(
                        SignalType.MISSING_RECORD, p.payment_id,
                        f"status={p.status.value}", 0, "E1",
                    ),
                ]
                assigned_payments.add(p.payment_id)
                results.append(ReconciliationResult(
                    group_id=f"GRP-{next(group_counter):04d}",
                    status=MatchStatus.MISMATCHED,
                    payment_ids=[p.payment_id],
                    settlement_ids=[],
                    bank_entry_ids=[],
                    match_score=None,
                    match_method=None,
                    exception_type=ExceptionType.FAILED_OR_REFUNDED,
                    resolution_status=ResolutionStatus.RESOLVED,
                    evidence=evidence_list,
                    evidence_summary=f"Payment {p.payment_id} has status {p.status.value}. No settlement expected.",
                    human_review_required=False,
                ))
                continue

            if p.payment_id in setl_by_pay:
                continue

            # Check if this payment belongs to a known duplicate group
            handled_as_duplicate = False
            for order_id, pids in dupes.items():
                if p.payment_id in pids and len(pids) > 1:
                    dup_partner_ids = [
                        d for d in pids if d != p.payment_id and d not in assigned_payments
                    ]
                    all_dup_ids = [p.payment_id] + dup_partner_ids
                    for dpid in all_dup_ids:
                        assigned_payments.add(dpid)
                    evidence_list = [
                        make_evidence(
                            SignalType.DUPLICATE_IDENTIFIER, p.payment_id,
                            f"order_id={p.order_id}", 0, "E1",
                        ),
                    ]
                    results.append(ReconciliationResult(
                        group_id=f"GRP-{next(group_counter):04d}",
                        status=MatchStatus.DUPLICATE,
                        payment_ids=all_dup_ids,
                        settlement_ids=[],
                        bank_entry_ids=[],
                        match_score=None,
                        match_method=None,
                        exception_type=ExceptionType.DUPLICATE,
                        resolution_status=ResolutionStatus.OPEN,
                        evidence=evidence_list,
                        evidence_summary=f"Payments {all_dup_ids} share order_id {order_id}. Duplicate detected.",
                        human_review_required=True,
                    ))
                    handled_as_duplicate = True
                    break

            if handled_as_duplicate:
                continue

            # No duplicate, no settlement -> MISSING_SETTLEMENT
            evidence_list = [
                make_evidence(
                    SignalType.MISSING_RECORD, p.payment_id,
                    "no_settlement", _PTS_MISSING, "E1",
                ),
            ]
            assigned_payments.add(p.payment_id)
            results.append(ReconciliationResult(
                group_id=f"GRP-{next(group_counter):04d}",
                status=MatchStatus.MISMATCHED,
                payment_ids=[p.payment_id],
                settlement_ids=[],
                bank_entry_ids=[],
                match_score=None,
                match_method=None,
                exception_type=ExceptionType.MISSING_SETTLEMENT,
                resolution_status=ResolutionStatus.OPEN,
                evidence=evidence_list,
                evidence_summary=f"Payment {p.payment_id} has no corresponding settlement.",
                human_review_required=True,
            ))

        # Step 4: Unmatched bank entries -> ORPHAN_BANK_ENTRY
        for b in bank_entries:
            if b.bank_entry_id in assigned_banks:
                continue

            evidence_list = [
                make_evidence(
                    SignalType.MISSING_RECORD, b.bank_entry_id,
                    f"reference={b.reference}", _PTS_MISSING, "E1",
                ),
            ]
            assigned_banks.add(b.bank_entry_id)
            results.append(ReconciliationResult(
                group_id=f"GRP-{next(group_counter):04d}",
                status=MatchStatus.MISMATCHED,
                payment_ids=[],
                settlement_ids=[],
                bank_entry_ids=[b.bank_entry_id],
                match_score=None,
                match_method=None,
                exception_type=ExceptionType.ORPHAN_BANK_ENTRY,
                resolution_status=ResolutionStatus.OPEN,
                evidence=evidence_list,
                evidence_summary=f"Bank entry {b.bank_entry_id} (ref: {b.reference}) has no matching settlement.",
                human_review_required=True,
            ))

        return results

