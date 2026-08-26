"""Reconciliation interfaces (protocols).

Defines contracts for the deterministic reconciliation engine.
Implementations will follow in later phases. Phase 3A only
establishes the interfaces.
"""

from __future__ import annotations

from typing import Protocol

from backend.reconciliation.models import (
    NormalizedBankEntry,
    NormalizedPayment,
    NormalizedSettlement,
    ReconciliationResult,
)


class BatchReconciliationProtocol(Protocol):
    """Contract for batch settlement reconciliation.

    Verifies whether a set of payments sums to a settlement amount.
    Implementations will check:
        sum(payment.amount_paise) == settlement.amount_paise
    """

    def check_batch(
        self,
        payments: list[NormalizedPayment],
        settlement: NormalizedSettlement,
    ) -> ReconciliationResult: ...


class DeterministicReconciliationEngine(Protocol):
    """Contract for the deterministic reconciliation engine.

    Accepts normalized source records and returns structured
    reconciliation results. All decisions are deterministic.
    No AI. No ground truth access. Source data from data/ only.
    """

    def reconcile(
        self,
        payments: list[NormalizedPayment],
        settlements: list[NormalizedSettlement],
        bank_entries: list[NormalizedBankEntry],
    ) -> list[ReconciliationResult]: ...
