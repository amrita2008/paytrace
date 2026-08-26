#!/usr/bin/env python3
"""PayTrace Synthetic Financial Data Generator.

Produces a deterministic, reproducible synthetic dataset:
- 55 payment gateway records
- 18 settlement records
- 22 bank/ledger records
- Ground truth answer key (evaluation/ground_truth.json)

Fixed seed for reproducibility. All data is synthetic.
"""

from __future__ import annotations

import json
import random
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

SEED = 20260826
DATA_DIR = Path("data")
EVAL_DIR = Path("evaluation")
NUM_PAYMENTS = 55
NUM_SETTLEMENTS = 18
NUM_BANK_ENTRIES = 22
BASE_DATE = datetime(2026, 8, 20, 8, 0, 0, tzinfo=timezone.utc)
FEE_PCT = 0.02


def ts(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def calc_fee(amount: int) -> int:
    return max(100, round(amount * FEE_PCT))


@dataclass
class Payment:
    payment_id: str
    order_id: str
    customer_ref: str
    amount_paise: int
    currency: str
    payment_timestamp: str
    payment_status: str
    gateway_reference: str


@dataclass
class Settlement:
    settlement_id: str
    settlement_timestamp: str
    amount_paise: int
    currency: str
    fee_paise: int
    net_amount_paise: int
    payment_refs: list[str]
    settlement_status: str
    gateway_settlement_reference: str
    is_known_exception: bool = False


@dataclass
class BankEntry:
    bank_entry_id: str
    entry_timestamp: str
    amount_paise: int
    currency: str
    reference: str
    entry_type: str
    ledger_status: str


@dataclass
class MatchGroup:
    group_id: str
    payment_ids: list[str]
    settlement_ids: list[str]
    bank_entry_ids: list[str]
    expected_status: str
    exception_type: str | None
    explanation: str


class Generator:
    def __init__(self, seed: int = SEED) -> None:
        self.rng = random.Random(seed)
        self.payments: list[Payment] = []
        self.settlements: list[Settlement] = []
        self.bank_entries: list[BankEntry] = []
        self.groups: list[MatchGroup] = []
        self._pi = 0
        self._si = 0
        self._bi = 0
        self._gi = 0

    def _next_pid(self) -> str:
        self._pi += 1
        return f"PAY-{self._pi:04d}"

    def _next_sid(self) -> str:
        self._si += 1
        return f"SETL-{self._si:04d}"

    def _next_bid(self) -> str:
        self._bi += 1
        return f"BANK-{self._bi:04d}"

    def _next_gid(self) -> str:
        self._gi += 1
        return f"G-{self._gi:04d}"

    def add_payment(self, amt: int, status: str = "captured",
                    days_offset: int = 0) -> Payment:
        pid = self._next_pid()
        p = Payment(
            payment_id=pid,
            order_id=f"ORD-{self._pi:04d}",
            customer_ref=f"CUST-{self._pi:04d}",
            amount_paise=amt,
            currency="INR",
            payment_timestamp=ts(BASE_DATE + timedelta(days=days_offset)),
            payment_status=status,
            gateway_reference=f"GW-{self._pi:04d}",
        )
        self.payments.append(p)
        return p

    def add_settlement(self, refs: list[str], gross: int,
                       days_offset: int = 0,
                       amount_override: int | None = None,
                       is_known_exception: bool = False) -> Settlement:
        sid = self._next_sid()
        reported = amount_override if amount_override is not None else gross
        fee = calc_fee(reported)
        s = Settlement(
            settlement_id=sid,
            settlement_timestamp=ts(BASE_DATE + timedelta(days=days_offset)),
            amount_paise=reported,
            currency="INR",
            fee_paise=fee,
            net_amount_paise=reported - fee,
            payment_refs=refs,
            settlement_status="settled",
            gateway_settlement_reference=f"GWSETL-{self._si:04d}",
            is_known_exception=is_known_exception,
        )
        self.settlements.append(s)
        return s

    def add_bank(self, ref: str, amt: int,
                 days_offset: int = 0) -> BankEntry:
        b = BankEntry(
            bank_entry_id=self._next_bid(),
            entry_timestamp=ts(BASE_DATE + timedelta(days=days_offset)),
            amount_paise=amt,
            currency="INR",
            reference=ref,
            entry_type="credit",
            ledger_status="cleared",
        )
        self.bank_entries.append(b)
        return b

    def add_group(self, pays: list[str], setls: list[str],
                  banks: list[str], status: str,
                  exc: str | None, explanation: str) -> None:
        self.groups.append(MatchGroup(
            self._next_gid(), pays, setls, banks, status, exc, explanation
        ))

    # ------------------------------------------------------------------
    # Scenario builders
    # ------------------------------------------------------------------

    def _build_batch_settlements(self) -> None:
        """8 batch settlements covering 2-4 payments each.

        Payments: 4+3+4+3+3+3+3+3 = 26
        Settlements: 8
        Bank entries: 8
        """
        batch_specs = [
            ([15000, 25000, 8000, 12000], 0),
            ([30000, 20000, 10000], 1),
            ([5000, 12000, 8000, 22000], 2),
            ([18000, 7000, 8500], 3),
            ([14000, 13000, 6000], 4),
            ([9000, 22000, 23000], 5),
            ([16000, 11000, 18000], 6),
            ([6000, 15000, 9000], 7),
        ]
        for amounts, d in batch_specs:
            pays = [self.add_payment(a, days_offset=d) for a in amounts]
            gross = sum(amounts)
            s = self.add_settlement(
                [p.payment_id for p in pays], gross, days_offset=d + 1
            )
            fee = calc_fee(gross)
            b = self.add_bank(s.settlement_id, gross - fee, days_offset=d + 2)
            self.add_group(
                [p.payment_id for p in pays],
                [s.settlement_id],
                [b.bank_entry_id],
                "MATCHED", None,
                f"Clean batch: {len(pays)} payments INR {gross / 100:.2f}"
                f" -> {s.settlement_id} -> {b.bank_entry_id}",
            )

    def _build_clean_singles(self) -> None:
        """2 clean single-payment settlements.

        Payments: 2 (total 28)
        Settlements: 2 (total 10)
        Bank entries: 2 (total 10)
        """
        for amt, d in [(8500, 8), (12500, 9)]:
            p = self.add_payment(amt, days_offset=d)
            s = self.add_settlement(
                [p.payment_id], amt, days_offset=d + 1
            )
            fee = calc_fee(amt)
            b = self.add_bank(s.settlement_id, amt - fee, days_offset=d + 2)
            self.add_group(
                [p.payment_id], [s.settlement_id], [b.bank_entry_id],
                "MATCHED", None,
                f"Clean single: {p.payment_id} INR {amt / 100:.2f}"
                f" -> {s.settlement_id} -> {b.bank_entry_id}",
            )

    def _build_amount_mismatches(self) -> None:
        """3 amount-mismatch cases.

        Payments: 3 (total 33)
        Settlements: 3 (total 15)
        Bank entries: 3 (total 15)
        """
        for pay_amt, setl_amt, d in [
            (10000, 9000, 12),
            (15000, 14500, 13),
            (12000, 11000, 14),
        ]:
            p = self.add_payment(pay_amt, days_offset=d)
            s = self.add_settlement(
                [p.payment_id], setl_amt, days_offset=d + 1,
                is_known_exception=True,
            )
            fee = calc_fee(setl_amt)
            b = self.add_bank(
                s.settlement_id, setl_amt - fee, days_offset=d + 2
            )
            diff = abs(pay_amt - setl_amt)
            self.add_group(
                [p.payment_id], [s.settlement_id], [b.bank_entry_id],
                "MISMATCHED", "AMOUNT_MISMATCH",
                f"Payment {p.payment_id} INR {pay_amt / 100:.2f} vs "
                f"settlement {s.settlement_id} INR {setl_amt / 100:.2f} "
                f"(diff INR {diff / 100:.2f})",
            )

    def _build_timing_mismatches(self) -> None:
        """3 timing-mismatch cases (settlement delayed 2-5 days).

        Payments: 3 (total 36)
        Settlements: 3 (total 18)
        Bank entries: 3 (total 18)
        """
        for amt, gap_days, base_d in [
            (8000, 3, 15),
            (13000, 4, 16),
            (7000, 2, 17),
        ]:
            p = self.add_payment(amt, days_offset=base_d)
            setl_day = base_d + gap_days
            s = self.add_settlement(
                [p.payment_id], amt, days_offset=setl_day
            )
            fee = calc_fee(amt)
            b = self.add_bank(
                s.settlement_id, amt - fee, days_offset=setl_day + 1
            )
            self.add_group(
                [p.payment_id], [s.settlement_id], [b.bank_entry_id],
                "MISMATCHED", "TIMING_MISMATCH",
                f"Payment {p.payment_id} day {base_d} vs "
                f"settlement {s.settlement_id} day {setl_day} "
                f"({gap_days}d gap)",
            )

    def _build_missing_settlements(self) -> None:
        """4 payments with no settlement.

        Payments: 4 (total 40)
        Settlements: 0 (total 18)
        Bank entries: 0 (total 18)
        """
        for amt, d in [(10000, 19), (15000, 20), (8000, 21), (20000, 22)]:
            p = self.add_payment(amt, days_offset=d)
            self.add_group(
                [p.payment_id], [], [],
                "MISSING", "MISSING_SETTLEMENT",
                f"Payment {p.payment_id} INR {amt / 100:.2f} has no settlement",
            )

    def _build_duplicates(self) -> None:
        """3 pairs of duplicate payments (6 records total).

        Same order_id, same amount, same timestamp.
        Payments: 6 (total 46)
        Settlements: 0 (total 18)
        Bank entries: 0 (total 18)
        """
        for amt, d in [(11000, 23), (9500, 24), (14500, 25)]:
            p1 = self.add_payment(amt, days_offset=d)
            pid2 = self._next_pid()
            p2 = Payment(
                payment_id=pid2,
                order_id=p1.order_id,
                customer_ref=f"CUST-{self._pi:04d}",
                amount_paise=amt,
                currency="INR",
                payment_timestamp=p1.payment_timestamp,
                payment_status="captured",
                gateway_reference=f"GW-{self._pi:04d}",
            )
            self.payments.append(p2)
            self.add_group(
                [p1.payment_id, p2.payment_id], [], [],
                "DUPLICATE", "DUPLICATE",
                f"Duplicates {p1.payment_id}+{p2.payment_id} "
                f"(order {p1.order_id}, INR {amt / 100:.2f})",
            )

    def _build_ambiguous(self) -> None:
        """2 ambiguous scenarios (4 payments, 2 settlements).

        Each scenario has 2 payment candidates with identical amount
        and timestamp but different order_ids. The settlement has
        empty payment_refs because the true payment is unknown.
        The ground-truth MatchGroup lists both candidates.

        Payments: 4 (total 50)
        Settlements: 2 (total 18)
        Bank entries: 0 (total 18)
        """
        for amt, d in [(10000, 26), (16000, 27)]:
            # Two candidate payments with same amount and timestamp
            p1 = self.add_payment(amt, days_offset=d)
            pid2 = self._next_pid()
            p2 = Payment(
                payment_id=pid2,
                order_id=f"ORD-{self._pi:04d}",
                customer_ref=f"CUST-{self._pi:04d}",
                amount_paise=amt,
                currency="INR",
                payment_timestamp=p1.payment_timestamp,
                payment_status="captured",
                gateway_reference=f"GW-{self._pi:04d}",
            )
            self.payments.append(p2)
            # Settlement with empty payment_refs — the true
            # payment relationship is intentionally unknown.
            s = self.add_settlement(
                [], amt, days_offset=d + 1
            )
            self.add_group(
                [p1.payment_id, p2.payment_id],
                [s.settlement_id], [],
                "AMBIGUOUS", "AMBIGUOUS",
                f"Ambiguous: {p1.payment_id}+{p2.payment_id} vs "
                f"{s.settlement_id} (same amount INR {amt / 100:.2f}, "
                f"same timestamp, different order_ids)",
            )

    def _build_failed_refunded(self) -> None:
        """7 failed/refunded payments with no settlement expected.

        Payments: 7 (total 55)
        Settlements: 0 (total 18)
        Bank entries: 0 (total 18)
        """
        for amt, status, d in [
            (5000, "failed", 28),
            (3000, "failed", 29),
            (7500, "refunded", 30),
            (4000, "failed", 31),
            (6500, "refunded", 32),
            (2500, "failed", 33),
            (8500, "refunded", 34),
        ]:
            p = self.add_payment(amt, status=status, days_offset=d)
            self.add_group(
                [p.payment_id], [], [],
                "EXCLUDED", "FAILED_OR_REFUNDED",
                f"Payment {p.payment_id} INR {amt / 100:.2f} "
                f"status={status}, no settlement expected",
            )

    def _build_orphan_bank_entries(self) -> None:
        """4 bank entries with no matching settlement.

        Payments: 0 (total 55)
        Settlements: 0 (total 18)
        Bank entries: 6 more (total 22 = 8+2+3+3+6)

        None of these reference any existing settlement.
        """
        # 1. Interest credit from bank (no settlement counterpart)
        b1 = self.add_bank("INT-20260820-001", 3500, days_offset=5)
        self.add_group(
            [], [], [b1.bank_entry_id],
            "UNMATCHED", "ORPHAN_BANK_ENTRY",
            f"Bank {b1.bank_entry_id} (INR 35.00) - "
            f"interest credit, no matching settlement",
        )

        # 2. Unknown incoming transfer (no settlement counterpart)
        b2 = self.add_bank("XFER-20260821-001", 2500, days_offset=8)
        self.add_group(
            [], [], [b2.bank_entry_id],
            "UNMATCHED", "ORPHAN_BANK_ENTRY",
            f"Bank {b2.bank_entry_id} (INR 25.00) - "
            f"unknown incoming transfer",
        )

        # 3. Bank entry with no corresponding settlement (deposit)
        b3 = self.add_bank("DEP-20260822-001", 12000, days_offset=10)
        self.add_group(
            [], [], [b3.bank_entry_id],
            "UNMATCHED", "ORPHAN_BANK_ENTRY",
            f"Bank {b3.bank_entry_id} (INR 120.00) - "
            f"deposit with no matching settlement",
        )

        # 4. Unreconciled bank adjustment
        b4 = self.add_bank("ADJ-20260823-001", 750, days_offset=12)
        self.add_group(
            [], [], [b4.bank_entry_id],
            "UNMATCHED", "ORPHAN_BANK_ENTRY",
            f"Bank {b4.bank_entry_id} (INR 7.50) - "
            f"bank adjustment with no settlement",
        )

        # 5. Reversed transaction (debit without settlement)
        b5 = self.add_bank("REV-20260824-001", 4200, days_offset=14)
        self.add_group(
            [], [], [b5.bank_entry_id],
            "UNMATCHED", "ORPHAN_BANK_ENTRY",
            f"Bank {b5.bank_entry_id} (INR 42.00) - "
            f"reversed transaction with no settlement",
        )

        # 6. Merchant payout adjustment
        b6 = self.add_bank("PAYADJ-20260825-001", 1800, days_offset=16)
        self.add_group(
            [], [], [b6.bank_entry_id],
            "UNMATCHED", "ORPHAN_BANK_ENTRY",
            f"Bank {b6.bank_entry_id} (INR 18.00) - "
            f"merchant payout adjustment with no settlement",
        )

    # ------------------------------------------------------------------
    # Main generate / validate / write
    # ------------------------------------------------------------------

    def generate(self) -> None:
        """Build all 95 records with exact count tracking.

        Final tally:
        - 8 batch:        26 pay,  8 setl,  8 bank
        - 2 clean single:  2 pay,  2 setl,  2 bank
        - 3 amount:        3 pay,  3 setl,  3 bank
        - 3 timing:        3 pay,  3 setl,  3 bank
        - 2 ambiguous:     4 pay,  2 setl,  0 bank
        - 4 missing:       4 pay,  0 setl,  0 bank
        - 3 dup pairs:     6 pay,  0 setl,  0 bank
        - 7 failed:        7 pay,  0 setl,  0 bank
        - orphan banks:    0 pay,  0 setl,  6 bank
                             ----  ----  ----
        Total:            55 pay, 18 setl, 22 bank
        """
        self._build_batch_settlements()
        self._build_clean_singles()
        self._build_amount_mismatches()
        self._build_timing_mismatches()
        self._build_ambiguous()
        self._build_missing_settlements()
        self._build_duplicates()
        self._build_failed_refunded()
        self._build_orphan_bank_entries()

    def validate(self) -> list[str]:
        errors: list[str] = []
        if len(self.payments) != NUM_PAYMENTS:
            errors.append(
                f"Expected {NUM_PAYMENTS} payments, got {len(self.payments)}"
            )
        if len(self.settlements) != NUM_SETTLEMENTS:
            errors.append(
                f"Expected {NUM_SETTLEMENTS} settlements, "
                f"got {len(self.settlements)}"
            )
        if len(self.bank_entries) != NUM_BANK_ENTRIES:
            errors.append(
                f"Expected {NUM_BANK_ENTRIES} bank entries, "
                f"got {len(self.bank_entries)}"
            )

        pay_ids = [p.payment_id for p in self.payments]
        if len(pay_ids) != len(set(pay_ids)):
            errors.append("Duplicate payment IDs found")
        setl_ids = [s.settlement_id for s in self.settlements]
        if len(setl_ids) != len(set(setl_ids)):
            errors.append("Duplicate settlement IDs found")
        bank_ids = [b.bank_entry_id for b in self.bank_entries]
        if len(bank_ids) != len(set(bank_ids)):
            errors.append("Duplicate bank entry IDs found")

        all_pay = set(pay_ids)
        all_setl = set(setl_ids)
        all_bank = set(bank_ids)
        for g in self.groups:
            for pid in g.payment_ids:
                if pid not in all_pay:
                    errors.append(
                        f"Group {g.group_id} unknown payment: {pid}"
                    )
            for sid in g.settlement_ids:
                if sid not in all_setl:
                    errors.append(
                        f"Group {g.group_id} unknown settlement: {sid}"
                    )
            for bid in g.bank_entry_ids:
                if bid not in all_bank:
                    errors.append(
                        f"Group {g.group_id} unknown bank: {bid}"
                    )

        # Check for duplicate source-record membership across groups.
        # A record should not appear in multiple groups unless it is
        # intentionally a DUPLICATE scenario (both candidates share the
        # same group).
        pay_membership: dict[str, list[str]] = {}
        setl_membership: dict[str, list[str]] = {}
        bank_membership: dict[str, list[str]] = {}
        for g in self.groups:
            for pid in g.payment_ids:
                pay_membership.setdefault(pid, []).append(g.group_id)
            for sid in g.settlement_ids:
                setl_membership.setdefault(sid, []).append(g.group_id)
            for bid in g.bank_entry_ids:
                bank_membership.setdefault(bid, []).append(g.group_id)
        for pid, gids in pay_membership.items():
            if len(gids) > 1:
                errors.append(
                    f"Payment {pid} in multiple groups: {gids}"
                )
        for sid, gids in setl_membership.items():
            if len(gids) > 1:
                errors.append(
                    f"Settlement {sid} in multiple groups: {gids}"
                )
        for bid, gids in bank_membership.items():
            if len(gids) > 1:
                errors.append(
                    f"Bank {bid} in multiple groups: {gids}"
                )

        for p in self.payments:
            if p.amount_paise <= 0:
                errors.append(f"Payment {p.payment_id}: non-positive amount")
        for s in self.settlements:
            if s.amount_paise <= 0:
                errors.append(f"Settlement {s.settlement_id}: non-positive amount")
        for b in self.bank_entries:
            if b.amount_paise <= 0:
                errors.append(f"Bank {b.bank_entry_id}: non-positive amount")

        for s in self.settlements:
            expected_net = s.amount_paise - s.fee_paise
            if s.net_amount_paise != expected_net:
                errors.append(
                    f"Settlement {s.settlement_id}: net {s.net_amount_paise} "
                    f"!= amount {s.amount_paise} - fee {s.fee_paise}"
                )

        # Validate payment reference arithmetic.
        # For settlements with non-empty payment_refs, the sum of
        # referenced payments amounts must equal settlement amount.
        pay_map = {p.payment_id: p for p in self.payments}
        for s in self.settlements:
            if s.payment_refs and not s.is_known_exception:
                ref_sum = sum(
                    pay_map[ref].amount_paise for ref in s.payment_refs
                )
                if ref_sum != s.amount_paise:
                    errors.append(
                        f"Settlement {s.settlement_id}: sum of referenced "
                        f"payments ({ref_sum}) != amount ({s.amount_paise})"
                    )

        return errors

    def _compute_rates(self) -> tuple[float, float]:
        """Compute match rates using unique record IDs.

        Record-level: count of unique source records appearing in any
        MATCHED group, divided by total records.

        Group-level: number of MATCHED groups divided by total groups.
        """
        total_records = (
            len(self.payments) + len(self.settlements) + len(self.bank_entries)
        )
        # Collect unique record IDs from MATCHED groups
        matched_pay_ids: set[str] = set()
        matched_setl_ids: set[str] = set()
        matched_bank_ids: set[str] = set()
        for g in self.groups:
            if g.expected_status == "MATCHED":
                matched_pay_ids.update(g.payment_ids)
                matched_setl_ids.update(g.settlement_ids)
                matched_bank_ids.update(g.bank_entry_ids)
        matched_records = (
            len(matched_pay_ids) + len(matched_setl_ids) + len(matched_bank_ids)
        )
        rec_rate = matched_records / total_records if total_records > 0 else 0.0
        grp_matched = sum(
            1 for g in self.groups if g.expected_status == "MATCHED"
        )
        grp_rate = grp_matched / len(self.groups) if self.groups else 0.0
        return rec_rate, grp_rate

    def write_output(self) -> dict[str, str]:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        EVAL_DIR.mkdir(parents=True, exist_ok=True)

        files: dict[str, str] = {}

        with open(DATA_DIR / "payment_gateway.json", "w") as f:
            json.dump([asdict(p) for p in self.payments], f, indent=2)
        files["data/payment_gateway.json"] = f"{len(self.payments)} records"

        with open(DATA_DIR / "settlements.json", "w") as f:
            json.dump([asdict(s) for s in self.settlements], f, indent=2)
        files["data/settlements.json"] = f"{len(self.settlements)} records"

        with open(DATA_DIR / "bank_ledger.json", "w") as f:
            json.dump([asdict(b) for b in self.bank_entries], f, indent=2)
        files["data/bank_ledger.json"] = f"{len(self.bank_entries)} records"

        rr, gr = self._compute_rates()
        gt = {
            "seed": SEED,
            "record_counts": {
                "payments": len(self.payments),
                "settlements": len(self.settlements),
                "bank_entries": len(self.bank_entries),
            },
            "match_groups": [asdict(g) for g in self.groups],
            "expected_match_rate_record_level": round(rr, 4),
            "expected_match_rate_group_level": round(gr, 4),
        }
        with open(EVAL_DIR / "ground_truth.json", "w") as f:
            json.dump(gt, f, indent=2)
        files["evaluation/ground_truth.json"] = f"{len(self.groups)} groups"

        return files

    def run(self) -> dict[str, str]:
        self.generate()
        errors = self.validate()
        if errors:
            print("VALIDATION ERRORS:", file=sys.stderr)
            for e in errors:
                print(f"  - {e}", file=sys.stderr)
            sys.exit(1)

        files = self.write_output()
        rr, gr = self._compute_rates()

        print(f"Seed: {SEED}")
        print(f"Payments:     {len(self.payments)}")
        print(f"Settlements:  {len(self.settlements)}")
        print(f"Bank entries: {len(self.bank_entries)}")
        print(f"Match groups: {len(self.groups)}")
        print(f"Expected record-level match rate: {rr:.2%}")
        print(f"Expected group-level match rate:   {gr:.2%}")

        print("\nException breakdown:")
        for exc, cnt in sorted(
            Counter(
                g.exception_type or "None (MATCHED)" for g in self.groups
            ).items()
        ):
            print(f"  {exc}: {cnt}")

        print("\nOutput files:")
        for path, info in files.items():
            print(f"  {path}: {info}")

        return files


if __name__ == "__main__":
    gen = Generator()
    gen.run()
