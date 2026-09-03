"""
Model A — Hedonic pricing model.

Estimates expected log(price) as a function of observable project
characteristics using OLS. Deliberately interpretable over predictive:
see docs/research_decisions_log.md, Decision 3, for why.
"""

import logging
import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf

logger = logging.getLogger(__name__)


def fit_hedonic_model(df: pd.DataFrame, feature_cols: dict):
    """
    Fit price = f(registry, project_type, country, project_age, liquidity, supply)
    using OLS with robust (HC3) standard errors — HC3 rather than plain OLS
    standard errors because carbon credit prices are very likely
    heteroskedastic (price variance differs a lot between e.g. cheap avoidance
    credits and expensive removal credits), and HC3 is the more conservative
    correction for smaller samples.

    Returns the fitted statsmodels result object, plus a DataFrame of the
    dataset actually used (after dropping rows with missing feature values —
    OLS can't handle NaNs, and silently dropping without telling you is how
    silent bugs happen).
    """
    target = feature_cols["target"]
    categorical = feature_cols["categorical"]
    numeric = feature_cols["numeric"]

    model_cols = [target] + categorical + numeric
    model_df = df[model_cols].copy()

    n_before = len(model_df)
    model_df = model_df.dropna()
    n_after = len(model_df)
    if n_after < n_before:
        logger.warning(
            f"Dropped {n_before - n_after} rows with missing values before fitting "
            f"(had NaN in one of: {model_cols})"
        )

    if n_after < 30:
        raise ValueError(
            f"Only {n_after} complete rows available for modelling — too few to fit "
            f"a reliable regression with this many categorical levels. Check your "
            f"price join (are you actually pulling enough Carbonmark prices?)."
        )

    # Build the formula string: categorical columns wrapped in C() so
    # statsmodels treats them as dummy variables, not numbers.
    cat_terms = " + ".join(f"C({col})" for col in categorical)
    num_terms = " + ".join(numeric)
    formula = f"{target} ~ {cat_terms} + {num_terms}"
    logger.info(f"Fitting: {formula}")

    model = smf.ols(formula=formula, data=model_df)
    result = model.fit(cov_type="HC3")

    logger.info(f"Model fit on {n_after} rows. R-squared: {result.rsquared:.3f}")
    return result, model_df


def diagnose_model(result, model_df: pd.DataFrame, feature_cols: dict) -> dict:
    """
    Run the residual diagnostics the spec explicitly requires before trusting
    the model: check for obvious multicollinearity (via condition number,
    a full VIF table needs a design matrix we don't retain here) and basic
    residual shape. Returns a dict of findings rather than just printing —
    so the calling notebook can act on them, not just eyeball them.
    """
    residuals = result.resid
    findings = {
        "r_squared": result.rsquared,
        "adj_r_squared": result.rsquared_adj,
        "n_obs": int(result.nobs),
        "condition_number": result.condition_number,
        "residual_mean": float(residuals.mean()),
        "residual_std": float(residuals.std()),
        "residual_skew": float(residuals.skew()),
    }

    # Condition number > 30 is the conventional rule-of-thumb flag for
    # concerning multicollinearity (Belsley, Kuh & Welsch) — cite this
    # explicitly rather than inventing a threshold, since an arbitrary cutoff
    # here is exactly the kind of thing the spec says to justify, not assume.
    findings["multicollinearity_flag"] = findings["condition_number"] > 30

    if abs(findings["residual_mean"]) > 0.01:
        logger.warning(f"Residual mean is {findings['residual_mean']:.4f}, not ~0 — check model specification")
    if findings["multicollinearity_flag"]:
        logger.warning(
            f"Condition number {findings['condition_number']:.1f} exceeds the conventional "
            f"threshold of 30 — some features may be redundant. Inspect coefficient "
            f"standard errors before trusting individual coefficients."
        )

    return findings


def predict_hedonic_price(result, df: pd.DataFrame) -> pd.Series:
    """
    Predict log(price), then exponentiate back to price. Note: exponentiating
    a log-scale prediction introduces a known small upward bias (Jensen's
    inequality) — for a portfolio project this is worth naming rather than
    silently ignoring, even though the correction (Duan smearing) is a
    documented future improvement, not implemented here.
    """
    log_pred = result.predict(df)
    return np.exp(log_pred)
