-- Carbon Credit Relative-Value Model — SQLite schema
-- Design notes: this schema stores one row per project, one row per issuance/retirement
-- transaction, and one row per price observation, so we can support both the
-- cross-sectional pricing model now and a time-series backtest later once price
-- history accumulates. See docs/research_decisions_log.md for why this shape.

CREATE TABLE IF NOT EXISTS registries (
    registry_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    registry_name   TEXT UNIQUE NOT NULL   -- e.g. 'verra', 'gold-standard'
);

CREATE TABLE IF NOT EXISTS projects (
    project_id              TEXT PRIMARY KEY,   -- e.g. 'VCS-191', matches OffsetsDB and Carbonmark
    name                     TEXT,
    registry_id              INTEGER NOT NULL,
    country                  TEXT,
    category                 TEXT,               -- e.g. 'forestry-land-use', 'renewable-energy'
    project_type              TEXT,
    status                    TEXT,               -- 'listed', 'registered', 'completed', 'unknown', etc.
    is_compliance             INTEGER,            -- 0/1, from OffsetsDB
    first_issuance_at         TEXT,               -- ISO date
    first_retirement_at        TEXT,
    total_issued               REAL,
    total_retired               REAL,
    proponent                  TEXT,
    project_url                TEXT,
    FOREIGN KEY (registry_id) REFERENCES registries(registry_id)
);

CREATE INDEX IF NOT EXISTS idx_projects_registry ON projects(registry_id);
CREATE INDEX IF NOT EXISTS idx_projects_type ON projects(project_type);
CREATE INDEX IF NOT EXISTS idx_projects_country ON projects(country);

CREATE TABLE IF NOT EXISTS credit_transactions (
    transaction_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id            TEXT NOT NULL,
    transaction_type       TEXT NOT NULL,   -- 'issuance' or 'retirement'
    quantity                REAL,
    vintage                  INTEGER,        -- year the emission reduction occurred
    transaction_date          TEXT,           -- ISO date
    retirement_beneficiary      TEXT,
    retirement_reason            TEXT,
    FOREIGN KEY (project_id) REFERENCES projects(project_id)
);

CREATE INDEX IF NOT EXISTS idx_credits_project ON credit_transactions(project_id);
CREATE INDEX IF NOT EXISTS idx_credits_vintage ON credit_transactions(vintage);
CREATE INDEX IF NOT EXISTS idx_credits_type ON credit_transactions(transaction_type);

-- Price observations: one row per snapshot of a listing. Designed so repeated
-- polling of Carbonmark over time builds a real time series in this same table
-- (observed_at differentiates snapshots) rather than needing a schema change later.
CREATE TABLE IF NOT EXISTS price_observations (
    price_obs_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id          TEXT NOT NULL,
    source                TEXT NOT NULL DEFAULT 'carbonmark',
    price_usd              REAL NOT NULL,
    currency                 TEXT DEFAULT 'USD',
    listing_type              TEXT,             -- 'listing' vs other Carbonmark price types
    observed_at                TEXT NOT NULL,    -- ISO datetime this snapshot was pulled
    raw_response_json            TEXT,           -- keep the raw API payload for auditability
    FOREIGN KEY (project_id) REFERENCES projects(project_id)
);

CREATE INDEX IF NOT EXISTS idx_prices_project ON price_observations(project_id);
CREATE INDEX IF NOT EXISTS idx_prices_observed_at ON price_observations(observed_at);

-- Output of the relative-value scoring step (Phase 12). One row per project per
-- scoring run, so re-running the model over time doesn't overwrite prior scores.
CREATE TABLE IF NOT EXISTS relative_value_scores (
    score_id             INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id             TEXT NOT NULL,
    run_at                   TEXT NOT NULL,
    observed_price             REAL,
    hedonic_model_price          REAL,
    comparable_model_price         REAL,
    residual                        REAL,
    residual_zscore                  REAL,
    liquidity_proxy                    REAL,
    classification                       TEXT,   -- 'strong undervaluation' ... 'strong overvaluation'
    FOREIGN KEY (project_id) REFERENCES projects(project_id)
);

CREATE INDEX IF NOT EXISTS idx_scores_project ON relative_value_scores(project_id);
CREATE INDEX IF NOT EXISTS idx_scores_run ON relative_value_scores(run_at);

-- Example queries -----------------------------------------------------------

-- All Verra projects with at least one price observation:
-- SELECT p.project_id, p.name, po.price_usd, po.observed_at
-- FROM projects p
-- JOIN registries r ON p.registry_id = r.registry_id
-- JOIN price_observations po ON p.project_id = po.project_id
-- WHERE r.registry_name = 'verra'
-- ORDER BY po.observed_at DESC;

-- Most recent relative-value ranking:
-- SELECT project_id, classification, residual_zscore
-- FROM relative_value_scores
-- WHERE run_at = (SELECT MAX(run_at) FROM relative_value_scores)
-- ORDER BY residual_zscore DESC;
