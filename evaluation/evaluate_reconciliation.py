"""Offline reconciliation evaluation.

Compares the deterministic reconciliation engine output against
the isolated ground truth. Groups are aligned by record content.

Runnable as: python -m evaluation.evaluate_reconciliation
"""
from __future__ import annotations
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

STATUS_NORMALIZE = {
    "MATCHED": "MATCHED", "MISMATCHED": "MISMATCHED",
    "MISSING": "MISMATCHED", "EXCLUDED": "MISMATCHED",
    "UNMATCHED": "MISMATCHED", "AMBIGUOUS": "AMBIGUOUS",
    "DUPLICATE": "DUPLICATE",
}
ENGINE_STATUS_MAP = {
    "matched": "MATCHED", "mismatched": "MISMATCHED",
    "ambiguous": "AMBIGUOUS", "duplicate": "DUPLICATE",
}

def _record_key(pids, sids, bids):
    return (tuple(sorted(pids)), tuple(sorted(sids)), tuple(sorted(bids)))

def _load_ground_truth(gt_path):
    with open(gt_path) as f:
        return json.load(f)

def _load_engine_results():
    from backend.api.reconciliation_runner import get_results
    results = get_results()
    return [{
        "group_id": r.group_id, "status": r.status.value,
        "payment_ids": r.payment_ids, "settlement_ids": r.settlement_ids,
        "bank_entry_ids": r.bank_entry_ids,
        "exception_type": r.exception_type.value if r.exception_type else None,
        "match_score": r.match_score, "evidence_count": len(r.evidence),
    } for r in results]

def _align_groups(gt_groups, engine_groups):
    engine_index = {}
    for eg in engine_groups:
        key = _record_key(eg["payment_ids"], eg["settlement_ids"], eg["bank_entry_ids"])
        engine_index[key] = eg
    aligned, gt_only, used = [], [], set()
    for gt_g in gt_groups:
        key = _record_key(gt_g["payment_ids"], gt_g["settlement_ids"], gt_g["bank_entry_ids"])
        if key in engine_index:
            aligned.append((gt_g, engine_index[key]))
            used.add(key)
        else:
            gt_only.append(gt_g)
    engine_only = [eg for eg in engine_groups
                   if _record_key(eg["payment_ids"], eg["settlement_ids"], eg["bank_entry_ids"]) not in used]
    return aligned, gt_only, engine_only

def _compute_precision_recall_f1(tp, fp, fn):
    p = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0.0
    return p, r, f1

def run_evaluation(gt_path=None, json_output=False):
    if gt_path is None:
        gt_path = Path("evaluation/ground_truth.json")
    gt_data = _load_ground_truth(gt_path)
    engine_groups = _load_engine_results()
    gt_groups = gt_data["match_groups"]
    aligned, gt_only, engine_only = _align_groups(gt_groups, engine_groups)

    status_correct = status_incorrect = exc_correct = exc_incorrect = 0
    status_details, exc_details = [], []
    all_classes = set()
    class_tp, class_fp, class_fn = Counter(), Counter(), Counter()

    for gt_g, eng_g in aligned:
        gt_sn = STATUS_NORMALIZE.get(gt_g["expected_status"], gt_g["expected_status"])
        en_sn = ENGINE_STATUS_MAP.get(eng_g["status"], eng_g["status"].upper())
        gt_exc = gt_g.get("exception_type")
        eng_exc = eng_g.get("exception_type")

        if gt_sn == en_sn:
            status_correct += 1
        else:
            status_incorrect += 1
            status_details.append({"gt_group": gt_g["group_id"], "gt_status": gt_g["expected_status"],
                "normalized_to": gt_sn, "engine_status": eng_g["status"], "engine_normalized": en_sn})

        if gt_exc == eng_exc:
            exc_correct += 1
        else:
            exc_incorrect += 1
            exc_details.append({"gt_group": gt_g["group_id"], "gt_exception": gt_exc,
                "engine_exception": eng_exc, "engine_group": eng_g["group_id"]})

        gt_class = gt_exc or "__matched__"
        eng_class = eng_exc or "__matched__"
        all_classes.update([gt_class, eng_class])
        if gt_class == eng_class:
            class_tp[gt_class] += 1
        else:
            class_fp[eng_class] += 1
            class_fn[gt_class] += 1

    total_records = sum(gt_data["record_counts"].values())
    matched_records = sum(
        len(eg["payment_ids"]) + len(eg["settlement_ids"]) + len(eg["bank_entry_ids"])
        for _, eg in aligned
        if ENGINE_STATUS_MAP.get(eg["status"], eg["status"].upper()) == "MATCHED"
    )

    aligned_total = len(aligned)
    class_metrics = {}
    for cls in sorted(all_classes - {"__matched__"}):
        p, r, f1 = _compute_precision_recall_f1(class_tp[cls], class_fp[cls], class_fn[cls])
        class_metrics[cls] = {"precision": round(p, 4), "recall": round(r, 4),
                              "f1": round(f1, 4), "support": class_tp[cls] + class_fn[cls]}

    results = {
        "ground_truth_groups": len(gt_groups), "engine_groups": len(engine_groups),
        "aligned_groups": aligned_total, "gt_only_groups": len(gt_only),
        "engine_only_groups": len(engine_only),
        "status_correct": status_correct, "status_incorrect": status_incorrect,
        "status_accuracy": round(status_correct / aligned_total, 4) if aligned_total else 0,
        "status_mismatches": status_details,
        "exception_correct": exc_correct, "exception_incorrect": exc_incorrect,
        "exception_accuracy": round(exc_correct / aligned_total, 4) if aligned_total else 0,
        "exception_mismatches": exc_details, "class_metrics": class_metrics,
        "total_records": total_records, "matched_records": matched_records,
        "record_match_rate": round(matched_records / total_records, 4) if total_records else 0,
    }
    if not json_output:
        _print_report(results)
    return results

def _print_report(r):
    print()
    print("RECONCILIATION EVALUATION REPORT")
    print("=" * 50)
    print()
    print("Dataset Alignment:")
    print(f'  Ground truth groups:        {r["ground_truth_groups"]}')
    print(f'  Engine groups:              {r["engine_groups"]}')
    print(f'  Matched by record content:  {r["aligned_groups"]}')
    print(f'  GT-only groups:             {r["gt_only_groups"]}')
    print(f'  Engine-only groups:         {r["engine_only_groups"]}')
    print()
    print("Status Classification (normalized):")
    print(f'  Correct:    {r["status_correct"]}')
    print(f'  Incorrect:  {r["status_incorrect"]}')
    print(f'  Accuracy:   {r["status_accuracy"]:.1%}')
    for m in r["status_mismatches"]:
        print(f'    {m["gt_group"]}: GT={m["gt_status"]}->{m["normalized_to"]} vs Engine={m["engine_status"]}->{m["engine_normalized"]}')
    print()
    print("Exception Type Classification:")
    print(f'  Correct:    {r["exception_correct"]}')
    print(f'  Incorrect:  {r["exception_incorrect"]}')
    print(f'  Accuracy:   {r["exception_accuracy"]:.1%}')
    for m in r["exception_mismatches"]:
        print(f'    {m["gt_group"]}: GT={m["gt_exception"]} vs Engine={m["engine_exception"]} ({m["engine_group"]})')
    print()
    print("Per-Class Metrics (exception type):")
    print(f'  {"CLASS":<28} {"Precision":>9} {"Recall":>7} {"F1":>7} {"Support":>8}')
    print('  ' + "-" * 55)
    for cls, m in r["class_metrics"].items():
        print(f'  {cls:<28} {m["precision"]:>9.4f} {m["recall"]:>7.4f} {m["f1"]:>7.4f} {m["support"]:>8}')
    print()
    print("Record-Level Metrics:")
    print(f'  Total source records:  {r["total_records"]}')
    print(f'  In matched groups:     {r["matched_records"]}')
    print(f'  Record match rate:     {r["record_match_rate"]:.1%}')
    print()

if __name__ == "__main__":
    run_evaluation(json_output="--json" in sys.argv)
