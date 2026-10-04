"""
Empty the database of all data and keep the schema.

Every table is cleared except `alembic_version` (so the database still knows
its schema is up to date) and the reference tables the migrations fill and
the app cannot run without (`forms`, `permissions`). Roles, societies, users
and everything else are recreated by the app: the first society registration
makes the roles, and `python -m app.utils.create_platform_admin` makes the
first Platform Admin.

This deletes real data and cannot be undone. TAKE A BACKUP FIRST:

    pg_dump "$DATABASE_URL" -Fc -f backup-$(date +%F).dump

Usage (from backend/, against whichever DATABASE_URL is in the environment):

    # 1. See what it would do. Deletes nothing.
    DATABASE_URL="..." python -m app.utils.reset_data

    # 2. Do it: name the database you mean, and say yes.
    DATABASE_URL="..." python -m app.utils.reset_data --confirm-db railway --yes

Postgres only in practice (one TRUNCATE ... CASCADE); SQLite is supported so
the safety checks can be tested.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

# Kept as they are: the migration bookkeeping, and the reference data the
# migrations insert (verified on a freshly migrated database: these are the only
# tables that hold rows). A migration that seeds another table must add it here.
KEEP_TABLES = frozenset({"alembic_version", "forms", "permissions"})


def tables_to_clear(engine: Engine) -> list:
    return sorted(t for t in inspect(engine).get_table_names() if t not in KEEP_TABLES)


def row_counts(engine: Engine, tables) -> dict:
    with engine.connect() as conn:
        return {t: conn.execute(text(f'SELECT COUNT(*) FROM "{t}"')).scalar() for t in tables}


def _where(engine: Engine) -> str:
    url = engine.url
    return f"{url.get_backend_name()} database '{url.database}' on {url.host or 'local file'}"


def reset(engine: Engine, confirm_db=None, yes: bool = False, out=print) -> bool:
    """Clear the data. Returns True if it deleted anything; False for a dry run
    (nothing confirmed) — it raises SystemExit if the confirmation is wrong."""
    tables = tables_to_clear(engine)
    counts = row_counts(engine, tables)
    holding = {t: n for t, n in counts.items() if n}

    out(f"Target: {_where(engine)}")
    out(f"Kept as they are: {', '.join(sorted(KEEP_TABLES))}")
    out(f"To be cleared: {len(tables)} tables; {sum(holding.values())} rows in {len(holding)} of them")
    for t, n in sorted(holding.items(), key=lambda kv: -kv[1])[:15]:
        out(f"    {t}: {n}")
    if len(holding) > 15:
        out(f"    … and {len(holding) - 15} more tables")

    if not yes and confirm_db is None:
        out("\nDry run — nothing was deleted. To delete, add:  --confirm-db "
            f"{engine.url.database} --yes")
        return False
    if confirm_db != engine.url.database:
        raise SystemExit(
            f"Refusing: --confirm-db {confirm_db!r} is not this database ({engine.url.database!r}).")
    if not yes:
        raise SystemExit("Refusing: add --yes to confirm that this deletes the data above.")

    quoted = ", ".join(f'"{t}"' for t in tables)
    with engine.begin() as conn:
        if engine.dialect.name == "postgresql":
            conn.execute(text(f"TRUNCATE TABLE {quoted} RESTART IDENTITY CASCADE"))
        else:
            if engine.dialect.name == "sqlite":
                conn.execute(text("PRAGMA foreign_keys=OFF"))
            for t in tables:
                conn.execute(text(f'DELETE FROM "{t}"'))
    left = {t: n for t, n in row_counts(engine, tables).items() if n}
    if left:
        raise SystemExit(f"Unexpected: rows remain in {left}")
    out("\nDone. The schema is unchanged and every table above is empty.")
    out("Next: create the first Platform Admin (python -m app.utils.create_platform_admin), "
        "then register societies in the app.")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Empty the database, keep the schema.")
    parser.add_argument("--confirm-db", help="the name of the database you mean to empty")
    parser.add_argument("--yes", action="store_true", help="really delete")
    args = parser.parse_args()
    from app.db.session import get_engine
    reset(get_engine(), confirm_db=args.confirm_db, yes=args.yes)


if __name__ == "__main__":
    main()
