"""Delete all the data of one society (rows only; no table is ever dropped or altered).

Used by scripts/purge_society.py and by the Platform Admin "Clean data" action.

Deleted: every table carrying a `society_id`, plus the child tables reached from them through foreign keys (flats,
residents, bill lines, voucher entries, poll options, ...), plus the society's users and their sessions / device
tokens / notifications / audit-log rows. Kept: other societies, platform-admin (superadmin) accounts and the global
roles / permissions / forms. The `societies` row itself is kept unless delete_society is set.
"""
from graphlib import CycleError, TopologicalSorter

from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.orm import Session

BLOCKING_ONDELETE = {None, "NO ACTION", "RESTRICT"}


def _import_models():
    import app.models  # noqa: F401 — registers every table on Base.metadata (modules are imported from there)
    from app.db.base import Base
    return Base.metadata


def default_login_emails(society_code):
    """The logins onboarding creates for every society (admin, chairman, secretary, treasurer @ <code>.com)."""
    from app.modules.onboarding.services.onboarding_service import DEFAULT_USER_CONFIGS
    if not society_code:
        return []
    return [f"{cfg['prefix']}@{society_code.lower()}.com" for cfg in DEFAULT_USER_CONFIGS]


def build_scope(metadata, society_id, keep_emails=()):
    """Return {table_name: WHERE-clause} selecting this society's rows in every table that holds its data.

    A table is in scope if it has `society_id`, or if a foreign key leads to a table that is in scope (child tables).
    Tables with neither (roles, permissions, forms, the societies table itself) are global and left alone.
    """
    tables = metadata.tables
    scope = {}
    for name, t in tables.items():
        if name != "societies" and "society_id" in t.c:
            scope[name] = t.c.society_id == society_id
    if keep_emails:
        # kept users stay, and so does everything that hangs off them alone (their roles, sessions, ...)
        scope["users"] = and_(scope["users"], func.lower(tables["users"].c.email).not_in([e.lower() for e in keep_emails]))
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
            return list(TopologicalSorter(graph(blocking_only)).static_order())
        except CycleError:
            continue
    raise RuntimeError("Foreign-key cycle between blocking constraints; cannot order the deletes safely.")


def find_society(db: Session, society_code: str):
    """(id, name) of the society with this code, or None."""
    societies = _import_models().tables["societies"]
    return db.execute(
        select(societies.c.id, societies.c.name).where(func.upper(societies.c.society_code) == society_code.strip().upper())
    ).first()


def purge_society(db: Session, society_id, dry_run: bool = False, delete_society: bool = False,
                  keep_default_logins: bool = True) -> dict:
    """Delete all data of one society. Returns {table: rows_deleted}. Caller commits/rolls back.

    Only rows are deleted, never tables. With dry_run the same counts are returned and nothing is deleted.
    The society's default logins (see default_login_emails) are kept unless keep_default_logins is False or the
    society record itself is being deleted.
    """
    metadata = _import_models()
    societies = metadata.tables["societies"]
    users = metadata.tables["users"]

    row = db.execute(select(societies.c.name, societies.c.society_code).where(societies.c.id == society_id)).first()
    if row is None:
        raise LookupError("Society not found.")
    society_name, society_code = row
    keep_emails = default_login_emails(society_code) if keep_default_logins and not delete_society else []

    if db.execute(select(func.count()).select_from(users).where(
            users.c.society_id == society_id, users.c.is_superadmin.is_(True))).scalar():
        raise RuntimeError("Refusing to purge: a platform-admin (superadmin) account is attached to this society.")

    scope = build_scope(metadata, society_id, keep_emails)
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
    return {"society_id": society_id, "society_name": society_name, "counts": counts, "kept_logins": keep_emails}
