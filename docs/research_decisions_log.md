# Research decisions log

Every major modelling or data decision, recorded as it's made: what was decided, what alternatives were considered, why the chosen approach won, and known limitations.

---

## Decision 1 — Data source for project/registry data

**Decision:** Use CarbonPlan's OffsetsDB (free, public CSV archive) as the source for project characteristics, issuances, and retirements.

**Alternatives considered:**
- Scraping Verra/Gold Standard registries directly — more fragile, duplicates work OffsetsDB already does, and OffsetsDB is maintained specifically to solve this harmonization problem.
- Berkeley Carbon Trading Project's Voluntary Registry Offsets Database — also free and credible, but updated only a few times a year via Excel, vs. OffsetsDB's more frequent snapshot cadence.

**Why:** OffsetsDB is free, actively maintained, already harmonizes field names and statuses across seven registries, and is explicitly built by a non-profit for researcher use rather than commercial resale.

**Limitations:** Snapshot-based, not real-time — freshness depends on when the archive was last generated (checked in notebook 01). No price data included.

---

## Decision 2 — Data source for pricing

**Decision:** Use the Carbonmark API's `/prices` endpoint for live per-project listing prices.

**Alternatives considered:**
- AlliedOffsets, MSCI — both have genuine historical transaction price data and would be the better source, but both are paid/subscription products with no free tier confirmed. Ruled out for a reproducible, free-to-run project.
- Ecosystem Marketplace / KAPSARC aggregate data — free, but only market-wide annual averages, not credit-level. Kept as a validation/context source, not a modelling input.

**Why:** Carbonmark is the only free, credit-level, currently-accessible price source found. It ties tokenized listings to real underlying registry project IDs (e.g. `VCS-191`), so it can be joined to OffsetsDB.

**Limitations (important):** Carbonmark gives a live snapshot, not a historical time series. There is no free historical carbon credit transaction price panel available anywhere as of this project's start. Consequence: no retrospective backtest is possible yet. This project instead begins polling Carbonmark on a schedule so a real time series accumulates going forward.

---

## Decision 3 — Model approach: statistical/econometric, not full ML

**Decision:** Core pricing model is hedonic regression (OLS via statsmodels), with a nearest-neighbours comparable-credit model (scikit-learn) for relative-value scoring. No black-box predictive ML model (e.g. gradient boosting) as the primary model.

**Alternatives considered:** A full ML regressor (random forest / gradient boosting) could plausibly get lower prediction error.

**Why:** Interpretability matters more than raw predictive accuracy for this project's purpose. A coefficient that says "REDD+ credits trade at an X% discount to removals, controlling for vintage and registry" is a more defensible research output — and a stronger portfolio signal for quant/commodities recruiters — than a black-box model with marginally better R² but no explainable mechanism. Nearest-neighbours for comparables is a genuine, standard relative-value technique, not a concession.

**Limitations:** OLS assumes a linear relationship between log-price and features; if that assumption fails badly, this will show up in residual diagnostics and may need revisiting.

---

## Decision 4 — No fabricated backtest

**Decision:** Do not attempt a historical backtest (Phase 9 of the original spec) until real historical price data has accumulated from ongoing Carbonmark polling.

**Alternatives considered:** Using compliance market data (EU ETS, ICAP allowance prices) as a stand-in historical series.

**Why rejected:** Compliance markets (regulated allowances) and voluntary markets (OTC carbon credits) are structurally different instruments. Using one to validate a model of the other would be methodologically misleading, not a legitimate substitute.

**Consequence:** This limitation is stated explicitly in the README and final report rather than papered over with a fake backtest.

---

## Decision 5 — Rare-category bucketing for high-cardinality features

**Decision:** Any level of `country` or `project_type` with fewer than 5 observations gets collapsed into an `'other'` bucket before fitting the hedonic model.

**How this was found:** Not a theoretical concern — a real bug caught by actually executing the pipeline end to end against a test price sample. With `country` used raw, the regression's design matrix became rank-deficient (statsmodels' `SingularMatrixWarning`, condition number in the billions), and `result.summary()` crashed outright trying to compute the F-statistic on a singular matrix. This is a direct consequence of having many countries relative to a necessarily small Carbonmark price sample.

**Alternatives considered:**
- Drop `country` entirely — simpler, but throws away real signal for the countries with good coverage.
- Group by continent/region instead of bucketing by count — more semantically meaningful, but requires a country-to-region mapping table not yet built.

**Why bucketing by count:** Simplest fix that directly addresses the mechanism of the bug (too few observations per dummy-variable level) without discarding a whole feature. `min_count=5` is a judgement call, not a derived constant — worth revisiting once real Carbonmark coverage is known. A country-to-region mapping is a reasonable future improvement, logged here rather than built speculatively before real data shows whether it's needed.

**Limitations:** This is a per-run decision, not a one-time fix — if the real Carbonmark price sample is very small (plausible, since not every OffsetsDB project is listed there), the `min_count` threshold may need lowering, or `country` may need dropping from the model entirely. Check the `multicollinearity_flag` in `diagnose_model()`'s output every time this is re-run with new data — don't assume the fix generalizes silently.

---

## Decision 6 — Working directory handling in notebooks 02 and 03

**Decision:** Both notebooks auto-detect the repo root (by locating `requirements.txt`) and `os.chdir()` into it, rather than assuming the kernel's working directory matches the notebook's file location.

**How this was found:** Another bug caught by actually executing the notebook, not assumed. `sys.path.insert(0, os.path.join(os.getcwd(), "..", "src"))` silently pointed at the wrong directory once tested with a kernel whose working directory didn't match the notebook's own folder — which is Colab's actual default behavior (working directory is `/content`, not wherever the notebook file happens to sit). The failure was a confusing `ModuleNotFoundError` several cells removed from the actual cause.

**Why auto-detection over documentation-only:** A comment telling you to "make sure you're in the right directory" is exactly the kind of thing that's easy to skip and hard to debug when skipped. Auto-detecting and failing loudly with a clear message if detection fails is more robust for a beginner-run notebook than trusting manual setup steps.

---

## Decision 7 — First real pipeline run: findings and what they mean

**What happened:** Ran the full pipeline against real Carbonmark data (pulled via a real sandbox API key) for the first time. Findings, recorded honestly rather than smoothed over:

- Of Carbonmark's 1,116 catalog projects, only **91 have an active listing** (`hasSupply: true`, `price > 0`). The rest are catalog entries with no current market price — confirms the project's own stated limitation that Carbonmark coverage is partial, not comprehensive.
- Of those 91, only **51 are on Verra (VCS)** — the only Carbonmark-listed registry that reliably joins to OffsetsDB's project characteristics. The other 40 are on registries (UCR, ICR, CMARK, REGEN, TVER, ECO, PUR) that OffsetsDB doesn't track at all. **Real usable sample size for the hedonic model is 51, not the 300 used in earlier synthetic testing.**
- With `registry` constant (all Verra) in this sample, it drops out of the model automatically — there's currently no registry-level price comparison possible with real data, only within-Verra comparison.
- The hedonic model fits (R² = 0.46) but **no individual coefficient is statistically significant at p < 0.05** with n=51. The condition number remains elevated (4.65e5) even after rare-category bucketing, and residuals are meaningfully right-skewed (skew = 1.93, Jarque-Bera p ≈ 0). Honest conclusion: **at this sample size, this model cannot support confident claims about which specific project characteristics drive Verra credit prices.** The comparable-credit model (nonparametric, doesn't require statistical significance) is more defensible to lean on right now.
- One project (`VCS-1764`, a Myanmar mangrove/"blue carbon" reforestation project) is flagged as a strong outlier ($42 vs. ~$1-2 model-implied). Checked against its raw Carbonmark record — it's a real, actively-traded credit, not a data error. Most likely explanation: blue carbon credits carry a genuine premium for biodiversity/community co-benefits, and a 51-project, Verra-only comparable set has no other blue carbon credits to compare it against. Flagged as a case where the model's classification ("strong potential overvaluation") is likely an artifact of a thin comparable set, not a real pricing signal — an example of exactly the caution the spec requires before calling a residual an opportunity.

**What this means for next steps:** Re-run notebook 02 repeatedly over time (per Decision 2) — both to build price history and because Carbonmark's live catalog will add new listings over time, growing the usable sample past 51. Until then, treat all current classifications as provisional and low-powered, not confident findings.
