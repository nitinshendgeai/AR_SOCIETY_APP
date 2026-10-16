#!/usr/bin/env python3
"""Migration checks used by CI (and runnable locally).

    python scripts/ci/check_migrations.py graph [--script-location DIR]
        No database needed. Fails on: several heads, a missing parent, a duplicate revision id, a revision no chain
        from the head reaches, or a migration file Alembic did not load.

    python scripts/ci/check_migrations.py drift --database-url URL
        A database already migrated to head. Fails if the models define a table or column the database lacks (a model
        change shipped without a migration) or the database has a table or column no model defines. Types, server
        defaults, indexes and constraints are NOT compared: they differ widely today (see docs/audit/PHASE_2_CI_AUDIT.md).

    python scripts/ci/check_migrations.py full --admin-url URL
        Needs a PostgreSQL server (any database on it; throwaway databases are created and dropped):
          1. the graph check;
          2. an EMPTY database upgraded to head, `current` equals head, no structural drift;
          3. the head migration downgraded one step and upgraded again;
          4. an EMPTY database upgraded to an earlier revision, then to head;
          5. the app started against a head database answers /health/ready 200, and against a database one revision
             behind answers 503.
        Never point this at a database that holds data you care about. CI uses a disposable service container.

Exit code 0 = every check passed; 1 = a check failed (the reason is printed); 2 = usage / environment error.
"""
import argparse
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
DEFAULT_SCRIPT_LOCATION = BACKEND_DIR / "alembic"

STRUCTURAL = ("add_table", "remove_table", "add_column", "remove_column")


# ── graph ────────────────────────────────────────────────────────────────────

def _parse_revision_files(versions_dir: Path):
    """(revision, down_revisions, filename) for every migration file, read from the source text."""
    out = []
    rev_re = re.compile(r"^revision\s*(?::\s*[^=]+)?=\s*['\"]([^'\"]+)['\"]", re.M)
    down_re = re.compile(r"^down_revision\s*(?::\s*[^=]+)?=\s*(.+)$", re.M)
    for path in sorted(versions_dir.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        m = rev_re.search(text)
        if not m:
            continue                                         # __init__.py or a helper, not a migration
        d = down_re.search(text)
        downs = re.findall(r"['\"]([^'\"]+)['\"]", d.group(1)) if d else []
        out.append((m.group(1), downs, path.name))
    return out


def check_graph(script_location: Path = DEFAULT_SCRIPT_LOCATION):
    """Return a list of problems (empty list = the migration history is sound)."""
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    problems = []
    versions = Path(script_location) / "versions"
    if not versions.is_dir():
        return [f"no versions directory at {versions}"]
    files = _parse_revision_files(versions)
    if not files:
        return [f"no migration files found in {versions}"]

    ids = [r for r, _, _ in files]
    for rid in sorted({r for r in ids if ids.count(r) > 1}):
        problems.append(f"revision id {rid} is used by more than one file: "
                        f"{[f for r, _, f in files if r == rid]}")
    known = set(ids)
    for rid, downs, fname in files:
        for parent in downs:
            if parent not in known:
                problems.append(f"{fname}: parent revision {parent} does not exist")

    cfg = Config()
    cfg.set_main_option("script_location", str(script_location))
    try:
        script = ScriptDirectory.from_config(cfg)
        heads = script.get_heads()
        if len(heads) != 1:
            problems.append(f"expected exactly one head, found {len(heads)}: {sorted(heads)}")
        reachable = {r.revision for r in script.walk_revisions()} if len(heads) >= 1 else set()
        unreachable = known - reachable
        if unreachable and len(heads) == 1:
            problems.append(f"revisions not reachable from the head: {sorted(unreachable)}")
        if len(reachable) != len(known) and len(heads) == 1 and not unreachable:
            problems.append(f"Alembic loaded {len(reachable)} revisions but {len(known)} migration files exist")
    except Exception as exc:                                  # Alembic's own errors on a broken graph
        problems.append(f"Alembic could not load the history: {exc}")
    return problems


# ── drift ────────────────────────────────────────────────────────────────────

def check_structural_drift(database_url: str):
    """Tables and columns the models and the database disagree on. Returns a list of problems."""
    os.environ["DATABASE_URL"] = database_url
    # Append, never insert first: backend/alembic (the migrations folder) would shadow the installed alembic library.
    if str(BACKEND_DIR) not in sys.path:
        sys.path.append(str(BACKEND_DIR))
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext
    from sqlalchemy import create_engine
    import app.models  # noqa: F401  (registers every model on Base.metadata)
    from app.db.base import Base

    engine = create_engine(database_url)
    try:
        with engine.connect() as conn:
            ctx = MigrationContext.configure(conn, opts={"compare_type": False, "compare_server_default": False})
            diffs = compare_metadata(ctx, Base.metadata)
    finally:
        engine.dispose()

    def flat(items):
        for d in items:
            if isinstance(d, list):
                yield from flat(d)
            else:
                yield d

    problems = []
    for d in flat(diffs):
        kind = d[0]
        if kind not in STRUCTURAL:
            continue
        if kind in ("add_table", "remove_table"):
            problems.append(f"{kind}: {d[1].name}")
        else:
            problems.append(f"{kind}: {d[2]}.{d[3].name}")
    return problems


# ── database helpers (PostgreSQL) ────────────────────────────────────────────

def _replace_db(url: str, name: str) -> str:
    return re.sub(r"(/)([^/?]+)(\?.*)?$", lambda m: f"/{name}{m.group(3) or ''}", url)


def _admin_exec(admin_url: str, sql: str):
    import psycopg2
    conn = psycopg2.connect(admin_url)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
    finally:
        conn.close()


def _run_alembic(db_url: str, *args: str, check=True):
    env = dict(os.environ, DATABASE_URL=db_url, SECRET_KEY=os.environ.get("SECRET_KEY", "ci-migration-check-secret-key-0123456789"),
               SCHEDULER_ENABLED="false", APP_ENV="test")
    # The `alembic` console script, as the repo documents: `python -m alembic` run from backend/ would import the
    # migrations folder (also named alembic) instead of the library.
    exe = Path(sys.executable).parent / "alembic"
    cmd = [str(exe)] if exe.exists() else [sys.executable, "-I", "-m", "alembic"]
    proc = subprocess.run([*cmd, *args], cwd=BACKEND_DIR, env=env, capture_output=True, text=True)
    if check and proc.returncode != 0:
        raise RuntimeError(f"alembic {' '.join(args)} failed (exit {proc.returncode}):\n{proc.stdout[-1500:]}\n{proc.stderr[-1500:]}")
    return proc


def _current(db_url: str) -> str:
    out = _run_alembic(db_url, "current").stdout + _run_alembic(db_url, "current").stderr
    m = re.findall(r"^([0-9a-f]{6,})", out, re.M)
    return m[-1] if m else ""


def _chain(script_location: Path = DEFAULT_SCRIPT_LOCATION):
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    cfg = Config()
    cfg.set_main_option("script_location", str(script_location))
    script = ScriptDirectory.from_config(cfg)
    return script.get_current_head(), [r.revision for r in script.walk_revisions()]   # head first


def _readiness(db_url: str, port: int):
    """(http status, body) of /health/ready from the app started against db_url."""
    env = dict(os.environ, DATABASE_URL=db_url, SECRET_KEY="ci-migration-check-secret-key-0123456789",
               SCHEDULER_ENABLED="false", APP_ENV="test", RUN_MIGRATIONS="false")
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(port), "--log-level", "warning"],
                            cwd=BACKEND_DIR, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        url = f"http://127.0.0.1:{port}/health/ready"
        deadline = time.time() + 60
        while time.time() < deadline:
            if proc.poll() is not None:
                raise RuntimeError("the app exited before it could answer /health/ready")
            try:
                with urllib.request.urlopen(url, timeout=3) as r:
                    return r.status, r.read().decode()
            except urllib.error.HTTPError as e:
                return e.code, e.read().decode()
            except (urllib.error.URLError, ConnectionError, OSError):
                time.sleep(1)
        raise RuntimeError("the app did not answer /health/ready within 60 s")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


# ── full ─────────────────────────────────────────────────────────────────────

def run_full(admin_url: str, port: int = 8765) -> int:
    failures = []
    suffix = uuid.uuid4().hex[:8]
    names = {"fresh": f"mig_fresh_{suffix}", "upgrade": f"mig_upgrade_{suffix}"}

    def step(title):
        print(f"\n=== {title}", flush=True)

    def fail(msg):
        failures.append(msg)
        print(f"FAIL: {msg}", flush=True)

    step("1. migration graph")
    probs = check_graph()
    for p in probs:
        fail(f"graph: {p}")
    if not probs:
        print("ok: one head, no missing parent, no duplicate id, every revision reachable")

    head, chain = _chain()
    try:
        for n in names.values():
            _admin_exec(admin_url, f'CREATE DATABASE "{n}"')
        fresh = _replace_db(admin_url, names["fresh"])
        older = _replace_db(admin_url, names["upgrade"])

        step("2. empty database -> head")
        t0 = time.time()
        _run_alembic(fresh, "upgrade", "head")
        cur = _current(fresh)
        print(f"upgraded 0 -> {cur} in {time.time() - t0:.1f}s")
        if cur != head:
            fail(f"after upgrade head the database is at {cur!r}, expected {head!r}")
        drift = check_structural_drift(fresh)
        for d in drift:
            fail(f"structural drift: {d}")
        if not drift:
            print("ok: models and migrated schema agree on every table and column")

        step("3. head migration is reversible")
        _run_alembic(fresh, "downgrade", "-1")
        if _current(fresh) != chain[1]:
            fail(f"downgrade -1 left the database at {_current(fresh)!r}, expected {chain[1]!r}")
        _run_alembic(fresh, "upgrade", "head")
        if _current(fresh) != head:
            fail("upgrade after downgrade did not return to head")
        else:
            print(f"ok: {head} -> {chain[1]} -> {head}")

        step("4. earlier revision -> head")
        target = chain[min(5, len(chain) - 1)]            # five migrations behind the head
        _run_alembic(older, "upgrade", target)
        if _current(older) != target:
            fail(f"could not build a database at {target}")
        _run_alembic(older, "upgrade", "head")
        if _current(older) != head:
            fail(f"upgrade from {target} ended at {_current(older)!r}, expected {head!r}")
        else:
            print(f"ok: {target} -> {head}")
        for d in check_structural_drift(older):
            fail(f"structural drift after the upgrade path: {d}")

        step("5. /health/ready on the app")
        status, body = _readiness(fresh, port)
        print(f"database at head -> HTTP {status}")
        if status != 200 or '"ready"' not in body:
            fail(f"expected 200 ready at head, got {status}: {body[:200]}")
        _admin_exec(fresh, "UPDATE alembic_version SET version_num = '%s'" % chain[1])
        status, body = _readiness(fresh, port)
        print(f"database one revision behind -> HTTP {status}")
        if status != 503 or "not_ready" not in body:
            fail(f"expected 503 not_ready when the schema is behind, got {status}: {body[:200]}")
    except Exception as exc:
        fail(f"error while checking: {exc}")
    finally:
        for n in names.values():
            try:
                _admin_exec(admin_url, f'DROP DATABASE IF EXISTS "{n}"')
            except Exception as exc:                       # never hide the real result behind a cleanup error
                print(f"warning: could not drop {n}: {exc}")

    print()
    if failures:
        print(f"MIGRATION CHECKS FAILED ({len(failures)}):")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("MIGRATION CHECKS PASSED")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("graph")
    g.add_argument("--script-location", default=str(DEFAULT_SCRIPT_LOCATION))
    d = sub.add_parser("drift")
    d.add_argument("--database-url", required=True)
    f = sub.add_parser("full")
    f.add_argument("--admin-url", required=True, help="postgresql://user:password@host:port/postgres (needs CREATE DATABASE)")
    f.add_argument("--port", type=int, default=8765)
    a = ap.parse_args(argv)

    if a.cmd == "graph":
        probs = check_graph(Path(a.script_location))
        if probs:
            print("MIGRATION GRAPH INVALID:")
            for p in probs:
                print(f"  - {p}")
            return 1
        print("migration graph ok")
        return 0
    if a.cmd == "drift":
        probs = check_structural_drift(a.database_url)
        if probs:
            print("STRUCTURAL DRIFT between models and database:")
            for p in probs:
                print(f"  - {p}")
            return 1
        print("no structural drift")
        return 0
    return run_full(a.admin_url, a.port)


if __name__ == "__main__":
    sys.exit(main())
