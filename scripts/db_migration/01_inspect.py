"""
01_inspect.py
━━━━━━━━━━━━━
Read-only introspection of both databases.

- Confirms AI-Navigator-Prod exists and is (expected) empty.
- Lists every user table in AI-Navigator (source) with row counts.

DOES NOT MODIFY ANY DATABASE. Safe to run repeatedly.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# load .env from project root (parent of scripts/db_migration)
_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_ROOT / ".env")

import pyodbc  # noqa: E402


def _connect(db_name: str) -> pyodbc.Connection:
    srv = os.getenv("AZURE_SQL_SERVER", "")
    u   = os.getenv("AZURE_SQL_USERNAME", "")
    p   = os.getenv("AZURE_SQL_PASSWORD", "")
    cs = (
        "DRIVER={ODBC Driver 18 for SQL Server};"
        f"SERVER={srv};DATABASE={db_name};UID={u};PWD={p};"
        "Encrypt=yes;TrustServerCertificate=no;Connection Timeout=15;"
    )
    return pyodbc.connect(cs)


def check_target(db: str = "AI-Navigator-Prod") -> int:
    print(f"\n══ Target check: {db} ══")
    try:
        c = _connect(db)
    except Exception as e:
        print(f"  ❌ Cannot connect: {e}")
        return -1
    cur = c.cursor()
    cur.execute("SELECT DB_NAME(), SUSER_NAME()")
    dbname, user = cur.fetchone()
    print(f"  ✅ Connected — DB={dbname}  User={user}")
    cur.execute("SELECT COUNT(*) FROM sys.tables WHERE type='U'")
    n = cur.fetchone()[0]
    print(f"  User tables present: {n}")
    if n > 0:
        cur.execute("SELECT name FROM sys.tables WHERE type='U' ORDER BY name")
        for r in cur.fetchall():
            print(f"    · {r[0]}")
    c.close()
    return n


def list_source(db: str = "AI-Navigator") -> list[dict]:
    print(f"\n══ Source inventory: {db} ══")
    c = _connect(db)
    cur = c.cursor()
    cur.execute("""
        SELECT s.name AS schema_name, t.name AS table_name,
               (SELECT SUM(p.rows) FROM sys.partitions p
                 WHERE p.object_id = t.object_id AND p.index_id IN (0,1)) AS row_count
        FROM sys.tables t
        JOIN sys.schemas s ON s.schema_id = t.schema_id
        WHERE t.type = 'U'
        ORDER BY s.name, t.name
    """)
    rows = cur.fetchall()
    out = []
    for r in rows:
        out.append({
            "schema": r.schema_name,
            "name": r.table_name,
            "rows": r.row_count if r.row_count is not None else 0,
        })
    total = sum(t["rows"] for t in out)
    print(f"  Total user tables: {len(out)}")
    print(f"  Total rows: {total}")
    print()
    print(f"  {'Schema':<12} {'Table':<40} {'Rows':>10}")
    print(f"  {'-'*12} {'-'*40} {'-'*10}")
    for t in out:
        print(f"  {t['schema']:<12} {t['name']:<40} {t['rows']:>10}")
    c.close()
    return out


if __name__ == "__main__":
    check_target()
    list_source()
    print("\n(Read-only. Nothing was modified.)")
