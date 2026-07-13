"""
03d_apply_remaining.py
━━━━━━━━━━━━━━━━━━━━━━
Applies CREATE TABLE statements from generated_schema.sql to
AI-Navigator-Prod, SKIPPING any table that already exists.

Used after 03c_drop_drifted.py has removed the 13 drifted tables.
The remaining 2 tables (admin_users, users) were created cleanly by
03b_apply_missing.py, so we skip them.

SAFETY GUARDS (same as 03_apply.py):
  1. TARGET_DB locked to "AI-Navigator-Prod".
  2. FORBIDDEN_DBS blocks source + system DBs.
  3. Skips statements for already-existing tables.
  4. Per-statement transactions.
  5. Interactive APPLY confirmation unless --yes passed.
"""
import argparse
import os
import re
import sys
from pathlib import Path
from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_ROOT / ".env")

import pyodbc  # noqa: E402


TARGET_DB     = "AI-Navigator-Prod"
FORBIDDEN_DBS = {"AI-Navigator", "master", "tempdb", "msdb", "model"}
SCHEMA_FILE   = Path(__file__).parent / "generated_schema.sql"


def _connect(db_name: str) -> pyodbc.Connection:
    if db_name != TARGET_DB:
        raise RuntimeError(
            f"REFUSED: apply script may only connect to {TARGET_DB!r}, not {db_name!r}."
        )
    if db_name in FORBIDDEN_DBS:
        raise RuntimeError(f"REFUSED: {db_name!r} is on the forbidden list.")
    srv = os.getenv("AZURE_SQL_SERVER", "")
    u   = os.getenv("AZURE_SQL_USERNAME", "")
    p   = os.getenv("AZURE_SQL_PASSWORD", "")
    cs = (
        "DRIVER={ODBC Driver 18 for SQL Server};"
        f"SERVER={srv};DATABASE={db_name};UID={u};PWD={p};"
        "Encrypt=yes;TrustServerCertificate=no;Connection Timeout=15;"
    )
    return pyodbc.connect(cs, autocommit=False)


def _split_statements(sql_text: str) -> list[str]:
    text = re.sub(r"/\*.*?\*/", "", sql_text, flags=re.DOTALL)
    text = re.sub(r"(?m)^--[^\n]*$", "", text)
    parts = [p.strip() for p in text.split(";")]
    return [p for p in parts if p]


def _extract_table_name(stmt: str) -> str | None:
    """Grab table name from CREATE TABLE [dbo].[name] or CREATE TABLE dbo.name."""
    m = re.search(
        r"CREATE\s+TABLE\s+(?:\[?dbo\]?\.)?\[?([A-Za-z_][A-Za-z0-9_]*)\]?",
        stmt, re.IGNORECASE,
    )
    return m.group(1) if m else None


def _existing_tables(cur) -> set[str]:
    cur.execute("SELECT name FROM sys.tables WHERE type='U'")
    return {r[0] for r in cur.fetchall()}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--yes", action="store_true",
                    help="Apply without interactive confirmation")
    args = ap.parse_args()

    if not SCHEMA_FILE.exists():
        print(f"❌ Schema file not found: {SCHEMA_FILE}")
        return 2

    sql_text = SCHEMA_FILE.read_text()
    statements = _split_statements(sql_text)
    print(f"Loaded {len(statements)} statement(s) from {SCHEMA_FILE.name}")

    conn = _connect(TARGET_DB)
    cur = conn.cursor()

    cur.execute("SELECT DB_NAME()")
    dbname = cur.fetchone()[0]
    if dbname != TARGET_DB:
        raise RuntimeError(
            f"REFUSED: connected DB is {dbname!r}, expected {TARGET_DB!r}."
        )

    existing = _existing_tables(cur)
    print(f"Target currently has {len(existing)} table(s): {sorted(existing)}")

    to_run = []
    to_skip = []
    for stmt in statements:
        tname = _extract_table_name(stmt)
        if tname is None:
            to_run.append((None, stmt))
        elif tname in existing:
            to_skip.append(tname)
        else:
            to_run.append((tname, stmt))

    print(f"\nWill CREATE ({len(to_run)}): {[t for t,_ in to_run if t]}")
    if to_skip:
        print(f"Will SKIP  ({len(to_skip)}): {to_skip}")

    if not to_run:
        print("Nothing to do.")
        return 0

    if not args.yes:
        ans = input("Type 'APPLY' to proceed (anything else aborts): ").strip()
        if ans != "APPLY":
            print("Aborted by user.")
            return 1

    print(f"\nApplying to {TARGET_DB}…")
    applied = 0
    for tname, stmt in to_run:
        label = f"dbo.{tname}" if tname else "(non-table stmt)"
        try:
            cur.execute(stmt)
            conn.commit()
            applied += 1
            print(f"  ✅  CREATE TABLE {label}")
        except Exception as e:
            conn.rollback()
            print(f"  ❌  FAILED {label}: {e}")
            print(f"\nStopped after {applied} successful statement(s).")
            return 1

    after = _existing_tables(cur)
    print(f"\n✅ Done. Target now has {len(after)} tables.")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
