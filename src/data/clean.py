"""
Cleaning and standardization functions for OffsetsDB project/credit data.

Each function does one cleaning job and is unit-testable in isolation —
see tests/test_clean.py. This matters more than it might seem: a pipeline
built from small, tested functions is one you can actually debug when
real-world data breaks something (and it will).
"""

import logging
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

# OffsetsDB already harmonizes registry names reasonably well, but we keep an
# explicit mapping here rather than trusting that blindly — this is exactly
# the kind of "don't assume the upstream source is clean" check the project
# spec calls for.
REGISTRY_CANONICAL_MAP = {
    "verra": "verra",
    "vcs": "verra",
    "gold-standard": "gold-standard",
    "gold standard": "gold-standard",
    "american-carbon-registry": "american-carbon-registry",
    "acr": "american-carbon-registry",
    "climate-action-reserve": "climate-action-reserve",
    "car": "climate-action-reserve",
    "art-trees": "art-trees",
    "cercarbono": "cercarbono",
    "isometric": "isometric",
}


def standardize_registry_name(raw_name: str) -> str:
    """Map a raw registry string to its canonical form. Unknown values pass through
    lowercased rather than being silently dropped, so they're visible for review."""
    if pd.isna(raw_name):
        return "unknown"
    key = str(raw_name).strip().lower()
    return REGISTRY_CANONICAL_MAP.get(key, key)


def clean_projects(projects_df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean the raw OffsetsDB projects table:
    - standardize registry names
    - fill missing status with explicit 'unknown' rather than leaving NaN
      (NaN in a categorical column silently breaks groupby/dummy-variable code later)
    - drop exact duplicate project_id rows, keeping the first
    - flag rows with no project_type as 'unknown' rather than dropping them
      (dropping would bias the sample toward better-documented registries)
    """
    df = projects_df.copy()
    n_start = len(df)

    df["registry"] = df["registry"].apply(standardize_registry_name)
    df["status"] = df["status"].fillna("unknown")
    df["project_type"] = df["project_type"].fillna("unknown")
    df["category"] = df["category"].fillna("unknown")
    df["country"] = df["country"].fillna("unknown")

    n_before_dedup = len(df)
    df = df.drop_duplicates(subset="project_id", keep="first")
    n_dropped_dupes = n_before_dedup - len(df)
    if n_dropped_dupes > 0:
        logger.warning(f"Dropped {n_dropped_dupes} duplicate project_id rows")

    # Rename 'issued'/'retired' to explicit total_ names to match the SQL schema
    # and avoid confusion with per-transaction quantities in credit_transactions.
    df = df.rename(columns={"issued": "total_issued", "retired": "total_retired"})

    logger.info(f"clean_projects: {n_start} -> {len(df)} rows")
    return df


def clean_credit_transactions(credits_df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean the raw OffsetsDB credits table:
    - drop rows with missing project_id (can't be linked to anything, useless for modelling)
    - drop rows with non-positive or missing quantity (data errors, not real transactions)
    - coerce vintage to a nullable integer type
    """
    df = credits_df.copy()
    n_start = len(df)

    df = df.dropna(subset=["project_id"])

    before_qty = len(df)
    df = df[df["quantity"].notna() & (df["quantity"] > 0)]
    n_dropped_qty = before_qty - len(df)
    if n_dropped_qty > 0:
        logger.info(f"Dropped {n_dropped_qty} rows with missing/non-positive quantity")

    df["vintage"] = pd.to_numeric(df["vintage"], errors="coerce").astype("Int64")

    logger.info(f"clean_credit_transactions: {n_start} -> {len(df)} rows")
    return df


def compute_project_aggregates(credits_df: pd.DataFrame) -> pd.DataFrame:
    """
    Roll the transaction-level credits table up to one row per project:
    total issued, total retired, total remaining (issued - retired), and the
    number of distinct vintages seen. This is the input to feature engineering's
    'project age' and 'liquidity proxy' features.
    """
    issued = (
        credits_df[credits_df["transaction_type"] == "issuance"]
        .groupby("project_id")["quantity"].sum()
        .rename("credits_issued")
    )
    retired = (
        credits_df[credits_df["transaction_type"] == "retirement"]
        .groupby("project_id")["quantity"].sum()
        .rename("credits_retired")
    )
    n_vintages = credits_df.groupby("project_id")["vintage"].nunique().rename("n_vintages")
    n_transactions = credits_df.groupby("project_id").size().rename("n_transactions")

    agg = pd.concat([issued, retired, n_vintages, n_transactions], axis=1).fillna(0)
    agg["credits_remaining"] = (agg["credits_issued"] - agg["credits_retired"]).clip(lower=0)
    agg = agg.reset_index()

    logger.info(f"compute_project_aggregates: aggregated to {len(agg)} projects")
    return agg


def clean_price_value(raw_value) -> float | None:
    """
    Clean a single price value that might arrive as '$8.50', '8.50 USD', 8.5,
    or garbage. Returns None (not 0, not a fabricated default) if it can't be
    parsed — a missing price should stay missing, never silently become zero.
    """
    if raw_value is None:
        return None
    if isinstance(raw_value, (int, float)):
        return float(raw_value) if raw_value > 0 else None
    cleaned = "".join(ch for ch in str(raw_value) if ch.isdigit() or ch == ".")
    try:
        value = float(cleaned)
        return value if value > 0 else None
    except ValueError:
        return None
