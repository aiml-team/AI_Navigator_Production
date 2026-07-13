"""
03c_drop_drifted.py
━━━━━━━━━━━━━━━━━━━
Drops the 13 drifted tables in AI-Navigator-Prod so they can be recreated
cleanly from generated_schema.sql via 03_apply.py.

The 13 tables were auto-created by the app's init_db()/init_navigator_tables()
routines and do NOT match the true source schema (missing columns like
audit_log.row_num, UserDefaultRole.tool_recommendation; wrong column widths).

We keep admin_users and users because those were created directly from
source DDL by 03b_apply_missing.py and match source exactly.

SAFETY GUARDS:
  1. TARGET_DB locked to "AI-Navigator-Prod".
  2. FORBIDDEN_DBS blocks source + system DBs.
  3. Hard-coded list of exactly 13 table names to drop.
  4. If any OTHER table exists that isn't in the drop list AND isn't in
     the keep list, we abort (unknown state).
  5. Interactive DROP confirmation unless --yes passed.

Read-only against source DB. Never touches AI-Navigator.
"""
import argparse
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_ROOT / ".env")

import pyodbc  # noqa: E402


TARGET_DB     = "AI-Navigator-Prod"
FORBIDDEN_DBS = {"AI-Navigator", "master", "tempdb", "msdb", "model"}

TABLES_TO_DROP = [
    "audit_log",
    "feedback",
    "NavigatorAdmins",
    "NavigatorUsers",
    "prompt_versions",
    "registered_tools",
    "scenario_suggestions",
    "scenarios",
    "technical_feedbacks",
    "tool_change_log",
    "user_saved_scenarios",
    "UserDefaultRole",
    "UserToolAccess",
]
TABLES_TO_KEEP = ["admin_users", "users"]


def _connect(db_name: str) -> pyodbc.Connection:
    if db_name != TARGET_DB:
        raise RuntimeError(
            f"REFUSED: drop script may only connect to {TARGET_DB!r}, not {db_name!r}."
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


def _existing_tables(cur) -> set[str]:
    cur.execute("SELECT name FROM sys.tables WHERE type='U'")
    return {r[0] for r in cur.fetchall()}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--yes", action="store_true",
                    help="Drop without interactive confirmation")
    args = ap.parse_args()

    print(f"Target: {TARGET_DB}")
    print(f"Tables to DROP ({len(TABLES_TO_DROP)}): {TABLES_TO_DROP}")
    print(f"Tables to KEEP ({len(TABLES_TO_KEEP)}): {TABLES_TO_KEEP}")

    conn = _connect(TARGET_DB)
    cur = conn.cursor()

    cur.execute("SELECT DB_NAME()")
    dbname = cur.fetchone()[0]
    if dbname != TARGET_DB:
        raise RuntimeError(
            f"REFUSED: connected DB is {dbname!r}, expected {TARGET_DB!r}."
        )

    existing = _existing_tables(cur)
    print(f"\nCurrent target has {len(existing)} table(s): {sorted(existing)}")

    # Sanity: refuse if there are unexpected tables
    known = set(TABLES_TO_DROP) | set(TABLES_TO_KEEP)
    unexpected = existing - known
    if unexpected:
        print(f"❌ REFUSED: target has unexpected tables: {sorted(unexpected)}")
        print("   Investigate before running drop.")
        return 1

    # Which of the drop list actually exist?
    to_drop_now = [t for t in TABLES_TO_DROP if t in existing]
    already_gone = [t for t in TABLES_TO_DROP if t not in existing]
    if already_gone:
        print(f"  (Already gone, will skip: {already_gone})")

    if not to_drop_now:
        print("Nothing to drop. Exiting.")
        return 0

    print(f"\nWill DROP: {to_drop_now}")
    print(f"Will KEEP: {[t for t in TABLES_TO_KEEP if t in existing]}")

    if not args.yes:
        ans = input("Type 'DROP' to proceed (anything else aborts): ").strip()
        if ans != "DROP":
            print("Aborted by user.")
            return 1

    print(f"\nDropping tables in {TARGET_DB}…")
    dropped = 0
    for name in to_drop_now:
        try:
            cur.execute(f"DROP TABLE [dbo].[{name}]")
            conn.commit()
            dropped += 1
            print(f"  ✅  DROP TABLE dbo.{name}")
        except Exception as e:
            conn.rollback()
            print(f"  ❌  FAILED to drop dbo.{name}: {e}")
            print(f"\nStopped after {dropped} successful drop(s).")
            return 1

    after = _existing_tables(cur)
    print(f"\n✅ Done. Target now has {len(after)} tables: {sorted(after)}")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
