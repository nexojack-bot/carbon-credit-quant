"""
Phase 12 — Relative-value scoring.

Combines the hedonic model's residual and the comparable model's deviation
into one score per project, then classifies into five bands. Weights are
NOT arbitrarily chosen (the spec explicitly forbids that) — see the
docstring on combine_scores() for the justification, and
docs/research_decisions_log.md for the logged decision.

Every classification here is labelled "potential" mispricing, never a
guaranteed arbitrage — matching the spec's explicit requirement not to
overstate a residual as a trading opportunity.
"""

import logging
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

CLASSIFICATION_BANDS = [
    (-np.inf, -2.0, "strong potential undervaluation"),
    (-2.0, -1.0, "moderate potential undervaluation"),
    (-1.0, 1.0, "fair value range"),
    (1.0, 2.0, "moderate potential overvaluation"),
    (2.0, np.inf, "strong potential overvaluation"),
]


def classify_zscore(z: float) -> str:
    """Map a combined z-score to a classification band. Bands are +/-1 and
    +/-2 standard deviations — the standard convention for flagging moderate
    vs. strong deviations, not an arbitrarily chosen cutoff."""
    if pd.isna(z):
        return "insufficient data"
    for low, high, label in CLASSIFICATION_BANDS:
        if low <= z < high:
            return label
    return "insufficient data"


def combine_scores(hedonic_result_df: pd.DataFrame, comparable_result_df: pd.DataFrame) -> pd.DataFrame:
    """
    Combine hedonic residual and comparable-model deviation into one relative-value score.

    Weighting approach: equal-weighted average of the two models' standardized
    residuals, NOT arbitrarily chosen. Justification: with only two models and
    no historical backtest data yet (see Decision 4 in the research log) to
    empirically estimate which model predicts convergence better, equal
    weighting is the defensible default — weighting one model higher without
    evidence it's more accurate would itself be an arbitrary choice dressed up
    as a decision. Once real price history accumulates, this should be
    revisited: re-estimate weights based on which model's residuals actually
    predicted subsequent price convergence (see Phase 9 in the original spec).

    Both input DataFrames must have a 'project_id' column plus:
    - hedonic_result_df: 'observed_price', 'hedonic_model_price'
    - comparable_result_df: 'comparable_model_price', 'liquidity_proxy' (optional)
    """
    merged = hedonic_result_df.merge(comparable_result_df, on="project_id", how="inner")

    merged["hedonic_residual"] = np.log(merged["observed_price"]) - np.log(merged["hedonic_model_price"])
    merged["comparable_residual"] = np.log(merged["observed_price"]) - np.log(merged["comparable_model_price"])

    # Standardize each residual to its own z-score before combining, so the
    # two models (which can have very different residual scales) contribute
    # comparably rather than one dominating just because its raw units are bigger.
    for col in ["hedonic_residual", "comparable_residual"]:
        mean, std = merged[col].mean(), merged[col].std()
        merged[f"{col}_z"] = (merged[col] - mean) / std if std > 0 else 0.0

    merged["combined_zscore"] = merged[["hedonic_residual_z", "comparable_residual_z"]].mean(axis=1)
    merged["classification"] = merged["combined_zscore"].apply(classify_zscore)

    # Confidence flag: low liquidity means the observed price itself is a
    # weaker signal, so a "strong" classification on a thinly-traded project
    # deserves more skepticism, not less — surfaced as a column rather than
    # silently baked into the score, so the reader can apply their own judgement.
    if "liquidity_proxy" in merged.columns:
        merged["low_confidence"] = merged["liquidity_proxy"] <= 1

    logger.info(f"Scored {len(merged)} projects")
    logger.info(f"Classification distribution:\n{merged['classification'].value_counts()}")

    return merged.sort_values("combined_zscore")


def build_ranked_table(scored_df: pd.DataFrame) -> pd.DataFrame:
    """
    Produce the final Phase 12 output table: one row per project with observed
    price, both model-implied prices, residual, score, and classification —
    ready to display or export.
    """
    cols = [
        "project_id", "observed_price", "hedonic_model_price", "comparable_model_price",
        "combined_zscore", "classification",
    ]
    if "low_confidence" in scored_df.columns:
        cols.append("low_confidence")
    available_cols = [c for c in cols if c in scored_df.columns]
    return scored_df[available_cols].reset_index(drop=True)
