"""
SQLite database access layer.

Beginner-friendly notes:
- We use plain sqlite3 (built into Python) rather than an ORM (like SQLAlchemy)
  on purpose. An ORM adds a layer of abstraction that's worth learning later,
  but writing raw SQL first means you actually see and understand the queries
  running against your data.
- Every function here does ONE thing. That's not just style — it's what makes
  the pipeline debuggable. If loading projects fails, you know exactly which
  function to look at.
"""

import sqlite3
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

SCHEMA_PATH = Path(__file__).parent.parent.parent / "sql" / "schema.sql"


def create_database(db_path: str) -> sqlite3.Connection:
    """
    Create (or connect to) the SQLite database and apply the schema.
    Safe to call repeatedly — CREATE TABLE IF NOT EXISTS won't error on re-runs.
    """
    conn = sqlite3.connect(db_path)
    with open(SCHEMA_PATH) as f:
        schema_sql = f.read()
    conn.executescript(schema_sql)
    conn.commit()
    logger.info(f"Database ready at {db_path}")
    return conn


def load_registries(conn: sqlite3.Connection, registry_names: list[str]) -> None:
    """Insert any registry names not already present. Idempotent."""
    cur = conn.cursor()
    for name in registry_names:
        cur.execute(
            "INSERT OR IGNORE INTO registries (registry_name) VALUES (?)", (name,)
        )
    conn.commit()
    logger.info(f"Loaded {len(registry_names)} registry names (duplicates ignored)")


def get_registry_id_map(conn: sqlite3.Connection) -> dict:
    """Return {registry_name: registry_id} for use when inserting projects."""
    cur = conn.execute("SELECT registry_id, registry_name FROM registries")
    return {name: rid for rid, name in cur.fetchall()}


def load_projects(conn: sqlite3.Connection, projects_df) -> int:
    """
    Load a cleaned projects DataFrame into the projects table.
    Expects columns matching the schema: project_id, name, registry (name, not id —
    this function looks up the id), country, category, project_type, status,
    is_compliance, first_issuance_at, first_retirement_at, total_issued,
    total_retired, proponent, project_url.
    Returns the number of rows inserted.
    """
    registry_map = get_registry_id_map(conn)
    cur = conn.cursor()
    rows_inserted = 0
    for _, row in projects_df.iterrows():
        registry_id = registry_map.get(row["registry"])
        if registry_id is None:
            logger.warning(f"Unknown registry '{row['registry']}' for project {row['project_id']} — skipping")
            continue
        cur.execute(
            """
            INSERT OR REPLACE INTO projects
            (project_id, name, registry_id, country, category, project_type, status,
             is_compliance, first_issuance_at, first_retirement_at, total_issued,
             total_retired, proponent, project_url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["project_id"], row.get("name"), registry_id, row.get("country"),
                row.get("category"), row.get("project_type"), row.get("status"),
                int(row.get("is_compliance", 0)) if row.get("is_compliance") is not None else None,
                row.get("first_issuance_at"), row.get("first_retirement_at"),
                row.get("total_issued"), row.get("total_retired"),
                row.get("proponent"), row.get("project_url"),
            ),
        )
        rows_inserted += 1
    conn.commit()
    logger.info(f"Loaded {rows_inserted} projects")
    return rows_inserted


def load_credit_transactions(conn: sqlite3.Connection, credits_df) -> int:
    """
    Load a cleaned credits DataFrame into credit_transactions.
    Expects columns: project_id, transaction_type, quantity, vintage,
    transaction_date, retirement_beneficiary, retirement_reason.
    """
    cur = conn.cursor()
    rows = [
        (
            row["project_id"], row["transaction_type"], row.get("quantity"),
            row.get("vintage"), row.get("transaction_date"),
            row.get("retirement_beneficiary"), row.get("retirement_reason"),
        )
        for _, row in credits_df.iterrows()
    ]
    cur.executemany(
        """
        INSERT INTO credit_transactions
        (project_id, transaction_type, quantity, vintage, transaction_date,
         retirement_beneficiary, retirement_reason)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    conn.commit()
    logger.info(f"Loaded {len(rows)} credit transactions")
    return len(rows)


def load_price_observations(conn: sqlite3.Connection, prices_df) -> int:
    """
    Load a prices DataFrame (from the Carbonmark pull) into price_observations.
    Expects columns: project_id, source, price_usd, currency, listing_type,
    observed_at, raw_response_json.
    """
    cur = conn.cursor()
    rows = [
        (
            row["project_id"], row.get("source", "carbonmark"), row["price_usd"],
            row.get("currency", "USD"), row.get("listing_type"),
            row["observed_at"], row.get("raw_response_json"),
        )
        for _, row in prices_df.iterrows()
    ]
    cur.executemany(
        """
        INSERT INTO price_observations
        (project_id, source, price_usd, currency, listing_type, observed_at, raw_response_json)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    conn.commit()
    logger.info(f"Loaded {len(rows)} price observations")
    return len(rows)


def query_projects_with_latest_price(conn: sqlite3.Connection):
    """
    Return a DataFrame joining each project to its most recent price observation.
    This is the core query the feature engineering step builds on.
    """
    import pandas as pd

    query = """
        SELECT
            p.project_id, p.name, r.registry_name AS registry, p.country,
            p.category, p.project_type, p.status, p.total_issued, p.total_retired,
            p.first_issuance_at,
            po.price_usd, po.observed_at
        FROM projects p
        JOIN registries r ON p.registry_id = r.registry_id
        JOIN (
            SELECT project_id, price_usd, observed_at,
                   ROW_NUMBER() OVER (PARTITION BY project_id ORDER BY observed_at DESC) AS rn
            FROM price_observations
        ) po ON p.project_id = po.project_id AND po.rn = 1
    """
    return pd.read_sql_query(query, conn)
