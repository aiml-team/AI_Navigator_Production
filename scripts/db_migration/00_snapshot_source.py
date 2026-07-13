"""
00_snapshot_source.py
━━━━━━━━━━━━━━━━━━━━━
Take a read-only snapshot of source DB row counts.
Writes JSON to source_snapshot.json so 04_verify.py can prove
nothing in source was touched by the migration.

READ-ONLY. Never modifies source.
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_ROOT / ".env")

import pyodbc  # noqa: E402

SOURCE = "AI-Navigator"
OUT = Path(__file__).parent / "source_snapshot.json"


def _connect(db: str) -> pyodbc.Connection:
    srv = os.getenv("AZURE_SQL_SERVER", "")
    u   = os.getenv("AZURE_SQL_USERNAME", "")
    p   = os.getenv("AZURE_SQL_PASSWORD", "")
    cs = (
        "DRIVER={ODBC Driver 18 for SQL Server};"
        f"SERVER={srv};DATABASE={db};UID={u};PWD={p};"
        "Encrypt=yes;TrustServerCertificate=no;Connection Timeout=15;"
    )
    return pyodbc.connect(cs)


def main() -> None:
    c = _connect(SOURCE); cur = c.cursor()
    cur.execute("""
        SELECT s.name + '.' + t.name AS full_name,
               (SELECT SUM(p.rows) FROM sys.partitions p
                 WHERE p.object_id = t.object_id AND p.index_id IN (0,1)) AS row_count
        FROM sys.tables t
        JOIN sys.schemas s ON s.schema_id = t.schema_id
        WHERE t.type = 'U'
        ORDER BY full_name
    """)
    counts = {r[0]: (r[1] or 0) for r in cur.fetchall()}
    total = sum(counts.values())
    payload = {
        "database": SOURCE,
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "total_rows": total,
        "table_counts": counts,
    }
    OUT.write_text(json.dumps(payload, indent=2))
    print(f"Snapshot: {len(counts)} tables, {total} total rows")
    print(f"Written: {OUT}")
    c.close()


if __name__ == "__main__":
    main()
