"""
Visualization functions. Each one answers a specific question (per the spec's
explicit "every chart must answer a useful question" rule) rather than being
decorative. Returns the matplotlib Figure so the caller decides whether to
show it, save it, or embed it in a notebook.
"""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def plot_price_distribution(df: pd.DataFrame, price_col: str = "price_usd", by: str = "registry"):
    """Answers: how are prices distributed, and does that distribution differ by registry?"""
    fig, ax = plt.subplots(figsize=(8, 5))
    for group_name, group_df in df.groupby(by):
        ax.hist(group_df[price_col], bins=20, alpha=0.5, label=group_name)
    ax.set_xlabel("Price (USD)")
    ax.set_ylabel("Count")
    ax.set_title(f"Price distribution by {by}")
    ax.legend()
    fig.tight_layout()
    return fig


def plot_actual_vs_predicted(observed: pd.Series, predicted: pd.Series, title: str = "Actual vs. model-implied price"):
    """Answers: how well does the model track observed prices, and where does it fail?
    Points far from the diagonal are the large-residual credits the relative-value
    score is built on — this chart is the visual version of that scoring logic."""
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.scatter(predicted, observed, alpha=0.5, s=20)
    lims = [min(predicted.min(), observed.min()), max(predicted.max(), observed.max())]
    ax.plot(lims, lims, "r--", linewidth=1, label="Perfect fit")
    ax.set_xlabel("Model-implied price (USD)")
    ax.set_ylabel("Observed price (USD)")
    ax.set_title(title)
    ax.legend()
    fig.tight_layout()
    return fig


def plot_residual_distribution(residuals: pd.Series, title: str = "Residual distribution"):
    """Answers: are residuals roughly symmetric around zero, or is the model
    systematically over/under-predicting for some segment of the data?"""
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.hist(residuals, bins=30, edgecolor="white")
    ax.axvline(0, color="red", linestyle="--", linewidth=1)
    ax.set_xlabel("Residual (log price)")
    ax.set_ylabel("Count")
    ax.set_title(title)
    fig.tight_layout()
    return fig


def plot_relative_value_ranking(ranked_df: pd.DataFrame, n: int = 15):
    """Answers: which specific credits does the model flag as most under/overvalued?
    Shows the extremes of the ranked table as a horizontal bar chart, sorted by
    combined z-score — this is the chart a portfolio reviewer will actually look at."""
    top_under = ranked_df.nsmallest(n // 2, "combined_zscore")
    top_over = ranked_df.nlargest(n // 2, "combined_zscore")
    combined = pd.concat([top_under, top_over]).sort_values("combined_zscore")

    fig, ax = plt.subplots(figsize=(8, max(4, len(combined) * 0.35)))
    colors = ["#1D9E75" if z < 0 else "#D85A30" for z in combined["combined_zscore"]]
    ax.barh(combined["project_id"], combined["combined_zscore"], color=colors)
    ax.axvline(0, color="black", linewidth=0.8)
    ax.set_xlabel("Combined relative-value z-score (negative = potentially undervalued)")
    ax.set_title("Most extreme relative-value flags")
    fig.tight_layout()
    return fig
