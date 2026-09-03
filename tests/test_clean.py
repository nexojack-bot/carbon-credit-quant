"""
Unit tests for src/data/clean.py.

Run with: pytest tests/test_clean.py -v
(from the repo root, after `pip install pytest`)

These use small hand-built DataFrames, not real data — that's the point of
a unit test: isolate one function, control its input exactly, check its
output exactly. The full pipeline gets exercised separately against real
data in the notebooks.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pandas as pd
import numpy as np
import pytest

from data.clean import (
    standardize_registry_name,
    clean_projects,
    clean_credit_transactions,
    compute_project_aggregates,
    clean_price_value,
)


def test_standardize_registry_name_known_variants():
    assert standardize_registry_name("VCS") == "verra"
    assert standardize_registry_name("Verra") == "verra"
    assert standardize_registry_name("gold standard") == "gold-standard"


def test_standardize_registry_name_missing():
    assert standardize_registry_name(None) == "unknown"
    assert standardize_registry_name(np.nan) == "unknown"


def test_standardize_registry_name_unknown_passthrough():
    # Unknown values should NOT be silently dropped — they pass through
    # lowercased so they're visible for review, per the module's design.
    assert standardize_registry_name("SomeNewRegistry") == "somenewregistry"


def test_clean_projects_fills_missing_status():
    df = pd.DataFrame({
        "project_id": ["A", "B"],
        "registry": ["verra", "VCS"],
        "status": ["listed", None],
        "project_type": ["solar", None],
        "category": ["energy", None],
        "country": ["India", None],
        "issued": [100, 200],
        "retired": [10, 20],
    })
    cleaned = clean_projects(df)
    assert cleaned["status"].isna().sum() == 0
    assert cleaned.loc[cleaned["project_id"] == "B", "status"].iloc[0] == "unknown"
    # Both rows should have standardized to the same registry
    assert set(cleaned["registry"]) == {"verra"}
    # issued/retired should be renamed
    assert "total_issued" in cleaned.columns
    assert "total_retired" in cleaned.columns


def test_clean_projects_drops_duplicates():
    df = pd.DataFrame({
        "project_id": ["A", "A", "B"],
        "registry": ["verra", "verra", "verra"],
        "status": ["listed", "listed", "listed"],
        "project_type": ["solar", "solar", "wind"],
        "category": ["energy", "energy", "energy"],
        "country": ["India", "India", "Kenya"],
        "issued": [100, 100, 50],
        "retired": [0, 0, 0],
    })
    cleaned = clean_projects(df)
    assert len(cleaned) == 2
    assert set(cleaned["project_id"]) == {"A", "B"}


def test_clean_credit_transactions_drops_bad_quantities():
    df = pd.DataFrame({
        "project_id": ["A", "B", "C", "D"],
        "transaction_type": ["issuance", "issuance", "retirement", "issuance"],
        "quantity": [100, -5, np.nan, 0],
        "vintage": [2020, 2020, 2021, 2021],
    })
    cleaned = clean_credit_transactions(df)
    # Only the first row has a valid positive quantity
    assert len(cleaned) == 1
    assert cleaned.iloc[0]["project_id"] == "A"


def test_clean_credit_transactions_drops_missing_project_id():
    df = pd.DataFrame({
        "project_id": ["A", None],
        "transaction_type": ["issuance", "issuance"],
        "quantity": [100, 100],
        "vintage": [2020, 2020],
    })
    cleaned = clean_credit_transactions(df)
    assert len(cleaned) == 1


def test_compute_project_aggregates():
    df = pd.DataFrame({
        "project_id": ["A", "A", "A", "B"],
        "transaction_type": ["issuance", "retirement", "retirement", "issuance"],
        "quantity": [1000, 300, 200, 500],
        "vintage": [2020, 2020, 2021, 2019],
    })
    agg = compute_project_aggregates(df)
    a_row = agg[agg["project_id"] == "A"].iloc[0]
    assert a_row["credits_issued"] == 1000
    assert a_row["credits_retired"] == 500
    assert a_row["credits_remaining"] == 500
    assert a_row["n_transactions"] == 3

    b_row = agg[agg["project_id"] == "B"].iloc[0]
    assert b_row["credits_issued"] == 500
    assert b_row["credits_retired"] == 0
    assert b_row["credits_remaining"] == 500


def test_compute_project_aggregates_remaining_never_negative():
    # A project can't have negative credits remaining even if retirement
    # records somehow exceed issuance records (a data quality issue we should
    # clip rather than propagate as a nonsensical negative number).
    df = pd.DataFrame({
        "project_id": ["A", "A"],
        "transaction_type": ["issuance", "retirement"],
        "quantity": [100, 500],
        "vintage": [2020, 2020],
    })
    agg = compute_project_aggregates(df)
    assert agg.iloc[0]["credits_remaining"] == 0


def test_clean_price_value_handles_currency_symbols():
    assert clean_price_value("$8.50") == 8.50
    assert clean_price_value("8.50 USD") == 8.50  # letters and space stripped, "8.50" remains


def test_clean_price_value_basic_cases():
    assert clean_price_value(8.5) == 8.5
    assert clean_price_value(-1) is None
    assert clean_price_value(0) is None
    assert clean_price_value(None) is None
    assert clean_price_value("garbage") is None


if __name__ == "__main__":
    import subprocess
    subprocess.run(["pytest", __file__, "-v"])
