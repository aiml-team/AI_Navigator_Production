"""
03_apply.py
━━━━━━━━━━━
Applies generated_schema.sql to the target database.

SAFETY GUARDS (hardcoded, cannot be bypassed via env vars):
  1. TARGET_DB is fixed to "AI-Navigator-Prod". Cannot be overridden.
  2. FORBIDDEN_DBS blocks any accidental connection to the source
     ("AI-Navigator", "master", "tempdb", "msdb", "model").
  3. Target must have ZERO user tables before applying.
     (Refuses to touch a DB that already contains tables.)
  4. Each CREATE TABLE / CREATE INDEX / ALTER TABLE runs in its OWN
     transaction. On error, that statement rolls back and we abort.
  5. Prints a plan and waits for interactive confirmation unless
     --yes is passed.

Usage:
    python scripts/db_migration/03_apply.py            # dry-run + confirm
    python scripts/db_migration/03_apply.py --yes      # apply without prompt

Read-only against source DB. Never touches AI-Navigator.
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


TARGET_DB     = "AI-Navigator-Prod"          # locked
FORBIDDEN_DBS = {"AI-Navigator", "master", "tempdb", "msdb", "model"}
SCHEMA_FILE   = Path(__file__).parent / "generated_schema.sql"


def _connect(db_name: str) -> pyodbc.Connection:
    if db_name != TARGET_DB:
        raise RuntimeError(
            f"REFUSED: apply script may only connect to {TARGET_DB!r}, "
            f"not {db_name!r}."
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
    """
    Split the schema file into individual DDL statements.
    Our generator ends each statement with ';' on its own or trailing.
    We rely on that: no procedures / blocks with embedded semicolons here.
    """
    # Strip comments (both /* */ and -- lines).
    text = re.sub(r"/\*.*?\*/", "", sql_text, flags=re.DOTALL)
    text = re.sub(r"(?m)^--[^\n]*$", "", text)
    parts = [p.strip() for p in text.split(";")]
    return [p for p in parts if p]


def _target_is_empty(cur) -> tuple[bool, list[str]]:
    cur.execute("SELECT name FROM sys.tables WHERE type='U' ORDER BY name")
    names = [r[0] for r in cur.fetchall()]
    return (len(names) == 0), names


def _plan(statements: list[str]) -> None:
    kinds = {"CREATE TABLE": 0, "CREATE INDEX": 0, "ALTER TABLE": 0, "OTHER": 0}
    for s in statements:
        head = s.split(None, 3)
        head_norm = " ".join(head[:2]).upper() if len(head) >= 2 else "OTHER"
        head3 = " ".join(head[:3]).upper() if len(head) >= 3 else head_norm
        if head_norm == "CREATE TABLE":
            kinds["CREATE TABLE"] += 1
        elif "CREATE" in head_norm and "INDEX" in head3:
            kinds["CREATE INDEX"] += 1
        elif head_norm == "ALTER TABLE":
            kinds["ALTER TABLE"] += 1
        else:
            kinds["OTHER"] += 1
    print("Planned operations:")
    for k, v in kinds.items():
        if v:
            print(f"  {k}:  {v}")
    print(f"  TOTAL:        {sum(kinds.values())}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--yes", action="store_true",
                    help="Apply without interactive confirmation")
    args = ap.parse_args()

    if not SCHEMA_FILE.exists():
        print(f"❌ Schema file not found: {SCHEMA_FILE}")
        print("   Run 02_extract_ddl.py first.")
        return 2

    sql_text = SCHEMA_FILE.read_text()
    statements = _split_statements(sql_text)
    print(f"Loaded {len(statements)} DDL statement(s) from {SCHEMA_FILE.name}")
    _plan(statements)

    print(f"\nConnecting to TARGET: {TARGET_DB}")
    conn = _connect(TARGET_DB)
    cur = conn.cursor()

    # Extra runtime guard: verify server confirms which DB we're on.
    cur.execute("SELECT DB_NAME()")
    dbname = cur.fetchone()[0]
    if dbname != TARGET_DB:
        raise RuntimeError(
            f"REFUSED: connected DB is {dbname!r}, expected {TARGET_DB!r}."
        )

    empty, existing = _target_is_empty(cur)
    if not empty:
        print(f"\n❌ REFUSED: {TARGET_DB} already contains {len(existing)} user table(s):")
        for n in existing:
            print(f"    · {n}")
        print("\nApply is safe only against an EMPTY target. Aborting.")
        return 1

    if not args.yes:
        print(f"\nAbout to apply {len(statements)} statement(s) to {TARGET_DB}.")
        ans = input("Type 'APPLY' to proceed (anything else aborts): ").strip()
        if ans != "APPLY":
            print("Aborted by user.")
            return 1

    print(f"\nApplying to {TARGET_DB}…")
    applied = 0
    for i, stmt in enumerate(statements, 1):
        preview = " ".join(stmt.split())[:80]
        try:
            cur.execute(stmt)
            conn.commit()
            applied += 1
            print(f"  [{i:2d}/{len(statements)}] ✅  {preview}…")
        except Exception as e:
            conn.rollback()
            print(f"  [{i:2d}/{len(statements)}] ❌  FAILED — {e}")
            print("  Statement was:")
            print("  " + "\n  ".join(stmt.splitlines()))
            print(f"\nStopped after {applied} successful statement(s).")
            print("Target DB left in partial state — you may want to clean it up before retry.")
            return 1

    # Post-check: count tables created
    cur.execute("SELECT COUNT(*) FROM sys.tables WHERE type='U'")
    ntables = cur.fetchone()[0]
    print(f"\n✅ Done. {applied}/{len(statements)} statements applied. Tables in {TARGET_DB}: {ntables}")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
