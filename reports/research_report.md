# Carbon Credit Relative-Value & Pricing Inefficiency Model
## Research Report — Preliminary

**Status: preliminary.** This report is based on the first real run of the pipeline against live market data. The sample size (51 credits) is small enough that several conclusions below are explicitly flagged as provisional. This report will be revised as the scheduled data refresh (see README) accumulates a larger and more diverse sample.

---

## 1. Executive Summary

This project builds a quantitative pipeline to identify carbon credits that may be mispriced relative to comparable credits, after controlling for observable project characteristics. Using real project data from CarbonPlan's OffsetsDB and real live prices from the Carbonmark marketplace, the pipeline cleans and joins the data, fits a hedonic pricing model and a nearest-neighbours comparable-credit model, and combines both into a relative-value score.

The first real run covers 51 Verra-registered credits with active Carbonmark listings. The pipeline runs correctly end-to-end and produces a defensible, honestly-caveated output — but the sample is too small for the hedonic model's individual coefficients to reach statistical significance. One large outlier (a Myanmar blue-carbon mangrove project) was investigated and is most likely explained by thin comparable coverage rather than genuine mispricing. The main finding of this phase of the project is methodological: a working, tested, honestly-scoped pipeline, ready to produce more confident results as real price history accumulates.

## 2. Introduction

Voluntary carbon markets allow organizations to purchase credits representing verified emissions reductions or removals, outside of any government compliance mandate. Unlike compliance markets (e.g. the EU Emissions Trading System), voluntary credits are heterogeneous — they differ by registry, methodology, project type, vintage, geography, and verification standard — and trade over-the-counter rather than on a centralized exchange. This heterogeneity and lack of centralized price discovery creates the conditions for persistent, hard-to-detect pricing inefficiencies: two credits representing functionally similar emissions reductions can trade at very different prices simply because there is no efficient mechanism forcing convergence.

This project asks whether those inefficiencies can be identified systematically, using public data and standard relative-value techniques adapted from quantitative finance.

## 3. Carbon Market Background

A carbon credit represents one tonne of CO2-equivalent emissions avoided, reduced, or removed, verified against a specific methodology and issued by a registry (e.g. Verra, Gold Standard, American Carbon Registry). Key characteristics that can legitimately affect price include:

- **Registry and methodology**: different registries have different verification rigor and market reputations.
- **Project type**: renewable energy, REDD+ (avoided deforestation), afforestation/reforestation, methane capture, direct air capture, and others carry different perceived quality and permanence.
- **Vintage**: the year the emissions reduction occurred; older vintages sometimes trade at a discount.
- **Geography**: country-level factors (regulatory risk, co-benefit narratives) can affect price.
- **Additionality**: whether the reduction wouldn't have happened without carbon finance — harder-to-verify additionality is often priced lower.
- **Permanence and reversal risk**: nature-based removals (e.g. forestry) carry reversal risk (fire, logging) that engineered removals don't.
- **Co-benefits**: biodiversity, community development, and Sustainable Development Goal alignment can command a premium, particularly for nature-based and blue-carbon projects.

This project uses registry, project type, country, project age, and market-activity proxies as observable features. It deliberately does not fabricate a composite "environmental quality score" — see Section 6.

## 4. Research Question

*After controlling for observable differences in registry, project type, country, project age, and market activity, which carbon credits appear statistically expensive or cheap relative to comparable credits?*

Sub-questions:
- Do similar credits trade within a predictable price range? *(Not yet confidently testable — see Section 8.)*
- Which characteristics explain the most price variation? *(Not yet confidently testable at n=51.)*
- Are apparent price differences better explained by illiquidity or thin data than by genuine mispricing? *(Actively investigated for the one large outlier found — see Section 8.)*

## 5. Data

**OffsetsDB** (CarbonPlan, free public archive): 11,659 projects across 7 registries, with issuance/retirement transaction history. Provides project characteristics; no price data.

**Carbonmark API** (free sandbox key): live marketplace listing prices for tokenized credits tied to real registry project IDs. Pulled live for this report: 1,116 catalog projects, of which 91 have an active listing (`hasSupply: true`, price > 0), of which 51 are on Verra — the only Carbonmark-covered registry that reliably joins to OffsetsDB.

**No historical price time series exists as free public data anywhere**, for either voluntary carbon credits specifically. This is a hard constraint on the project, not an oversight — see Section 9.

## 6. Methodology

Data flows through five stages: clean → load to SQLite → engineer features → fit two independent pricing models → combine into a relative-value score. Each stage is implemented as tested, reusable functions in `src/`, not inline notebook code, so the same logic runs whether triggered manually or by the scheduled GitHub Actions refresh.

Cleaning standardizes registry names, fills categorical nulls explicitly (rather than leaving NaN, which silently breaks downstream grouping), drops non-positive or missing transaction quantities, and — a fix added after testing surfaced the need — buckets any `country` or `project_type` level with fewer than 5 observations into an `'other'` category to prevent a rank-deficient regression matrix.

## 7. Feature Engineering

Features used: `registry`, `project_type`, `country` (all categorical, one-hot or dummy-encoded), `project_age_years` (from first issuance date), `liquidity_proxy` (count of transactions on record), and `project_type_supply` (how many projects share this project type, as a rough category-competition proxy).

**Deliberately not included:** a composite environmental-quality score. The original project brief explicitly warns against inventing subjective quality scores without a defensible weighting methodology, and none of the available data supports one yet (no consistent third-party quality ratings are freely available at the project level). This is logged as a legitimate future extension, not a shortcut taken silently.

## 8. Pricing Models

**Model A — Hedonic regression.** OLS with HC3 robust standard errors, predicting log(price) from the features above. Result on the real 51-credit sample: R² = 0.46, adjusted R² = 0.34, but **no individual coefficient reaches p < 0.05**, and the condition number (4.65 × 10⁵) remains elevated despite rare-category bucketing. Residuals are right-skewed (skew = 1.93) with a highly non-normal distribution (Jarque-Bera p ≈ 0). **Honest interpretation: this model cannot currently support confident claims about which specific characteristics drive price** — it is included because it runs correctly and the R² is not meaningless, but individual coefficients should not be quoted as findings at this sample size.

**Model B — Comparable-credit model.** k-nearest-neighbours (k=5) on standardized numeric features and one-hot encoded categoricals, using median neighbour price as the expected price. Nonparametric — doesn't require statistical significance to be informative, and is the more defensible model to lean on given Model A's current limitations.

**Combined relative-value score.** Equal-weighted average of both models' standardized residuals (z-scores). Equal weighting was a deliberate choice, not a default: with no historical backtest data yet to empirically determine which model's residuals better predict subsequent price convergence, weighting one model higher without evidence would itself be an arbitrary choice. See `docs/research_decisions_log.md`, Decision 4, for the full reasoning and the plan to revisit this once backtest data exists.

## 9. Results

Of 51 scored credits: 6 classified as potentially undervalued, 39 in the fair-value range, 6 potentially overvalued (see `data/processed/relative_value_scores_latest.csv` and the interactive dashboard at `reports/website/index.html` for the full ranked table).

**One outlier investigated directly, not just flagged.** `VCS-1764` (a Myanmar mangrove reforestation "blue carbon" project) prices at $42.00 against a hedonic-model-implied $2.14 and comparable-model-implied $1.05 — a combined z-score of 4.66, the largest in the sample. Checked against its raw Carbonmark record: it's a real, actively-traded credit (`totalListingsSupply: 968.87`, not a zero-supply catalog placeholder). The most defensible explanation is that blue carbon credits carry a genuine premium for biodiversity and community co-benefits, and this 51-credit, Verra-only sample has no other blue carbon credits for the comparable model to draw on. **This is presented as a probable data-thinness artifact, not a confirmed pricing anomaly** — exactly the distinction the original project brief requires between "observed price difference" and "potential mispricing."

## 10. Robustness Checks

Completed: residual diagnostics (mean ≈ 0, confirmed), multicollinearity check via condition number (flagged and addressed via category bucketing), rare-category handling (verified via unit tests and a real bug found in testing — see Decision 5).

**Not yet completed, and explicitly deferred rather than faked:** cross-validation, alternative model specifications, and sensitivity analysis on the comparable model's k parameter. At n=51, a train/test split would leave too few observations per side to be meaningful. These are planned once the sample grows past roughly 150–200 credits (a judgement threshold, not a derived one) via the scheduled refresh.

## 11. Limitations

- **Sample size (51) is the binding constraint on everything in this report.** Every finding above should be read as provisional.
- **No historical price time series exists**, so no backtest of whether flagged "potential mispricing" actually converges over time. The scheduled Carbonmark refresh begins building one from this project's start date forward.
- **Registry coverage is currently Verra-only** in the real priced sample, so the original research question about cross-registry price differences cannot yet be answered with real data.
- **No environmental-quality score** is used, by design (see Section 7) — this means genuine quality differences within a project type/registry/country combination aren't captured, and may be part of what the model's unexplained residual variance reflects.
- **Sandbox API data**: Carbonmark prices were pulled via a sandbox API key. Prices appeared to vary meaningfully across projects (not placeholder-uniform), suggesting real market data, but this hasn't been cross-validated against a second independent source.

## 12. Practical Implications

None of the classifications in this report should be treated as executable trading signals. At this sample size and without a validated backtest, the most defensible practical use of this project is as a monitoring tool: re-run monthly, watch how the sample grows and how classifications for the same credit change over time, and treat persistent flags (the same credit repeatedly classified as under/overvalued across multiple refreshes) as more informative than a single snapshot.

## 13. Conclusion

This phase of the project delivers a real, tested, end-to-end pricing pipeline against live market data — not a proof of concept on synthetic data. The infrastructure (cleaning, database, feature engineering, two independent pricing models, relative-value scoring, an automated refresh schedule, and a public-facing dashboard) is complete and validated. The substantive research question — which carbon credits are genuinely mispriced — remains open, honestly, pending a larger sample. That is the correct place for this project to be after one real run, and the next milestone is accumulating enough price history to revisit Sections 8–11 with statistical confidence.

---

*Generated from the pipeline run at the timestamp recorded in `data/processed/relative_value_scores_latest.csv`. See `docs/research_decisions_log.md` for the complete, dated record of every methodological decision behind this report.*
