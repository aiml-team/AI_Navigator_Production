"""
02_extract_ddl.py
━━━━━━━━━━━━━━━━━
Reads schema from AI-Navigator (source) and writes CREATE TABLE +
CREATE INDEX statements to scripts/db_migration/generated_schema.sql.

DOES NOT MODIFY ANY DATABASE. Read-only against source.

Coverage:
  • Columns: name, type, length/precision/scale, nullability, defaults,
             identity (IDENTITY(seed, incr)), computed column expressions
  • Primary keys (clustered/nonclustered)
  • Unique constraints
  • Foreign keys
  • Check constraints
  • Non-PK indexes (including included columns, filter predicates)

Not covered (rare in this codebase; will warn if encountered):
  • Triggers, views, stored procedures, user-defined types, sequences,
    partitioning, extended properties.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_ROOT / ".env")

import pyodbc  # noqa: E402


SOURCE_DB = "AI-Navigator"
OUT_PATH  = Path(__file__).parent / "generated_schema.sql"


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


def q(ident: str) -> str:
    return "[" + ident.replace("]", "]]") + "]"


def _get_tables(cur) -> list[dict]:
    cur.execute("""
        SELECT s.name AS schema_name, t.name AS table_name, t.object_id
        FROM sys.tables t
        JOIN sys.schemas s ON s.schema_id = t.schema_id
        WHERE t.type = 'U'
        ORDER BY s.name, t.name
    """)
    return [{"schema": r.schema_name, "name": r.table_name, "object_id": r.object_id}
            for r in cur.fetchall()]


def _get_columns(cur, object_id: int) -> list[dict]:
    cur.execute("""
        SELECT
            c.name                        AS col_name,
            c.column_id,
            t.name                        AS type_name,
            c.max_length,
            c.precision,
            c.scale,
            c.is_nullable,
            c.is_identity,
            CAST(ic.seed_value      AS BIGINT) AS seed_value,
            CAST(ic.increment_value AS BIGINT) AS increment_value,
            c.is_computed,
            cc.definition                 AS computed_definition,
            cc.is_persisted,
            dc.definition                 AS default_definition,
            dc.name                       AS default_name,
            c.collation_name
        FROM sys.columns c
        INNER JOIN sys.types t
            ON t.user_type_id = c.user_type_id
        LEFT JOIN sys.identity_columns ic
            ON ic.object_id = c.object_id AND ic.column_id = c.column_id
        LEFT JOIN sys.computed_columns cc
            ON cc.object_id = c.object_id AND cc.column_id = c.column_id
        LEFT JOIN sys.default_constraints dc
            ON dc.parent_object_id = c.object_id AND dc.parent_column_id = c.column_id
        WHERE c.object_id = ?
        ORDER BY c.column_id
    """, object_id)
    return [dict(zip([d[0] for d in cur.description], r)) for r in cur.fetchall()]


def _fmt_type(col: dict) -> str:
    t = col["type_name"].lower()
    ml = col["max_length"]
    p  = col["precision"]
    s  = col["scale"]

    if t in ("varchar", "char", "varbinary", "binary"):
        length = "MAX" if ml == -1 else str(ml)
        return f"{t.upper()}({length})"
    if t in ("nvarchar", "nchar"):
        # For nchar/nvarchar, max_length is in bytes (2 per char)
        length = "MAX" if ml == -1 else str(ml // 2)
        return f"{t.upper()}({length})"
    if t in ("decimal", "numeric"):
        return f"{t.upper()}({p},{s})"
    if t in ("float",):
        return f"FLOAT({p})" if p != 53 else "FLOAT"
    if t in ("datetime2", "time", "datetimeoffset"):
        return f"{t.upper()}({s})" if s != 7 else t.upper()
    return t.upper()


def _get_pk(cur, object_id: int) -> dict | None:
    cur.execute("""
        SELECT kc.name AS constraint_name, i.type_desc, i.index_id
        FROM sys.key_constraints kc
        JOIN sys.indexes i
          ON i.object_id = kc.parent_object_id AND i.index_id = kc.unique_index_id
        WHERE kc.parent_object_id = ? AND kc.type = 'PK'
    """, object_id)
    row = cur.fetchone()
    if not row:
        return None
    pk = {"name": row.constraint_name, "type": row.type_desc, "columns": []}
    cur.execute("""
        SELECT c.name, ic.is_descending_key
        FROM sys.index_columns ic
        JOIN sys.columns c
          ON c.object_id = ic.object_id AND c.column_id = ic.column_id
        WHERE ic.object_id = ? AND ic.index_id = ?
        ORDER BY ic.key_ordinal
    """, object_id, row.index_id)
    pk["columns"] = [(r[0], "DESC" if r[1] else "ASC") for r in cur.fetchall()]
    return pk


def _get_unique_constraints(cur, object_id: int) -> list[dict]:
    cur.execute("""
        SELECT kc.name AS constraint_name, i.index_id, i.type_desc
        FROM sys.key_constraints kc
        JOIN sys.indexes i
          ON i.object_id = kc.parent_object_id AND i.index_id = kc.unique_index_id
        WHERE kc.parent_object_id = ? AND kc.type = 'UQ'
    """, object_id)
    result = []
    for row in cur.fetchall():
        u = {"name": row.constraint_name, "type": row.type_desc, "columns": []}
        cur.execute("""
            SELECT c.name, ic.is_descending_key
            FROM sys.index_columns ic
            JOIN sys.columns c
              ON c.object_id = ic.object_id AND c.column_id = ic.column_id
            WHERE ic.object_id = ? AND ic.index_id = ?
            ORDER BY ic.key_ordinal
        """, object_id, row.index_id)
        u["columns"] = [(r[0], "DESC" if r[1] else "ASC") for r in cur.fetchall()]
        result.append(u)
    return result


def _get_indexes(cur, object_id: int) -> list[dict]:
    """Non-PK, non-UNIQUE-constraint indexes."""
    cur.execute("""
        SELECT i.name, i.index_id, i.type_desc, i.is_unique, i.filter_definition
        FROM sys.indexes i
        WHERE i.object_id = ?
          AND i.type IN (1, 2)             -- clustered / nonclustered (skip heap type 0)
          AND i.is_primary_key = 0
          AND i.is_unique_constraint = 0
          AND i.name IS NOT NULL
    """, object_id)
    idxs = []
    for row in cur.fetchall():
        idx = {"name": row.name, "type": row.type_desc, "unique": bool(row.is_unique),
               "filter": row.filter_definition, "key_cols": [], "included_cols": []}
        cur.execute("""
            SELECT c.name, ic.is_descending_key, ic.is_included_column
            FROM sys.index_columns ic
            JOIN sys.columns c
              ON c.object_id = ic.object_id AND c.column_id = ic.column_id
            WHERE ic.object_id = ? AND ic.index_id = ?
            ORDER BY ic.is_included_column, ic.key_ordinal, ic.index_column_id
        """, object_id, row.index_id)
        for r in cur.fetchall():
            entry = (r[0], "DESC" if r[1] else "ASC")
            if r[2]:
                idx["included_cols"].append(r[0])
            else:
                idx["key_cols"].append(entry)
        idxs.append(idx)
    return idxs


def _get_foreign_keys(cur, object_id: int) -> list[dict]:
    cur.execute("""
        SELECT
            fk.name             AS fk_name,
            fk.delete_referential_action_desc  AS on_delete,
            fk.update_referential_action_desc  AS on_update,
            OBJECT_SCHEMA_NAME(fk.referenced_object_id) AS ref_schema,
            OBJECT_NAME(fk.referenced_object_id)        AS ref_table
        FROM sys.foreign_keys fk
        WHERE fk.parent_object_id = ?
    """, object_id)
    result = []
    for row in cur.fetchall():
        fk = {
            "name": row.fk_name,
            "ref_schema": row.ref_schema,
            "ref_table": row.ref_table,
            "on_delete": row.on_delete,
            "on_update": row.on_update,
            "cols": [], "ref_cols": [],
        }
        cur.execute("""
            SELECT
                pc.name AS parent_col,
                rc.name AS ref_col
            FROM sys.foreign_key_columns fkc
            JOIN sys.columns pc
              ON pc.object_id = fkc.parent_object_id AND pc.column_id = fkc.parent_column_id
            JOIN sys.columns rc
              ON rc.object_id = fkc.referenced_object_id AND rc.column_id = fkc.referenced_column_id
            JOIN sys.foreign_keys fk ON fk.object_id = fkc.constraint_object_id
            WHERE fk.name = ?
            ORDER BY fkc.constraint_column_id
        """, row.fk_name)
        for c in cur.fetchall():
            fk["cols"].append(c.parent_col)
            fk["ref_cols"].append(c.ref_col)
        result.append(fk)
    return result


def _get_check_constraints(cur, object_id: int) -> list[dict]:
    cur.execute("""
        SELECT name, definition, is_not_trusted
        FROM sys.check_constraints
        WHERE parent_object_id = ?
    """, object_id)
    return [{"name": r[0], "definition": r[1]} for r in cur.fetchall()]


def _get_extras(cur) -> dict:
    """Warn about objects this script doesn't copy."""
    out = {}
    cur.execute("SELECT COUNT(*) FROM sys.triggers WHERE parent_class = 1")
    out["triggers"]   = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM sys.views WHERE is_ms_shipped = 0")
    out["views"]      = cur.fetchone()[0]
    cur.execute("""
        SELECT COUNT(*) FROM sys.objects
        WHERE is_ms_shipped = 0 AND type IN ('P','FN','TF','IF')
    """)
    out["procs_fns"]  = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM sys.types WHERE is_user_defined = 1")
    out["user_types"] = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM sys.sequences")
    out["sequences"]  = cur.fetchone()[0]
    return out


# ── build DDL ────────────────────────────────────────────────────────
def build_create_table(t: dict, cols: list[dict], pk: dict | None,
                        uqs: list[dict], checks: list[dict]) -> str:
    lines = [f"CREATE TABLE {q(t['schema'])}.{q(t['name'])} ("]
    col_lines = []
    for c in cols:
        parts = [f"    {q(c['col_name'])}"]
        if c["is_computed"]:
            persisted = " PERSISTED" if c.get("is_persisted") else ""
            parts.append(f"AS {c['computed_definition']}{persisted}")
        else:
            parts.append(_fmt_type(c))
            if c.get("collation_name") and c["type_name"].lower() in ("char","varchar","nchar","nvarchar","text","ntext"):
                # emit only when different from server default; skip for simplicity/safety
                pass
            if c["is_identity"]:
                seed = c["seed_value"] if c["seed_value"] is not None else 1
                incr = c["increment_value"] if c["increment_value"] is not None else 1
                parts.append(f"IDENTITY({seed},{incr})")
            parts.append("NULL" if c["is_nullable"] else "NOT NULL")
            if c.get("default_definition"):
                # keep default anonymous (no CONSTRAINT name) — safer across DBs
                parts.append(f"DEFAULT {c['default_definition']}")
        col_lines.append(" ".join(parts))

    if pk:
        cols_txt = ", ".join(f"{q(n)} {d}" for n, d in pk["columns"])
        clustered = "CLUSTERED" if pk["type"] == "CLUSTERED" else "NONCLUSTERED"
        col_lines.append(f"    CONSTRAINT {q(pk['name'])} PRIMARY KEY {clustered} ({cols_txt})")

    for u in uqs:
        cols_txt = ", ".join(f"{q(n)} {d}" for n, d in u["columns"])
        clustered = "CLUSTERED" if u["type"] == "CLUSTERED" else "NONCLUSTERED"
        col_lines.append(f"    CONSTRAINT {q(u['name'])} UNIQUE {clustered} ({cols_txt})")

    for ck in checks:
        col_lines.append(f"    CONSTRAINT {q(ck['name'])} CHECK {ck['definition']}")

    lines.append(",\n".join(col_lines))
    lines.append(");")
    return "\n".join(lines)


def build_create_indexes(t: dict, idxs: list[dict]) -> list[str]:
    out = []
    for idx in idxs:
        unique = "UNIQUE " if idx["unique"] else ""
        idx_type = "CLUSTERED" if idx["type"] == "CLUSTERED" else "NONCLUSTERED"
        keys = ", ".join(f"{q(n)} {d}" for n, d in idx["key_cols"])
        stmt = f"CREATE {unique}{idx_type} INDEX {q(idx['name'])} ON {q(t['schema'])}.{q(t['name'])} ({keys})"
        if idx["included_cols"]:
            stmt += " INCLUDE (" + ", ".join(q(c) for c in idx["included_cols"]) + ")"
        if idx["filter"]:
            stmt += f" WHERE {idx['filter']}"
        stmt += ";"
        out.append(stmt)
    return out


def build_add_fk(t: dict, fks: list[dict]) -> list[str]:
    out = []
    for fk in fks:
        cols = ", ".join(q(c) for c in fk["cols"])
        ref_cols = ", ".join(q(c) for c in fk["ref_cols"])
        stmt = (
            f"ALTER TABLE {q(t['schema'])}.{q(t['name'])} "
            f"ADD CONSTRAINT {q(fk['name'])} "
            f"FOREIGN KEY ({cols}) "
            f"REFERENCES {q(fk['ref_schema'])}.{q(fk['ref_table'])} ({ref_cols})"
        )
        # Only emit non-default actions; NO_ACTION is the default in SQL Server
        if fk["on_delete"] and fk["on_delete"] != "NO_ACTION":
            stmt += f" ON DELETE {fk['on_delete'].replace('_', ' ')}"
        if fk["on_update"] and fk["on_update"] != "NO_ACTION":
            stmt += f" ON UPDATE {fk['on_update'].replace('_', ' ')}"
        out.append(stmt + ";")
    return out


def main() -> None:
    print(f"Reading schema from source DB: {SOURCE_DB}")
    c = _connect(SOURCE_DB)
    cur = c.cursor()

    tables = _get_tables(cur)
    print(f"Tables: {len(tables)}")

    extras = _get_extras(cur)
    print("Extras present in source (NOT copied by this script):")
    for k, v in extras.items():
        marker = "⚠️ " if v > 0 else "  "
        print(f"  {marker}{k}: {v}")

    ddl_creates: list[str] = []
    ddl_indexes: list[str] = []
    ddl_fks: list[str] = []
    summary_lines: list[str] = []

    for t in tables:
        cols   = _get_columns(cur, t["object_id"])
        pk     = _get_pk(cur, t["object_id"])
        uqs    = _get_unique_constraints(cur, t["object_id"])
        idxs   = _get_indexes(cur, t["object_id"])
        fks    = _get_foreign_keys(cur, t["object_id"])
        checks = _get_check_constraints(cur, t["object_id"])

        ddl_creates.append(build_create_table(t, cols, pk, uqs, checks))
        ddl_indexes.extend(build_create_indexes(t, idxs))
        ddl_fks.extend(build_add_fk(t, fks))
        summary_lines.append(
            f"  [{t['schema']}].[{t['name']}]  "
            f"cols={len(cols)}  pk={'yes' if pk else 'no'}  "
            f"uq={len(uqs)}  ix={len(idxs)}  fk={len(fks)}  ck={len(checks)}"
        )

    c.close()

    print("\nSummary per table:")
    print("\n".join(summary_lines))

    header = (
        "/* ====================================================================\n"
        f"   Auto-generated DDL from source DB: {SOURCE_DB}\n"
        "   Target: AI-Navigator-Prod (created empty; safe to apply once).\n"
        "   Do not edit by hand; regenerate with scripts/db_migration/02_extract_ddl.py.\n"
        "   ==================================================================== */\n\n"
    )
    body = "\n\n-- ── Tables ─────────────────────────────────────────────\n"
    body += "\n\n".join(ddl_creates)
    if ddl_indexes:
        body += "\n\n-- ── Indexes ────────────────────────────────────────────\n"
        body += "\n".join(ddl_indexes)
    if ddl_fks:
        body += "\n\n-- ── Foreign keys ───────────────────────────────────────\n"
        body += "\n".join(ddl_fks)
    body += "\n"

    OUT_PATH.write_text(header + body)
    print(f"\n✅ Written: {OUT_PATH}  ({OUT_PATH.stat().st_size} bytes)")
    print("\nNothing was modified. Review the SQL, then run 03_apply.py to create the schema in AI-Navigator-Prod.")


if __name__ == "__main__":
    main()
