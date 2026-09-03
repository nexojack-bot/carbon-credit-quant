"""
Feature engineering: joins projects + credit aggregates + prices into one
modelling-ready DataFrame, and derives the features the pricing models use.

Design note: we deliberately do NOT fabricate an environmental-quality score
here. The original project spec explicitly warns against inventing subjective
quality scores without a defensible methodology — so project-type and
registry are used as-is (they proxy for quality indirectly, since registries
and methodologies differ in rigor), and a real quality score is left as a
documented future extension, not faked to look more sophisticated.
"""

import logging
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def bucket_rare_categories(series: pd.Series, min_count: int = 5, other_label: str = "other") -> pd.Series:
    """
    Collapse any category level with fewer than min_count observations into
    'other'. This exists because of a real bug found by testing: with a small
    price sample, high-cardinality columns like 'country' produce a
    rank-deficient design matrix (statsmodels raises SingularMatrixWarning,
    and result.summary() then crashes outright trying to compute the
    F-statistic on a singular matrix — not just a cosmetic warning).

    min_count=5 is a reasonable starting default, not a derived constant —
    revisit it once real price coverage is known. Logged as a limitation in
    docs/research_decisions_log.md.
    """
    counts = series.value_counts()
    rare_categories = counts[counts < min_count].index
    if len(rare_categories) > 0:
        logger.info(
            f"Bucketing {len(rare_categories)} rare category levels "
            f"(each with fewer than {min_count} observations) into '{other_label}'"
        )
    return series.where(~series.isin(rare_categories), other_label)


def build_modelling_dataset(
    projects_df: pd.DataFrame,
    project_aggregates_df: pd.DataFrame,
    prices_df: pd.DataFrame,
    reference_date: str | None = None,
) -> pd.DataFrame:
    """
    Join cleaned projects + credit aggregates + prices, then derive features.

    prices_df must have columns: project_id, price_usd (one row per project;
    if you have multiple price observations per project, aggregate to one —
    e.g. most recent or median — before calling this function).

    reference_date: ISO date string used to compute project age. Defaults to
    today if not given.
    """
    if reference_date is None:
        reference_date = pd.Timestamp.now().strftime("%Y-%m-%d")
    ref_ts = pd.Timestamp(reference_date)

    df = projects_df.merge(project_aggregates_df, on="project_id", how="left")
    n_before_price_join = len(df)
    df = df.merge(prices_df[["project_id", "price_usd"]], on="project_id", how="inner")
    logger.info(
        f"Price join: {n_before_price_join} projects -> {len(df)} with a matched price "
        f"({n_before_price_join - len(df)} projects had no price observation and were dropped "
        f"from the modelling set, not from the underlying data)"
    )

    # Fill credit-aggregate NaNs (projects with a price but no transaction history yet)
    for col in ["credits_issued", "credits_retired", "credits_remaining", "n_vintages", "n_transactions"]:
        if col in df.columns:
            df[col] = df[col].fillna(0)

    # Project age in years, from first issuance to reference date. Missing
    # first_issuance_at means we can't compute this — leave as NaN, don't guess.
    # utc=True normalizes any timezone-aware timestamps in the source data so
    # subtraction against ref_ts doesn't fail on a tz-naive/tz-aware mismatch
    # (this bug was caught by actually running the pipeline against real data).
    df["first_issuance_at"] = pd.to_datetime(df["first_issuance_at"], errors="coerce", utc=True)
    df["project_age_years"] = (ref_ts.tz_localize("UTC") - df["first_issuance_at"]).dt.days / 365.25

    # Log price is the standard hedonic-model target transform: prices are
    # right-skewed (a few very expensive removal credits, many cheap ones),
    # and log-linear regression handles that better than a raw linear fit.
    df["log_price"] = np.log(df["price_usd"])

    # Liquidity proxy: how many transactions has this project seen. A project
    # with 1 transaction and a listed price is a much less reliable price
    # signal than one with 50 transactions — this feeds the relative-value
    # score's confidence/liquidity adjustment later.
    df["liquidity_proxy"] = df["n_transactions"]

    # Category-level supply: how many projects share this project_type. Used
    # to check whether apparent price effects are really about category size
    # (more supply -> more price competition) rather than quality.
    # Computed BEFORE bucketing rare categories, so supply reflects the true
    # original category size, not the post-bucketing 'other' group size.
    category_counts = df["project_type"].value_counts()
    df["project_type_supply"] = df["project_type"].map(category_counts)

    # Bucket rare categories in the high-cardinality columns before they hit
    # the regression — see bucket_rare_categories() docstring for why this is
    # necessary, not optional. min_count scales loosely with sample size: a
    # fixed count of 5 is a reasonable floor regardless of dataset size, since
    # fewer than 5 observations can't support a stable dummy-variable coefficient.
    df["country"] = bucket_rare_categories(df["country"], min_count=5)
    df["project_type"] = bucket_rare_categories(df["project_type"], min_count=5)

    logger.info(f"build_modelling_dataset: final shape {df.shape}")
    return df


def get_feature_columns() -> dict:
    """
    Central place listing which columns feed the hedonic model as which kind
    of feature. Keeping this in one function means the model code and the
    feature code can't silently drift out of sync.
    """
    return {
        "target": "log_price",
        "categorical": ["registry", "project_type", "country"],
        "numeric": ["project_age_years", "liquidity_proxy", "project_type_supply"],
    }
