# PayTrace Evaluation Layer

Offline evaluation of PayTrace reconciliation accuracy and AI investigation quality.

## Architecture

```
evaluation/
├── ground_truth.json              # Authoritative answer key (38 groups)
├── evaluate_reconciliation.py     # Reconciliation accuracy evaluation
├── evaluate_ai.py                 # AI pipeline structural validation
└── README.md                      # This file
```

**Ground-truth isolation**: `evaluation/` is never imported by production code. The reconciliation engine, AI investigation layer, and API routes have no dependency on ground truth.

## Running

```bash
# Reconciliation evaluation
python -m evaluation.evaluate_reconciliation

# AI investigation evaluation
python -m evaluation.evaluate_ai

# JSON output
python -m evaluation.evaluate_reconciliation --json
python -m evaluation.evaluate_ai --json
```

## Status Normalization

Ground truth uses 7 status values; the engine uses 4. Normalization mapping:

| Ground Truth | → Normalized | Rationale |
|---|---|---|
| MATCHED | MATCHED | Direct equivalence |
| MISMATCHED | MISMATCHED | Direct equivalence |
| MISSING | MISMATCHED | Missing settlement is a mismatch |
| EXCLUDED | MISMATCHED | Failed/refunded correctly flagged |
| UNMATCHED | MISMATCHED | Orphan bank entry correctly flagged |
| AMBIGUOUS | AMBIGUOUS | Direct equivalence |
| DUPLICATE | DUPLICATE | Direct equivalence |

**Status correctness and exception-type correctness are reported independently.** An incorrect exception type is flagged even when the normalized status is correct.

## Group Alignment

Ground truth uses `G-xxx` IDs; the engine uses `GRP-xxx` IDs. Groups are aligned by record content: `(sorted(payment_ids), sorted(settlement_ids), sorted(bank_entry_ids))`.

## AI Evaluation

Two modes:

1. **Pipeline validation (NullProvider)**: Always runs. Validates structural compliance, evidence grounding, policy compliance, fallback behavior, confidence range, human-review policy, and absence of chain-of-thought. Does not measure content quality.

2. **Real LLM evaluation (optional)**: Only runs if `PAYTRACE_LLM_API_KEY` is configured. Reports fallback rate, mean confidence, mean facts, mean unresolved questions.

### Limitations

- NullProvider validates structure only, not explanation quality
- Real LLM root-cause accuracy cannot be measured without labeled data
- Evidence grounding checks citation validity, not semantic correctness
- Results depend on provider/model configuration

## Known Discrepancies

- 2 TIMING_MISMATCH groups (G-0014, G-0016) classified as MATCHED by engine
- 2 AMBIGUOUS groups (G-0017, G-0018) structurally split by engine (both candidates reported separately)
- 4 engine-only MISSING_SETTLEMENT groups for payments without settlements
