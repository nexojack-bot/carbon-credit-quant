"""
Model B — Comparable-credit model.

For every credit, finds its k nearest neighbours in feature space (after
standardizing numeric features and one-hot encoding categoricals) and uses
their median price as the "expected price" — the classic relative-value
technique of pricing something against what similar things trade at.

Distance metric choice: Euclidean distance on standardized + one-hot encoded
features. We use plain Euclidean rather than Mahalanobis distance because
Mahalanobis requires inverting a covariance matrix, which is unstable with
this many one-hot categorical columns relative to sample size (high risk of
a near-singular matrix) — a real limitation worth stating rather than using
a more "sophisticated"-sounding method that would actually be less reliable
here. See docs/research_decisions_log.md for this choice logged formally.
"""

import logging
import numpy as np
import pandas as pd
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)


def build_comparable_model(df: pd.DataFrame, feature_cols: dict, k: int = 5):
    """
    Build the nearest-neighbours comparable model.

    k=5 default: small enough that "comparable" credits are actually similar,
    large enough that the median isn't dominated by one noisy price. This is
    a judgement call, not a derived constant — worth revisiting with a
    sensitivity check (try k=3, k=10, see how much rankings move) once real
    price data is in.

    Returns: (fitted NearestNeighbors object, the encoded feature matrix,
    the scaler used, and the project_id index aligned to the feature matrix
    rows — needed later to map neighbour indices back to project_ids).
    """
    categorical = feature_cols["categorical"]
    numeric = feature_cols["numeric"]

    model_cols = categorical + numeric
    model_df = df[["project_id"] + model_cols].dropna().reset_index(drop=True)

    if len(model_df) < k + 1:
        raise ValueError(
            f"Only {len(model_df)} complete rows — need at least k+1={k+1} to find "
            f"neighbours excluding self."
        )

    encoded = pd.get_dummies(model_df[categorical], drop_first=False)
    scaler = StandardScaler()
    numeric_scaled = pd.DataFrame(
        scaler.fit_transform(model_df[numeric]), columns=numeric, index=model_df.index
    )
    feature_matrix = pd.concat([encoded, numeric_scaled], axis=1)

    # k+1 because the nearest neighbour to any point is always itself —
    # we fetch one extra and drop self-matches when scoring.
    nn = NearestNeighbors(n_neighbors=k + 1, metric="euclidean")
    nn.fit(feature_matrix.values)

    logger.info(f"Comparable model fit on {len(model_df)} projects, k={k}, {feature_matrix.shape[1]} encoded features")
    return nn, feature_matrix, scaler, model_df["project_id"]


def score_comparable_prices(nn, feature_matrix: pd.DataFrame, project_ids: pd.Series,
                              prices: pd.Series, k: int = 5) -> pd.DataFrame:
    """
    For each project, find its k nearest neighbours (excluding itself) and
    compute the median price among them as the comparable-implied price.

    prices must be indexed the same way as project_ids (same row order).
    """
    distances, indices = nn.kneighbors(feature_matrix.values)

    results = []
    for row_idx, project_id in enumerate(project_ids):
        neighbour_idx = indices[row_idx]
        neighbour_dist = distances[row_idx]
        # Drop the first neighbour if it's a self-match (distance ~0 at own index)
        mask = neighbour_idx != row_idx
        neighbour_idx = neighbour_idx[mask][:k]
        neighbour_dist = neighbour_dist[mask][:k]

        neighbour_prices = prices.iloc[neighbour_idx]
        comparable_price = neighbour_prices.median()
        avg_distance = neighbour_dist.mean()

        results.append({
            "project_id": project_id,
            "comparable_model_price": comparable_price,
            "comparable_avg_distance": avg_distance,
            "n_comparables_used": len(neighbour_idx),
        })

    return pd.DataFrame(results)
