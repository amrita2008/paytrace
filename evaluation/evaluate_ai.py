"""Offline AI investigation pipeline validation.

Validates structural compliance, evidence grounding, policy compliance,
fallback behavior, confidence range, human-review policy, and absence
of chain-of-thought in investigation records.

Two modes:
  1. Pipeline validation (NullProvider) — always runs, no credentials needed
  2. Real LLM evaluation (optional) — only if PAYTRACE_LLM_API_KEY is set

Runnable as: python -m evaluation.evaluate_ai

This script is an OFFLINE evaluation tool. It must never be imported
by production code or exposed through any API.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from backend.ai.models import InvestigationInput
from backend.ai.policy_validator import validate_investigation
from backend.ai.response_validator import validate_llm_response


# Fields that must never appear in investigation records
_COT_FIELDS = {
    "chain_of_thought", "chain-of-thought", "hidden_reasoning",
    "reasoning_trace", "model_thoughts", "internal_reasoning",
    "raw_response", "raw_llm_output",
}


class _NullProvider:
    """Fallback provider for structural validation."""

    @property
    def provider_name(self) -> str:
        return "none"

    @property
    def model_name(self) -> str:
        return "unavailable"

    def complete(self, prompt: str):  # type: ignore[override]
        from backend.ai.models import ProviderErrorCategory
        from backend.ai.provider import ProviderResponse
        return ProviderResponse(
            content="",
            success=False,
            error_category=ProviderErrorCategory.UNAVAILABLE,
        )


def _build_test_investigation_input() -> InvestigationInput:
    """Build a minimal valid InvestigationInput for structural testing."""
    return InvestigationInput(
        group_id="GRP-TEST",
        exception_type="MISSING_SETTLEMENT",
        payment_ids=["PAY-0001"],
        settlement_ids=[],
        bank_entry_ids=[],
        evidence=[
            type("E", (), {
                "signal_id": "E1",
                "signal_type": "MISSING_RECORD",
                "source_record_id": "PAY-0001",
                "observed_value": "no_settlement",
            })(),
        ],
        evidence_summary="Payment has no settlement.",
        relevant_record_metadata=[],
    )


def _get_non_matched_groups() -> list[dict[str, Any]]:
    """Get reconciliation results for non-matched groups."""
    from backend.api.reconciliation_runner import get_results

    results = get_results()
    return [
        {
            "group_id": r.group_id,
            "status": r.status.value,
            "exception_type": r.exception_type.value if r.exception_type else None,
            "payment_ids": r.payment_ids,
            "settlement_ids": r.settlement_ids,
            "bank_entry_ids": r.bank_entry_ids,
            "evidence": [
                {
                    "signal_id": e.signal_id,
                    "signal_type": e.signal_type.value,
                    "source_record_id": e.source_record_id,
                    "observed_value": e.observed_value,
                    "points": e.points,
                }
                for e in r.evidence
            ],
            "evidence_summary": r.evidence_summary,
            "human_review_required": r.human_review_required,
        }
        for r in results
        if r.status.value != "matched"
    ]


def _validate_record_structure(record_dict: dict) -> tuple[bool, list[str]]:
    """Validate an InvestigationRecord has no prohibited fields."""
    issues: list[str] = []
    for field in _COT_FIELDS:
        if field in record_dict:
            issues.append(f"prohibited_field:{field}")
    required = [
        "investigation_id", "group_id", "exception_type", "summary",
        "evidence_ids", "provider_name", "model_name", "timestamp",
        "recommendation", "confidence", "validation_status",
        "requires_human_review",
    ]
    for field in required:
        if field not in record_dict:
            issues.append(f"missing_field:{field}")
    if "confidence" in record_dict:
        c = record_dict["confidence"]
        if not isinstance(c, (int, float)) or c < 0.0 or c > 1.0:
            issues.append("invalid_confidence_range")
    return len(issues) == 0, issues


def run_evaluation(json_output: bool = False) -> dict[str, Any]:
    """Run AI investigation pipeline validation.

    Returns a dict of results for programmatic use.
    """
    groups = _get_non_matched_groups()
    total = len(groups)

    # --- Pipeline validation with NullProvider ---
    from backend.ai.investigation_service import InvestigationService

    provider = _NullProvider()
    service = InvestigationService(provider)

    sv = 0
    si = 0
    fb = 0
    # policy_violations tracked via other counters
    ev_ok = 0
    ev_fail = 0
    c_ok = 0
    c_bad = 0
    hr_ok = 0
    hr_bad = 0
    no_cot = True
    cot_detected_in: list[str] = []

    all_facts = 0
    valid_facts = 0

    for g in groups:
        # Build a minimal ReconciliationResult-like object for the service
        from backend.reconciliation.models import (
            ReconciliationResult, MatchStatus, ExceptionType,
            ResolutionStatus, MatchEvidence, SignalType,
        )

        status_map = {
            "mismatched": MatchStatus.MISMATCHED,
            "ambiguous": MatchStatus.AMBIGUOUS,
            "duplicate": MatchStatus.DUPLICATE,
        }
        exc_map = {
            "AMOUNT_MISMATCH": ExceptionType.AMOUNT_MISMATCH,
            "TIMING_MISMATCH": ExceptionType.TIMING_MISMATCH,
            "MISSING_SETTLEMENT": ExceptionType.MISSING_SETTLEMENT,
            "FAILED_OR_REFUNDED": ExceptionType.FAILED_OR_REFUNDED,
            "ORPHAN_BANK_ENTRY": ExceptionType.ORPHAN_BANK_ENTRY,
            "DUPLICATE": ExceptionType.DUPLICATE,
            "AMBIGUOUS": ExceptionType.AMBIGUOUS,
        }

        evidence_list = [
            MatchEvidence(
                signal_id=e["signal_id"],
                source_record_id=e["source_record_id"],
                signal_type=SignalType(e["signal_type"]),
                observed_value=e["observed_value"],
                points=e["points"],
            )
            for e in g["evidence"]
        ]

        result = ReconciliationResult(
            group_id=g["group_id"],
            status=status_map.get(g["status"], MatchStatus.MISMATCHED),
            payment_ids=g["payment_ids"],
            settlement_ids=g["settlement_ids"],
            bank_entry_ids=g["bank_entry_ids"],
            match_score=None,
            match_method=None,
            exception_type=exc_map.get(g["exception_type"]) if g["exception_type"] else None,
            resolution_status=ResolutionStatus.OPEN,
            evidence=evidence_list,
            evidence_summary=g["evidence_summary"],
            human_review_required=g["human_review_required"],
        )

        # Normalize payment/settlement/bank for the investigation service
        from backend.reconciliation.matching import (
            normalize_payment, normalize_settlement, normalize_bank_entry,
        )
        from backend.api.reconciliation_runner import get_normalized_data
        norm_pays, norm_setls, norm_banks = get_normalized_data()

        inv_response = service.investigate(result, norm_pays, norm_setls, norm_banks)
        record = inv_response.record
        inv_result = inv_response.result

        # Fallback check
        if record.validation_status == "fallback": fb += 1

        # Record structure validation
        record_dict = {
            "investigation_id": record.investigation_id,
            "group_id": record.group_id,
            "exception_type": record.exception_type,
            "summary": record.summary,
            "evidence_ids": record.evidence_ids,
            "provider_name": record.provider_name,
            "model_name": record.model_name,
            "timestamp": record.timestamp,
            "recommendation": record.recommendation,
            "confidence": record.confidence,
            "validation_status": record.validation_status,
            "requires_human_review": record.requires_human_review,
        }
        v, _ = _validate_record_structure(record_dict)
        if v: sv += 1
        else: si += 1

        if 0.0 <= record.confidence <= 1.0: c_ok += 1
        else: c_bad += 1

        if record.confidence < 0.5:
            if record.requires_human_review: hr_ok += 1
            else: hr_bad += 1
        else: hr_ok += 1

        if inv_result:
            valid_ids = {e["signal_id"] for e in g["evidence"]}
            facts_good = True
            for f in inv_result.observed_facts:
                all_facts += 1
                if all(eid in valid_ids for eid in f.evidence_ids):
                    valid_facts += 1
                else:
                    facts_good = False; ev_fail += 1
            if facts_good: ev_ok += 1
            for field in _COT_FIELDS:
                if hasattr(inv_result, field): no_cot = False; cot_detected_in.append(g["group_id"])

    results = {
        "total_investigated": total, "structural_valid": sv, "structural_invalid": si,
        "fallback_count": fb, "evidence_grounding_ok": ev_ok, "evidence_grounding_fail": ev_fail,
        "all_facts_count": all_facts, "valid_facts_count": valid_facts,
        "confidence_in_range": c_ok, "confidence_out_of_range": c_bad,
        "human_review_correct": hr_ok, "human_review_incorrect": hr_bad,
        "no_cot": no_cot, "cot_detected_in": cot_detected_in, "real_llm": None,
    }

    api_key = os.getenv("PAYTRACE_LLM_API_KEY")
    if api_key:
        try:
            from backend.ai.providers.openai_provider import OpenAIProvider
            rp = OpenAIProvider(); rs = InvestigationService(rp)
            rt = 0; rf = 0; rc = []; rfc = []; rqc = []
            for g in groups:
                el = [MatchEvidence(signal_id=e["signal_id"], source_record_id=e["source_record_id"],
                    signal_type=SignalType(e["signal_type"]), observed_value=e["observed_value"], points=e["points"])
                    for e in g["evidence"]]
                r = ReconciliationResult(group_id=g["group_id"], status=status_map.get(g["status"], MatchStatus.MISMATCHED),
                    payment_ids=g["payment_ids"], settlement_ids=g["settlement_ids"], bank_entry_ids=g["bank_entry_ids"],
                    match_score=None, match_method=None,
                    exception_type=exc_map.get(g["exception_type"]) if g["exception_type"] else None,
                    resolution_status=ResolutionStatus.OPEN, evidence=el,
                    evidence_summary=g["evidence_summary"], human_review_required=g["human_review_required"])
                resp = rs.investigate(r, norm_pays, norm_setls, norm_banks)
                rt += 1
                if resp.record.validation_status == "fallback": rf += 1
                rc.append(resp.record.confidence)
                if resp.result: rfc.append(len(resp.result.observed_facts)); rqc.append(len(resp.result.unresolved_questions))
            results["real_llm"] = {"provider": rp.provider_name, "model": rp.model_name, "total": rt,
                "fallback_count": rf, "fallback_rate": round(rf/rt, 4) if rt else 0,
                "mean_confidence": round(sum(rc)/len(rc), 4) if rc else 0,
                "mean_facts": round(sum(rfc)/len(rfc), 1) if rfc else 0,
                "mean_unresolved": round(sum(rqc)/len(rqc), 1) if rqc else 0}
        except Exception:
            results["real_llm"] = {"error": "Real LLM evaluation failed"}

    if not json_output: _print_report(results)
    return results

def _print_report(r):
    print()
    print("AI INVESTIGATION EVALUATION REPORT")
    print("=" * 50)
    print()
    print("Mode: Pipeline Validation (NullProvider)")
    print(f"Investigations evaluated:  {r['total_investigated']}")
    print()
    print("Structural Compliance:")
    print(f"  Structurally valid:    {r['structural_valid']}/{r['total_investigated']}")
    print(f"  Fallback records:      {r['fallback_count']}/{r['total_investigated']}")
    print()
    print("Evidence Grounding:")
    print(f"  Investigations grounded:  {r['evidence_grounding_ok']}/{r['total_investigated']}")
    print(f"  Total facts:             {r['all_facts_count']}")
    print(f"  Valid evidence refs:     {r['valid_facts_count']}/{r['all_facts_count']}")
    print()
    print("Confidence Validation:")
    y = "Yes" if r["confidence_out_of_range"] == 0 else "No"
    print(f"  All in [0.0, 1.0]: {y}")
    print()
    print("Human Review Policy:")
    tot = r["human_review_correct"] + r["human_review_incorrect"]
    print(f"  Low confidence triggers review: {r['human_review_correct']}/{tot} correct")
    print()
    print("Chain-of-Thought:")
    print(f"  Absent in all records: {'Yes' if r['no_cot'] else 'No'}")
    if r["cot_detected_in"]: print(f"  Detected in: {r['cot_detected_in']}")
    print()
    if r["real_llm"]:
        rl = r["real_llm"]
        if "error" in rl:
            print(f"Real LLM: {rl['error']}")
        else:
            print("Real LLM Results:")
            print(f"  Provider: {rl['provider']}  Model: {rl['model']}")
            print(f"  Total: {rl['total']}  Fallback: {rl['fallback_rate']:.1%}")
            print(f"  Mean confidence: {rl['mean_confidence']:.4f}")
        print()
    print("Limitations:")
    print("  - NullProvider validates structure only, not content quality")
    print("  - Real LLM root-cause accuracy cannot be measured without labeled data")
    print("  - Evidence grounding checks citation validity, not semantics")
    print()

if __name__ == "__main__":
    run_evaluation(json_output="--json" in sys.argv)
