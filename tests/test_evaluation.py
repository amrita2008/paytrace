"""Tests for the evaluation layer.

8 focused tests covering: ground truth loading, status normalization,
record alignment, metrics calculation, ground-truth isolation, and
evaluation script execution.

Uses small deterministic fixtures where appropriate.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


# 1. Ground truth loads correctly

class TestGroundTruthLoading:

    def test_ground_truth_loads_with_38_groups(self):
        gt_path = Path("evaluation/ground_truth.json")
        assert gt_path.exists(), "ground_truth.json not found"
        with open(gt_path) as f:
            data = json.load(f)
        assert "match_groups" in data
        assert len(data["match_groups"]) == 38

    def test_ground_truth_groups_have_required_fields(self):
        gt_path = Path("evaluation/ground_truth.json")
        with open(gt_path) as f:
            data = json.load(f)
        for g in data["match_groups"]:
            assert "group_id" in g
            assert "payment_ids" in g
            assert "settlement_ids" in g
            assert "bank_entry_ids" in g
            assert "expected_status" in g
            assert "exception_type" in g


# 2. Status normalization

class TestStatusNormalization:

    def test_normalization_mapping(self):
        from evaluation.evaluate_reconciliation import STATUS_NORMALIZE
        assert STATUS_NORMALIZE["MATCHED"] == "MATCHED"
        assert STATUS_NORMALIZE["MISSING"] == "MISMATCHED"
        assert STATUS_NORMALIZE["EXCLUDED"] == "MISMATCHED"
        assert STATUS_NORMALIZE["UNMATCHED"] == "MISMATCHED"
        assert STATUS_NORMALIZE["AMBIGUOUS"] == "AMBIGUOUS"
        assert STATUS_NORMALIZE["DUPLICATE"] == "DUPLICATE"

    def test_engine_status_map(self):
        from evaluation.evaluate_reconciliation import ENGINE_STATUS_MAP
        assert ENGINE_STATUS_MAP["matched"] == "MATCHED"
        assert ENGINE_STATUS_MAP["mismatched"] == "MISMATCHED"
        assert ENGINE_STATUS_MAP["ambiguous"] == "AMBIGUOUS"
        assert ENGINE_STATUS_MAP["duplicate"] == "DUPLICATE"


# 3. Record alignment

class TestRecordAlignment:

    def test_align_groups_by_record_content(self):
        from evaluation.evaluate_reconciliation import _align_groups

        gt = [
            {"group_id": "G-1", "payment_ids": ["P1", "P2"], "settlement_ids": ["S1"], "bank_entry_ids": ["B1"],
             "expected_status": "MATCHED", "exception_type": None},
            {"group_id": "G-2", "payment_ids": ["P3"], "settlement_ids": [], "bank_entry_ids": [],
             "expected_status": "MISSING", "exception_type": "MISSING_SETTLEMENT"},
        ]
        engine = [
            {"group_id": "GRP-1", "status": "matched", "payment_ids": ["P2", "P1"], "settlement_ids": ["S1"],
             "bank_entry_ids": ["B1"], "exception_type": None, "match_score": 100, "evidence_count": 5},
            {"group_id": "GRP-2", "status": "mismatched", "payment_ids": ["P3"], "settlement_ids": [],
             "bank_entry_ids": [], "exception_type": "MISSING_SETTLEMENT", "match_score": None, "evidence_count": 1},
        ]

        aligned, gt_only, engine_only = _align_groups(gt, engine)
        assert len(aligned) == 2
        assert len(gt_only) == 0
        assert len(engine_only) == 0

    def test_unmatched_groups_detected(self):
        from evaluation.evaluate_reconciliation import _align_groups

        gt = [
            {"group_id": "G-1", "payment_ids": ["P1"], "settlement_ids": [], "bank_entry_ids": [],
             "expected_status": "MISSING", "exception_type": "MISSING_SETTLEMENT"},
        ]
        engine = [
            {"group_id": "GRP-1", "status": "mismatched", "payment_ids": ["P1"], "settlement_ids": [],
             "bank_entry_ids": [], "exception_type": "MISSING_SETTLEMENT", "match_score": None, "evidence_count": 1},
            {"group_id": "GRP-2", "status": "mismatched", "payment_ids": ["P99"], "settlement_ids": [],
             "bank_entry_ids": [], "exception_type": "MISSING_SETTLEMENT", "match_score": None, "evidence_count": 1},
        ]

        aligned, gt_only, engine_only = _align_groups(gt, engine)
        assert len(aligned) == 1
        assert len(gt_only) == 0
        assert len(engine_only) == 1
        assert engine_only[0]["group_id"] == "GRP-2"


# 4. Metrics calculation

class TestMetricsCalculation:

    def test_precision_recall_f1(self):
        from evaluation.evaluate_reconciliation import _compute_precision_recall_f1

        p, r, f1 = _compute_precision_recall_f1(10, 0, 0)
        assert p == 1.0 and r == 1.0 and f1 == 1.0

        p, r, f1 = _compute_precision_recall_f1(0, 0, 5)
        assert p == 0.0 and r == 0.0 and f1 == 0.0

        p, r, f1 = _compute_precision_recall_f1(3, 1, 2)
        assert abs(p - 0.75) < 0.001
        assert abs(r - 0.6) < 0.001
        assert abs(f1 - 2 * 0.75 * 0.6 / (0.75 + 0.6)) < 0.001


# 5. No ground truth in production modules

class TestGroundTruthIsolation:

    PRODUCTION_FILES = [
        "backend/reconciliation/engine.py",
        "backend/reconciliation/matching.py",
        "backend/reconciliation/batch.py",
        "backend/reconciliation/models.py",
        "backend/ai/investigation_service.py",
        "backend/ai/prompt_builder.py",
        "backend/ai/response_validator.py",
        "backend/ai/policy_validator.py",
        "backend/ai/sanitizer.py",
        "backend/api/routes.py",
        "backend/api/ai_routes.py",
        "backend/api/reconciliation_runner.py",
    ]

    def test_no_evaluation_import_in_production_modules(self):
        for filepath in self.PRODUCTION_FILES:
            path = Path(filepath)
            assert path.exists(), f"File not found: {filepath}"
            source = path.read_text()
            assert "from evaluation" not in source, f"{filepath} imports from evaluation"
            assert "import evaluation" not in source, f"{filepath} imports evaluation"

    def test_no_ground_truth_in_api_schemas(self):
        from backend.api.schemas import GroupDetailResponse, PaginatedResultsResponse
        fields_gt = GroupDetailResponse.model_fields.keys()
        assert "ground_truth" not in fields_gt
        assert "expected_status" not in fields_gt

    def test_no_ground_truth_in_ai_schemas(self):
        from backend.api.ai_schemas import InvestigationResponseSchema
        fields = InvestigationResponseSchema.model_fields.keys()
        assert "ground_truth" not in fields
        assert "expected_status" not in fields


# 6. Evaluation scripts run without error

class TestEvaluationScripts:

    def test_evaluate_reconciliation_runs(self):
        from evaluation.evaluate_reconciliation import run_evaluation
        results = run_evaluation(json_output=True)
        assert "status_accuracy" in results
        assert "exception_accuracy" in results
        assert "aligned_groups" in results
        assert isinstance(results["class_metrics"], dict)

    def test_evaluate_ai_runs(self):
        from evaluation.evaluate_ai import run_evaluation
        results = run_evaluation(json_output=True)
        assert "total_investigated" in results
        assert "structural_valid" in results
        assert "no_cot" in results
        assert results["no_cot"] is True
