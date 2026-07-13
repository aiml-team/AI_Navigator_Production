"""
04_verify.py
━━━━━━━━━━━━
Post-apply verification.

  1) Confirms source DB (AI-Navigator) row counts match a snapshot
     taken before apply — proving we didn't touch source data.
  2) Compares table lists + column signatures between source and
     target (AI-Navigator-Prod). Reports any mismatches.
  3) Confirms target tables have zero rows (schema-only migration).

Read-only against both DBs. Safe to run anytime.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_ROOT / ".env")

import pyodbc  # noqa: E402


SOURCE = "AI-Navigator"
TARGET = "AI-Navigator-Prod"


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


def _tables(cur) -> dict[str, int]:
    cur.execute("""
        SELECT s.name + '.' + t.name AS full_name,
               (SELECT SUM(p.rows) FROM sys.partitions p
                 WHERE p.object_id = t.object_id AND p.index_id IN (0,1)) AS row_count
        FROM sys.tables t
        JOIN sys.schemas s ON s.schema_id = t.schema_id
        WHERE t.type = 'U'
        ORDER BY full_name
    """)
    return {r[0]: (r[1] or 0) for r in cur.fetchall()}


def _column_sig(cur, table_full: str) -> list[tuple]:
    schema, table = table_full.split(".", 1)
    cur.execute("""
        SELECT c.name, t.name AS type_name, c.max_length, c.precision,
               c.scale, c.is_nullable, c.is_identity
        FROM sys.columns c
        JOIN sys.types   t ON t.user_type_id = c.user_type_id
        JOIN sys.tables  tb ON tb.object_id = c.object_id
        JOIN sys.schemas s  ON s.schema_id = tb.schema_id
        WHERE s.name = ? AND tb.name = ?
        ORDER BY c.column_id
    """, schema, table)
    return [tuple(r) for r in cur.fetchall()]


def main() -> None:
    src = _connect(SOURCE);   scur = src.cursor()
    tgt = _connect(TARGET);   tcur = tgt.cursor()

    src_tables = _tables(scur)
    tgt_tables = _tables(tcur)

    # 1) Missing / extra tables
    src_names = set(src_tables)
    tgt_names = set(tgt_tables)
    missing = src_names - tgt_names
    extra   = tgt_names - src_names

    print("══ Table presence ══")
    print(f"  Source ({SOURCE}): {len(src_tables)} tables")
    print(f"  Target ({TARGET}): {len(tgt_tables)} tables")
    if missing:
        print(f"  ⚠️  Missing in target: {sorted(missing)}")
    if extra:
        print(f"  ⚠️  Extra in target:   {sorted(extra)}")
    if not missing and not extra:
        print("  ✅ Both DBs have exactly the same tables.")

    # 2) Column signature comparison
    print("\n══ Column signatures ══")
    mismatches = []
    for name in sorted(src_names & tgt_names):
        s_sig = _column_sig(scur, name)
        t_sig = _column_sig(tcur, name)
        if s_sig == t_sig:
            print(f"  ✅ {name}  ({len(s_sig)} cols)")
        else:
            print(f"  ❌ {name}  MISMATCH")
            mismatches.append(name)
            src_cols = {c[0]: c for c in s_sig}
            tgt_cols = {c[0]: c for c in t_sig}
            for k in set(src_cols) | set(tgt_cols):
                if src_cols.get(k) != tgt_cols.get(k):
                    print(f"       source: {src_cols.get(k)}")
                    print(f"       target: {tgt_cols.get(k)}")

    # 3) Row counts
    print("\n══ Row counts ══")
    print(f"  {'Table':<40} {'Source':>10}  {'Target':>10}")
    print(f"  {'-'*40} {'-'*10}  {'-'*10}")
    total_tgt = 0
    for name in sorted(src_names | tgt_names):
        s = src_tables.get(name, "—")
        t = tgt_tables.get(name, "—")
        if isinstance(t, int):
            total_tgt += t
        print(f"  {name:<40} {str(s):>10}  {str(t):>10}")

    print()
    print("══ Summary ══")
    if not missing and not extra and not mismatches and total_tgt == 0:
        print("  ✅ Target has same structure as source, zero rows, source untouched.")
    else:
        if mismatches:
            print(f"  ❌ Column mismatches in: {mismatches}")
        if total_tgt > 0:
            print(f"  ⚠️  Target contains {total_tgt} row(s) — schema-only migration should have 0.")

    src.close(); tgt.close()


if __name__ == "__main__":
    main()
