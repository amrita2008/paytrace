"""Tests for the synthetic data generator."""

import json
from collections import defaultdict
from pathlib import Path

import pytest

from scripts.generate_synthetic_data import (
    Generator, SEED, NUM_PAYMENTS, NUM_SETTLEMENTS, NUM_BANK_ENTRIES
)


@pytest.fixture
def gen():
    g = Generator()
    g.generate()
    return g


@pytest.fixture
def gen2():
    g = Generator()
    g.generate()
    return g


def test_exact_payment_count(gen):
    assert len(gen.payments) == NUM_PAYMENTS


def test_exact_settlement_count(gen):
    assert len(gen.settlements) == NUM_SETTLEMENTS


def test_exact_bank_entry_count(gen):
    assert len(gen.bank_entries) == NUM_BANK_ENTRIES


def test_unique_payment_ids(gen):
    ids = [p.payment_id for p in gen.payments]
    assert len(ids) == len(set(ids))


def test_unique_settlement_ids(gen):
    ids = [s.settlement_id for s in gen.settlements]
    assert len(ids) == len(set(ids))


def test_unique_bank_entry_ids(gen):
    ids = [b.bank_entry_id for b in gen.bank_entries]
    assert len(ids) == len(set(ids))


def test_all_payment_amounts_positive(gen):
    for p in gen.payments:
        assert p.amount_paise > 0


def test_all_settlement_amounts_positive(gen):
    for s in gen.settlements:
        assert s.amount_paise > 0


def test_all_bank_amounts_positive(gen):
    for b in gen.bank_entries:
        assert b.amount_paise > 0


def test_settlement_arithmetic(gen):
    for s in gen.settlements:
        assert s.net_amount_paise == s.amount_paise - s.fee_paise


def test_all_currencies_inr(gen):
    for p in gen.payments:
        assert p.currency == "INR"
    for s in gen.settlements:
        assert s.currency == "INR"
    for b in gen.bank_entries:
        assert b.currency == "INR"


def test_group_references_valid(gen):
    all_pay = {p.payment_id for p in gen.payments}
    all_setl = {s.settlement_id for s in gen.settlements}
    all_bank = {b.bank_entry_id for b in gen.bank_entries}
    for g in gen.groups:
        for pid in g.payment_ids:
            assert pid in all_pay
        for sid in g.settlement_ids:
            assert sid in all_setl
        for bid in g.bank_entry_ids:
            assert bid in all_bank


def test_no_cross_group_membership(gen):
    pay_members = defaultdict(list)
    setl_members = defaultdict(list)
    bank_members = defaultdict(list)
    for g in gen.groups:
        for pid in g.payment_ids:
            pay_members[pid].append(g.group_id)
        for sid in g.settlement_ids:
            setl_members[sid].append(g.group_id)
        for bid in g.bank_entry_ids:
            bank_members[bid].append(g.group_id)
    for pid, gids in pay_members.items():
        assert len(gids) == 1, f"Payment {pid} in {gids}"
    for sid, gids in setl_members.items():
        assert len(gids) == 1, f"Settlement {sid} in {gids}"
    for bid, gids in bank_members.items():
        assert len(gids) == 1, f"Bank {bid} in {gids}"


def test_reproducibility(gen, gen2):
    for p1, p2 in zip(gen.payments, gen2.payments):
        assert p1.payment_id == p2.payment_id
        assert p1.amount_paise == p2.amount_paise
        assert p1.payment_timestamp == p2.payment_timestamp
    for s1, s2 in zip(gen.settlements, gen2.settlements):
        assert s1.settlement_id == s2.settlement_id
        assert s1.amount_paise == s2.amount_paise
    for b1, b2 in zip(gen.bank_entries, gen2.bank_entries):
        assert b1.bank_entry_id == b2.bank_entry_id
        assert b1.amount_paise == b2.amount_paise
    assert len(gen.groups) == len(gen2.groups)


def test_no_real_secrets(gen):
    suspicious = ["api_key", "sk_live", "sk_test", "password", "token"]
    all_data = json.dumps([
        {"payments": [p.__dict__ for p in gen.payments]},
        {"settlements": [s.__dict__ for s in gen.settlements]},
        {"bank": [b.__dict__ for b in gen.bank_entries]}
    ]).lower()
    for term in suspicious:
        assert term not in all_data


def test_validation_passes(gen):
    errors = gen.validate()
    assert errors == [], f"Validation errors: {errors}"


def test_ground_truth_only_in_evaluation():
    assert Path("evaluation/ground_truth.json").exists()
    assert not Path("data/ground_truth.json").exists()


def test_expected_exception_types(gen):
    exc_types = {g.exception_type for g in gen.groups}
    assert "MISSING_SETTLEMENT" in exc_types
    assert "AMOUNT_MISMATCH" in exc_types
    assert "TIMING_MISMATCH" in exc_types
    assert "DUPLICATE" in exc_types
    assert "AMBIGUOUS" in exc_types
    assert "FAILED_OR_REFUNDED" in exc_types
    assert "ORPHAN_BANK_ENTRY" in exc_types


def test_matched_groups_exist(gen):
    matched = [g for g in gen.groups if g.expected_status == "MATCHED"]
    assert len(matched) > 0


def test_ground_truth_structure():
    with open("evaluation/ground_truth.json") as f:
        gt = json.load(f)
    assert "seed" in gt
    assert "record_counts" in gt
    assert "match_groups" in gt
    assert "expected_match_rate_record_level" in gt
    assert "expected_match_rate_group_level" in gt
    assert gt["seed"] == SEED


def test_batch_settlements_exist(gen):
    multi = [s for s in gen.settlements if len(s.payment_refs) > 1]
    assert len(multi) >= 8


def test_failed_refunded_excluded(gen):
    for p in gen.payments:
        if p.payment_status in ("failed", "refunded"):
            groups_with = [
                g for g in gen.groups if p.payment_id in g.payment_ids
            ]
            assert len(groups_with) == 1
            assert groups_with[0].settlement_ids == []


def test_ambiguous_settlements_empty_payment_refs(gen):
    """Ambiguous settlements must have empty payment_refs."""
    amb_groups = [g for g in gen.groups if g.exception_type == "AMBIGUOUS"]
    pay_map = {p.payment_id: p for p in gen.payments}
    for g in amb_groups:
        assert len(g.settlement_ids) == 1
        setl = next(
            s for s in gen.settlements
            if s.settlement_id == g.settlement_ids[0]
        )
        assert setl.payment_refs == [], (
            f"Ambiguous {setl.settlement_id} must have empty payment_refs, "
            f"got {setl.payment_refs}"
        )


def test_ambiguous_groups_have_two_candidates(gen):
    """Each ambiguous group must list exactly two candidate payment IDs."""
    amb_groups = [g for g in gen.groups if g.exception_type == "AMBIGUOUS"]
    assert len(amb_groups) == 2
    for g in amb_groups:
        assert len(g.payment_ids) == 2, (
            f"Ambiguous {g.group_id} needs exactly 2 candidates, "
            f"got {len(g.payment_ids)}"
        )
        assert g.expected_status == "AMBIGUOUS"


def test_ambiguous_candidates_equal_signals(gen):
    """Ambiguous candidates must have identical amount and timestamp."""
    pay_map = {p.payment_id: p for p in gen.payments}
    amb_groups = [g for g in gen.groups if g.exception_type == "AMBIGUOUS"]
    for g in amb_groups:
        cands = [pay_map[pid] for pid in g.payment_ids]
        amounts = {c.amount_paise for c in cands}
        timestamps = {c.payment_timestamp for c in cands}
        assert len(amounts) == 1, (
            f"Ambiguous {g.group_id} candidates have different amounts: {amounts}"
        )
        assert len(timestamps) == 1, (
            f"Ambiguous {g.group_id} candidates have different timestamps: {timestamps}"
        )


def test_settlement_reference_arithmetic(gen):
    """Non-exception settlements must have sum(ref payments) == amount."""
    pay_map = {p.payment_id: p for p in gen.payments}
    for s in gen.settlements:
        if s.payment_refs and not s.is_known_exception:
            ref_sum = sum(pay_map[ref].amount_paise for ref in s.payment_refs)
            assert ref_sum == s.amount_paise, (
                f"{s.settlement_id}: sum(refs)={ref_sum} != amount={s.amount_paise}"
            )


def test_match_rate_unique_records(gen):
    rr, _gr = gen._compute_rates()
    total = len(gen.payments) + len(gen.settlements) + len(gen.bank_entries)
    matched_pay = set()
    matched_setl = set()
    matched_bank = set()
    for g in gen.groups:
        if g.expected_status == "MATCHED":
            matched_pay.update(g.payment_ids)
            matched_setl.update(g.settlement_ids)
            matched_bank.update(g.bank_entry_ids)
    expected = (len(matched_pay) + len(matched_setl) + len(matched_bank)) / total
    assert abs(rr - expected) < 1e-6


def test_orphan_bank_entries_no_settlement(gen):
    for g in gen.groups:
        if g.exception_type == "ORPHAN_BANK_ENTRY":
            assert g.settlement_ids == []
            assert len(g.bank_entry_ids) == 1


def test_exception_counts_match(gen):
    exc = defaultdict(int)
    for g in gen.groups:
        key = g.exception_type or "MATCHED"
        exc[key] += 1
    assert exc["MATCHED"] == 10
    assert exc["MISSING_SETTLEMENT"] == 4
    assert exc["AMOUNT_MISMATCH"] == 3
    assert exc["TIMING_MISMATCH"] == 3
    assert exc["DUPLICATE"] == 3
    assert exc["AMBIGUOUS"] == 2
    assert exc["FAILED_OR_REFUNDED"] == 7
    assert exc["ORPHAN_BANK_ENTRY"] == 6
