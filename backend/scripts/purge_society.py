"""
Platform-admin maintenance script: permanently delete all data of ONE society.

    python scripts/purge_society.py <SOCIETY_CODE>                 # preview, then ask to re-type the code
    python scripts/purge_society.py <SOCIETY_CODE> --dry-run       # preview only, nothing is deleted
    python scripts/purge_society.py <SOCIETY_CODE> --yes           # no prompt (automation)
    python scripts/purge_society.py <SOCIETY_CODE> --delete-society  # also remove the society record itself

Run it from the backend/ directory against the database in DATABASE_URL (the same env var the app uses).

What is deleted: every row that belongs to the society — all tables carrying a `society_id`, plus the child tables
reached from them through foreign keys (flats, residents, bill lines, voucher entries, poll options, ...), plus the
society's users and their sessions / device tokens / notifications / audit-log rows.

What is kept: other societies, platform-admin (superadmin) accounts, and the global roles / permissions / forms.
By default the `societies` row is kept (so the code stays reserved and can be re-onboarded); pass --delete-society
to remove it too.

Everything runs in a single transaction: any error rolls the whole purge back. Uploaded files on disk or in object
storage are NOT touched.
"""
import argparse
import os
import sys
from graphlib import CycleError, TopologicalSorter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import delete, func, or_, select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

BLOCKING_ONDELETE = {None, "NO ACTION", "RESTRICT"}


def _import_models():
    import app.models  # noqa: F401 — registers every table on Base.metadata (modules are imported from there)
    from app.db.base import Base
    return Base.metadata


def build_scope(metadata, society_id):
    """Return {table_name: WHERE-clause} selecting this society's rows in every table that holds its data.

    A table is in scope if it has `society_id`, or if a foreign key leads to a table that is in scope (child tables).
    Tables with neither (roles, permissions, forms, the societies table itself) are global and left alone.
    """
    tables = metadata.tables
    scope = {}
    for name, t in tables.items():
        if name != "societies" and "society_id" in t.c:
            scope[name] = t.c.society_id == society_id
    scope["societies"] = None  # handled separately

    # Child tables with no society_id of their own: scoped through their foreign keys, to a fixpoint.
    changed = True
    while changed:
        changed = False
        for name, t in tables.items():
            if name in scope:
                continue
            clauses = []
            for fk in t.foreign_keys:
                parent = fk.column.table.name
                if parent in scope and scope[parent] is not None:
                    clauses.append(fk.parent.in_(select(fk.column).where(scope[parent])))
            if clauses:
                scope[name] = or_(*clauses)
                changed = True
    scope.pop("societies")
    return scope


def delete_order(metadata, names):
    """Children before parents. Falls back to blocking-FK edges only if the full FK graph has a cycle."""
    def graph(blocking_only):
        g = {n: set() for n in names}
        for n in names:
            for fk in metadata.tables[n].foreign_keys:
                parent = fk.column.table.name
                if parent == n or parent not in g:
                    continue
                if blocking_only and (fk.ondelete or "").upper() not in BLOCKING_ONDELETE:
                    continue
                g[parent].add(n)  # parent must be deleted after child
        return g

    for blocking_only in (False, True):
        try:
            return list(TopologicalSorter(graph(blocking_only)).static_order())[::-1]
        except CycleError:
            continue
    raise RuntimeError("Foreign-key cycle between blocking constraints; cannot order the deletes safely.")


def purge_society(db: Session, society_code: str, dry_run: bool = False, delete_society: bool = False) -> dict:
    """Delete all data of the society with this code. Returns {table: rows_deleted}. Caller commits/rolls back."""
    metadata = _import_models()
    societies = metadata.tables["societies"]
    users = metadata.tables["users"]

    row = db.execute(
        select(societies.c.id, societies.c.name).where(func.upper(societies.c.society_code) == society_code.strip().upper())
    ).first()
    if row is None:
        raise LookupError(f"No society with code {society_code!r}.")
    society_id, society_name = row

    if db.execute(select(func.count()).select_from(users).where(
            users.c.society_id == society_id, users.c.is_superadmin.is_(True))).scalar():
        raise RuntimeError("Refusing to purge: a platform-admin (superadmin) account is attached to this society.")

    scope = build_scope(metadata, society_id)
    counts = {}
    for name in delete_order(metadata, list(scope)):
        table = metadata.tables[name]
        if dry_run:
            n = db.execute(select(func.count()).select_from(table).where(scope[name])).scalar()
        else:
            n = db.execute(delete(table).where(scope[name])).rowcount
        if n:
            counts[name] = n

    if delete_society:
        if dry_run:
            counts["societies"] = 1
        else:
            counts["societies"] = db.execute(delete(societies).where(societies.c.id == society_id)).rowcount
    return {"society_id": society_id, "society_name": society_name, "counts": counts}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Permanently delete all data of one society (platform admin only).")
    ap.add_argument("society_code", help="society_code of the society to clean")
    ap.add_argument("--dry-run", action="store_true", help="show what would be deleted, delete nothing")
    ap.add_argument("--delete-society", action="store_true", help="also delete the society record itself")
    ap.add_argument("--yes", action="store_true", help="skip the interactive confirmation")
    args = ap.parse_args(argv)

    from app.db.session import get_session_factory
    db = get_session_factory()()
    try:
        preview = purge_society(db, args.society_code, dry_run=True, delete_society=args.delete_society)
        db.rollback()
        print(f"Society : {preview['society_name']}  (code {args.society_code.upper()}, id {preview['society_id']})")
        total = sum(preview["counts"].values())
        for table, n in sorted(preview["counts"].items()):
            print(f"  {table:<40}{n:>8}")
        print(f"  {'TOTAL':<40}{total:>8}")
        if args.dry_run:
            print("Dry run — nothing deleted.")
            return 0

        if not args.yes:
            typed = input(f"\nThis permanently deletes the data above. Re-type the society code ({args.society_code.upper()}) to confirm: ")
            if typed.strip().upper() != args.society_code.strip().upper():
                print("Code did not match — aborted, nothing deleted.")
                return 1

        result = purge_society(db, args.society_code, delete_society=args.delete_society)
        db.commit()
        print(f"Done — {sum(result['counts'].values())} rows deleted.")
        return 0
    except (LookupError, RuntimeError) as e:
        db.rollback()
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
