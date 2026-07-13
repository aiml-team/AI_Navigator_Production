"""
03b_apply_missing.py
━━━━━━━━━━━━━━━━━━━━
Applies ONLY the missing tables (admin_users, users) to AI-Navigator-Prod.

Context: AI-Navigator-Prod was populated with 13 of the 15 tables by the
app's auto-init routines (main.py → init_db / init_navigator_tables) when
the app was started against it earlier. The two tables NOT auto-created
by app startup are `admin_users` and `users`. This script creates only
those two, using DDL extracted from the source DB.

SAFETY GUARDS (identical to 03_apply.py):
  1. TARGET_DB locked to "AI-Navigator-Prod".
  2. FORBIDDEN_DBS blocks source + system DBs.
  3. Refuses to run if either target table already exists.
  4. Per-statement transactions.
  5. Interactive APPLY confirmation unless --yes passed.

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


TARGET_DB     = "AI-Navigator-Prod"          # locked
FORBIDDEN_DBS = {"AI-Navigator", "master", "tempdb", "msdb", "model"}
TABLES_TO_CREATE = ["admin_users", "users"]

# DDL copied verbatim from generated_schema.sql (lines 10-21 and 205-216).
DDL_ADMIN_USERS = """
CREATE TABLE [dbo].[admin_users] (
    [id] NVARCHAR(36) NOT NULL,
    [email] NVARCHAR(255) NOT NULL,
    [password_hash] NVARCHAR(255) NOT NULL,
    [full_name] NVARCHAR(255) NULL DEFAULT (''),
    [role] NVARCHAR(50) NULL DEFAULT ('admin'),
    [is_active] INT NULL DEFAULT ((1)),
    [created_at] NVARCHAR(50) NULL,
    [last_login] NVARCHAR(50) NULL,
    CONSTRAINT [PK__admin_us__3213E83FDA8DF879] PRIMARY KEY CLUSTERED ([id] ASC),
    CONSTRAINT [UQ__admin_us__AB6E616431103204] UNIQUE NONCLUSTERED ([email] ASC)
)
""".strip()

DDL_USERS = """
CREATE TABLE [dbo].[users] (
    [id] NVARCHAR(36) NOT NULL,
    [email] NVARCHAR(255) NOT NULL,
    [full_name] NVARCHAR(255) NULL DEFAULT (''),
    [role] NVARCHAR(255) NULL DEFAULT ('general'),
    [department] NVARCHAR(255) NULL DEFAULT (''),
    [is_active] INT NULL DEFAULT ((1)),
    [created_at] NVARCHAR(50) NULL,
    [last_login] NVARCHAR(50) NULL,
    CONSTRAINT [PK__users__3213E83FB8AADDCC] PRIMARY KEY CLUSTERED ([id] ASC),
    CONSTRAINT [UQ__users__AB6E616413321ECD] UNIQUE NONCLUSTERED ([email] ASC)
)
""".strip()

STATEMENTS = [
    ("admin_users", DDL_ADMIN_USERS),
    ("users",       DDL_USERS),
]


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


def _existing_tables(cur) -> set[str]:
    cur.execute("SELECT name FROM sys.tables WHERE type='U'")
    return {r[0] for r in cur.fetchall()}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--yes", action="store_true",
                    help="Apply without interactive confirmation")
    args = ap.parse_args()

    print(f"Target: {TARGET_DB}")
    print(f"Tables to create: {TABLES_TO_CREATE}")

    conn = _connect(TARGET_DB)
    cur = conn.cursor()

    # Runtime guard: server confirms DB_NAME.
    cur.execute("SELECT DB_NAME()")
    dbname = cur.fetchone()[0]
    if dbname != TARGET_DB:
        raise RuntimeError(
            f"REFUSED: connected DB is {dbname!r}, expected {TARGET_DB!r}."
        )

    existing = _existing_tables(cur)
    print(f"\nCurrent target has {len(existing)} table(s).")

    conflicts = [t for t in TABLES_TO_CREATE if t in existing]
    if conflicts:
        print(f"❌ REFUSED: these tables already exist in target: {conflicts}")
        print("   Nothing to do — target already has them.")
        return 1

    missing_check = [t for t in TABLES_TO_CREATE if t not in existing]
    print(f"Will create: {missing_check}")

    if not args.yes:
        ans = input("Type 'APPLY' to proceed (anything else aborts): ").strip()
        if ans != "APPLY":
            print("Aborted by user.")
            return 1

    print(f"\nApplying to {TARGET_DB}…")
    applied = 0
    for name, stmt in STATEMENTS:
        try:
            cur.execute(stmt)
            conn.commit()
            applied += 1
            print(f"  ✅  CREATE TABLE dbo.{name}")
        except Exception as e:
            conn.rollback()
            print(f"  ❌  FAILED to create dbo.{name}: {e}")
            print("  Statement was:")
            print("  " + "\n  ".join(stmt.splitlines()))
            print(f"\nStopped after {applied} successful statement(s).")
            return 1

    # Post-check.
    after = _existing_tables(cur)
    print(f"\n✅ Done. Target now has {len(after)} tables.")
    for t in TABLES_TO_CREATE:
        marker = "✅" if t in after else "❌"
        print(f"  {marker} {t}")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
