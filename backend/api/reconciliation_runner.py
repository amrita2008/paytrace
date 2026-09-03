"""Reconciliation runner — loads data, runs engine, caches results.

Lazy-loaded on first API request. Results cached in module-level dict.
No evaluation/ access. No AI/LLM calls.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.config import settings
from backend.reconciliation.engine import ExactReconciliationEngine
from backend.reconciliation.matching import (
    normalize_bank_entry,
    normalize_payment,
    normalize_settlement,
)
from backend.reconciliation.models import ReconciliationResult

_cache: dict[str, Any] | None = None


def _load_and_run() -> dict[str, Any]:
    """Load raw JSON, normalize, run engine, and cache. Idempotent."""
    global _cache
    if _cache is not None:
        return _cache

    data_dir = Path(settings.DATA_DIR)

    with open(data_dir / "payment_gateway.json") as f:
        raw_pays = json.load(f)
    with open(data_dir / "settlements.json") as f:
        raw_setls = json.load(f)
    with open(data_dir / "bank_ledger.json") as f:
        raw_banks = json.load(f)

    pays = [normalize_payment(r) for r in raw_pays]
    setls = [normalize_settlement(r) for r in raw_setls]
    banks = [normalize_bank_entry(r) for r in raw_banks]

    engine = ExactReconciliationEngine()
    results = engine.reconcile(pays, setls, banks)

    _cache = {
        "payments": raw_pays,
        "settlements": raw_setls,
        "bank_entries": raw_banks,
        "results": results,
        "processing_timestamp": datetime.now(timezone.utc).isoformat(),
    }
    return _cache


def get_results() -> list[ReconciliationResult]:
    """Get cached reconciliation results, loading and running if needed."""
    return _load_and_run()["results"]


def get_source_counts() -> tuple[int, int, int]:
    """Get counts of raw source records."""
    data = _load_and_run()
    return len(data["payments"]), len(data["settlements"]), len(data["bank_entries"])


def get_processing_timestamp() -> str:
    """Get the ISO timestamp of when reconciliation was run."""
    return _load_and_run()["processing_timestamp"]


def clear_cache() -> None:
    """Reset cache. Use in tests."""
    global _cache
    _cache = None


def get_normalized_data() -> tuple[
    list["NormalizedPayment"],
    list["NormalizedSettlement"],
    list["NormalizedBankEntry"],
]:
    """Return cached normalized records for the AI investigation layer.

    Normalizes raw JSON on first call, caches in _cache.
    """
    data = _load_and_run()
    if "norm_pays" not in data:
        data["norm_pays"] = [normalize_payment(r) for r in data["payments"]]
        data["norm_setls"] = [normalize_settlement(r) for r in data["settlements"]]
        data["norm_banks"] = [normalize_bank_entry(r) for r in data["bank_entries"]]
    return data["norm_pays"], data["norm_setls"], data["norm_banks"]
