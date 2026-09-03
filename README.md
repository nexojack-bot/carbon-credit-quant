# Carbon Credit Relative-Value & Pricing Inefficiency Model

A quantitative research project comparing pricing inefficiencies across voluntary carbon credit markets, and identifying credits that may be mispriced relative to comparable credits after controlling for observable characteristics.

**Status:** early build — data exploration stage. This README will be filled in properly once the pipeline exists; for now it's a placeholder tracking scope.

## Research question

After controlling for observable differences in quality, vintage, project type, registry, geography, and market characteristics, which carbon credits appear statistically expensive or cheap relative to comparable credits?

## Status

**First real run completed** (see `docs/research_decisions_log.md`, Decision 7, for full details): 51 real Verra credits with live Carbonmark prices, joined to real OffsetsDB characteristics. Honest headline finding: at this sample size, the hedonic model has no statistically significant coefficients — real Carbonmark coverage is smaller and less diverse (Verra-only) than hoped, so current output should be treated as a working pipeline proof, not a confident pricing signal yet. `data/processed/relative_value_scores_latest.csv` has the real ranked table from this run.

## Key findings (preliminary — see caveats below)

*Based on the first real pipeline run: 51 Verra credits with live Carbonmark prices, joined to real OffsetsDB project characteristics.*

- **Real market coverage is thin.** Of Carbonmark's 1,116 catalog projects, only 91 currently have an active price listing, and of those, only 51 are on a registry (Verra) that OffsetsDB also tracks. This is the actual usable sample right now — not the hundreds of credits a mature version of this project would have.
- **No statistically significant price drivers — yet.** The hedonic regression fits (R² = 0.46) but with n=51 and 9 model parameters, no individual coefficient clears conventional significance (p < 0.05), and the design matrix's condition number remains elevated even after bucketing rare categories. Read as: **we cannot currently say with confidence which project characteristics drive Verra credit prices.** This is a sample-size problem, not a modelling failure — it should improve as more price history accumulates via the scheduled refresh.
- **Registry-level comparison isn't testable yet.** The original research question asks whether prices differ systematically across registries — but the current real sample is 100% Verra, so that comparison has no data to run on yet. Worth monitoring as Carbonmark's other-registry coverage grows.
- **One flagged outlier, checked rather than assumed.** `VCS-1764`, a Myanmar mangrove "blue carbon" reforestation project, prices at $42 against a ~$1–2 model-implied price. Verified against its raw Carbonmark record — it's a real, actively-traded credit, not a data error. Most likely explanation: blue carbon credits carry a genuine premium for biodiversity/community co-benefits that a 51-project, single-category comparable set has no other examples of. Treated as a probable artifact of a thin comparable set, not a confirmed pricing anomaly — see `docs/research_decisions_log.md`, Decision 7.
- **The pipeline itself is validated.** Every function has unit tests; the full pipeline was tested end-to-end against real data (not just synthetic fixtures) before this run, catching and fixing three real bugs (timezone handling, rank-deficient regression matrix, working-directory assumptions) — see Decisions 5–7 in the research log.

**Bottom line:** the infrastructure works and produces real, defensible output — but the *substantive* findings are provisional until the sample grows. Treat every classification in `data/processed/relative_value_scores_latest.csv` as a hypothesis worth re-checking next month, not a settled result.

## Data sources

| Source | What it provides | Access |
|---|---|---|
| [CarbonPlan OffsetsDB](https://github.com/carbonplan/offsets-db-data) | Project metadata, issuances, retirements across 7 registries | Free, public CSV/Parquet archive |
| [Carbonmark API](https://docs.carbonmark.com/) | Live per-project listing prices | Free sandbox API key |

No paid data sources are used. See `docs/research_decisions_log.md` for the full data source investigation and why paid providers (AlliedOffsets, MSCI) were ruled out.

**Known limitation:** there is no free historical carbon credit price time series available anywhere. This project builds a cross-sectional pricing model now, and begins logging Carbonmark price snapshots on an ongoing basis so a real backtest becomes possible once enough history accumulates. This is stated plainly rather than faking a backtest with data that doesn't exist.

## Repository structure

```
carbon-credit-quant/
├── data/
│   ├── raw/          # untouched downloads
│   ├── interim/       # partially cleaned checkpoints
│   └── processed/     # modelling-ready datasets
├── notebooks/          # exploration and analysis notebooks, numbered in build order
├── src/
│   ├── data/           # data acquisition and cleaning code
│   ├── database/       # SQLite schema and access code
│   ├── features/       # feature engineering
│   ├── models/         # pricing and comparable-credit models
│   ├── analysis/        # relative-value scoring and validation
│   └── visualization/  # chart generation
├── sql/                 # CREATE TABLE statements and example queries
├── tests/                # unit tests for pipeline functions
├── reports/              # generated research report and figures
└── docs/
    └── research_decisions_log.md   # every major modelling decision, alternatives considered, why
```

## Setup

```bash
pip install -r requirements.txt
```

Built and tested in Google Colab — no local environment required.

## Keeping prices up to date automatically

`.github/workflows/refresh_prices.yml` runs notebook 02 (pull live Carbonmark prices) then notebook 03 (re-model, re-score, rebuild the website) on a schedule, and commits the results back to the repo. This is how real price history accumulates over time toward an eventual backtest.

**Setup required (I can't do this part for you — it needs your GitHub account):**
1. Push this repo to GitHub (private is fine — Actions works on private repos).
2. Repo Settings → Secrets and variables → Actions → New repository secret → name it `CARBONMARK_API_KEY`, paste your real key as the value.
3. That's it — the workflow runs automatically on the schedule below, or manually anytime via the Actions tab → "Refresh Carbonmark prices..." → Run workflow.

**Default schedule:** every Monday at 06:00 UTC. To change it, edit the `cron:` line in `.github/workflows/refresh_prices.yml` — cron syntax is `minute hour day month weekday`, always UTC. Examples: `0 6 * * *` = daily at 6am UTC; `0 */6 * * *` = every 6 hours; `0 6 1,15 * *` = 1st and 15th of each month.

**Important honesty note:** I (Claude) can't run a persistent background process from this chat — there's no "always on" server here. What I've built is the actual automation infrastructure GitHub's own servers will execute once you push the repo and add the secret. Until you do that, nothing runs on a schedule.

## Setup: pushing this to GitHub and going live on Pages

**No terminal on your machine? Use GitHub Codespaces** — a full dev environment (with a real terminal) that runs in GitHub's cloud and opens in your browser. Nothing installs locally, and it comes with Git already authenticated. Free tier: 120 core-hours/month, far more than this one-time setup needs.

1. **Create the repo** — github.com → New repository → name it `carbon-credit-quant` → Private → **check "Add a README file"** (needed so Codespaces has an initial commit to attach to) → Create repository.
2. **Open a Codespace** — on the repo page, green Code button → Codespaces tab → Create codespace on main. Wait ~30-60 seconds.
3. **Upload the zip** — download `carbon-credit-quant-repo.zip` to your laptop normally first, then in the Codespace's Explorer panel, right-click the empty area below the file list → Upload... → select the zip.
4. **Extract, including hidden files** — open a terminal (Terminal menu → New Terminal) and run:
   ```bash
   unzip carbon-credit-quant-repo.zip -d /tmp/extract
   cp -r /tmp/extract/carbon-credit-quant/. .
   rm -rf carbon-credit-quant-repo.zip /tmp/extract
   ```
   The `.../. .` form specifically copies hidden folders like `.github/` — GitHub's plain drag-and-drop web uploader often silently drops these, which would break the automation, so this extraction method matters.
5. **Commit and push** — still in the terminal:
   ```bash
   git add .
   git commit -m "Initial commit: pipeline, notebooks, website, automation"
   git push
   ```
   No login prompt — Codespaces is already authenticated to your account.
6. **Add your Carbonmark API key as a secret** — repo page → Settings → Secrets and variables → Actions → New repository secret → name `CARBONMARK_API_KEY` → paste your real key → Add secret.
7. **Turn on GitHub Pages, sourced from Actions** — Settings → Pages → under "Build and deployment," set Source to **GitHub Actions** (not "Deploy from a branch" — the dashboard lives at `reports/website/`, not the repo root).
8. **Trigger the first deploy manually** — Actions tab → "Deploy dashboard to GitHub Pages" → Run workflow. After ~1 minute, live at `https://YOUR-USERNAME.github.io/carbon-credit-quant/`.
9. **Trigger the first price refresh manually too** — Actions tab → "Refresh Carbonmark prices and relative-value scores" → Run workflow. This re-triggers step 8's deploy automatically with fresh data.

After this, both run themselves: prices refresh weekly, the live dashboard updates automatically. You can delete the Codespace once step 5 succeeds — it's done its job.

*(If you later get access to a personal computer with git installed, the equivalent local commands are the standard `git init && git add . && git commit -m "..." && git remote add origin <url> && git push -u origin main` — same idea, just run locally instead of in a Codespace.)*

## How to run

**Upload the whole `carbon-credit-quant/` folder to Colab, not just individual notebook files** — notebooks 02 and 03 import from `src/` and read/write shared `data/` paths, so they need the full repo structure present together. (Notebook 01 is the exception — it's self-contained and can be run standalone.)

Notebooks are numbered in the order they should be run:

1. **`01_data_exploration.ipynb`** — download and explore OffsetsDB project/credit data. No setup needed.
2. **`02_carbonmark_prices.ipynb`** — pull live listing prices from Carbonmark. **Requires a free Carbonmark sandbox API key** (get one at the [Developer Dashboard](https://docs.carbonmark.com/carbonmark-api/quickstart)) — paste it into the notebook where indicated. Re-run this periodically to build price history over time.
3. **`03_pricing_model.ipynb`** — the full pipeline: cleans data, loads it into SQLite, builds features, fits the hedonic regression and comparable-credit models, scores relative value, and generates visualizations. Requires notebook 02 to have been run at least once.

Every function this pipeline uses has unit tests in `tests/` and was tested end to end against real OffsetsDB data before being delivered — including catching and fixing two real bugs (a timezone-handling error and a rank-deficient regression matrix from high-cardinality categories) rather than shipping untested code. See `docs/research_decisions_log.md` for what was found and how it was fixed.

## Limitations

Documented as they're discovered — see `docs/research_decisions_log.md`. The main one so far: no free historical price panel exists for voluntary carbon credits, so backtesting is a forward-looking data collection effort, not a retrospective one.
