"""The CI helper scripts must FAIL when they should: a CI check that cannot fail is worse than none.

Covers scripts/ci/check_migrations.py (migration history and schema drift) and scripts/ci/check_test_results.py
(guards against a false-green test run). The drift test needs a PostgreSQL server and is skipped unless
MIGRATION_TEST_ADMIN_URL is set (the CI migration job sets it); everything else runs anywhere.
"""
import importlib.util
import os
import subprocess
import sys
import textwrap
import uuid
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[2]
SCRIPTS = BACKEND / "scripts" / "ci"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mig = _load("check_migrations")
res = _load("check_test_results")


def _migration(versions: Path, rev: str, down, name="m"):
    down_src = "None" if down is None else repr(down)
    (versions / f"{rev}_{name}.py").write_text(textwrap.dedent(f'''
        """{name}"""
        from alembic import op
        revision = {rev!r}
        down_revision = {down_src}
        branch_labels = None
        depends_on = None
        def upgrade(): pass
        def downgrade(): pass
    '''))


def _history(tmp_path, spec):
    """spec: list of (revision, down_revision). Returns the script_location."""
    loc = tmp_path / "alembic"
    (loc / "versions").mkdir(parents=True)
    for rev, down in spec:
        _migration(loc / "versions", rev, down)
    return loc


# ── migration graph ──────────────────────────────────────────────────────────

def test_the_real_migration_history_is_valid():
    assert mig.check_graph() == []


def test_a_straight_chain_is_valid(tmp_path):
    assert mig.check_graph(_history(tmp_path, [("a1", None), ("b2", "a1"), ("c3", "b2")])) == []


def test_two_heads_are_rejected(tmp_path):
    problems = mig.check_graph(_history(tmp_path, [("a1", None), ("b2", "a1"), ("c3", "a1")]))
    assert any("exactly one head" in p for p in problems), problems


def test_a_missing_parent_is_rejected(tmp_path):
    problems = mig.check_graph(_history(tmp_path, [("a1", None), ("b2", "ghost")]))
    assert any("ghost" in p and "does not exist" in p for p in problems), problems


def test_a_duplicate_revision_id_is_rejected(tmp_path):
    loc = _history(tmp_path, [("a1", None), ("b2", "a1")])
    _migration(loc / "versions", "b2", "a1", name="copy")           # a second file claiming revision b2
    problems = mig.check_graph(loc)
    assert any("more than one file" in p for p in problems), problems


def test_an_empty_or_missing_history_is_rejected(tmp_path):
    (tmp_path / "alembic" / "versions").mkdir(parents=True)
    assert mig.check_graph(tmp_path / "alembic")
    assert mig.check_graph(tmp_path / "nowhere")


def _cli(*args):
    return subprocess.run([sys.executable, str(SCRIPTS / "check_migrations.py"), *args], capture_output=True, text=True)


def test_the_command_line_exits_non_zero_on_a_broken_history(tmp_path):
    bad = _history(tmp_path, [("a1", None), ("b2", "a1"), ("c3", "a1")])
    r = _cli("graph", "--script-location", str(bad))
    assert r.returncode == 1 and "INVALID" in r.stdout
    assert _cli("graph").returncode == 0


# ── structural drift (needs PostgreSQL) ──────────────────────────────────────

PG_ADMIN = os.environ.get("MIGRATION_TEST_ADMIN_URL")


@pytest.mark.skipif(not PG_ADMIN, reason="set MIGRATION_TEST_ADMIN_URL to a PostgreSQL server to run the drift check")
def test_drift_check_reports_a_missing_and_an_extra_column():
    name = f"drift_{uuid.uuid4().hex[:8]}"
    mig._admin_exec(PG_ADMIN, f'CREATE DATABASE "{name}"')
    try:
        url = mig._replace_db(PG_ADMIN, name)
        mig._run_alembic(url, "upgrade", "head")
        assert mig.check_structural_drift(url) == []                     # a freshly migrated database is clean
        mig._admin_exec(url, "ALTER TABLE wings DROP COLUMN code")       # a model column the database lacks
        mig._admin_exec(url, "ALTER TABLE wings ADD COLUMN zz_not_in_model integer")
        problems = mig.check_structural_drift(url)
        assert "add_column: wings.code" in problems, problems
        assert "remove_column: wings.zz_not_in_model" in problems, problems
        assert _cli("drift", "--database-url", url).returncode == 1
    finally:
        mig._admin_exec(PG_ADMIN, f'DROP DATABASE IF EXISTS "{name}"')


# ── test-result checker ──────────────────────────────────────────────────────

def _junit(tmp_path, tests=10, failures=0, errors=0, skipped=0, name="r.xml"):
    p = tmp_path / name
    p.write_text(f'<?xml version="1.0"?><testsuites><testsuite name="pytest" tests="{tests}" failures="{failures}" '
                 f'errors="{errors}" skipped="{skipped}" time="1.5"></testsuite></testsuites>')
    return p


def test_a_clean_report_passes(tmp_path):
    problems, line = res.check(str(_junit(tmp_path)), min_tests=5, max_skipped=0)
    assert problems == [] and "10 tests" in line


def test_a_failure_or_an_error_fails_the_check(tmp_path):
    assert res.check(str(_junit(tmp_path, failures=1)), 1, 0)[0]
    assert res.check(str(_junit(tmp_path, errors=2)), 1, 0)[0]


def test_far_too_few_tests_is_not_a_pass(tmp_path):
    problems, _ = res.check(str(_junit(tmp_path, tests=3)), min_tests=1000, max_skipped=0)
    assert any("only 3 tests ran" in p for p in problems)


def test_too_many_skips_fail(tmp_path):
    assert res.check(str(_junit(tmp_path, skipped=9)), 1, max_skipped=2)[0]


def test_a_missing_empty_or_garbled_report_is_not_a_pass(tmp_path):
    assert res.check(str(tmp_path / "absent.xml"), 1, 0)[0]
    empty = tmp_path / "empty.xml"; empty.write_text("")
    assert res.check(str(empty), 1, 0)[0]
    bad = tmp_path / "bad.xml"; bad.write_text("<testsuites><oops")
    assert res.check(str(bad), 1, 0)[0]
    none = tmp_path / "none.xml"; none.write_text("<testsuites></testsuites>")
    assert res.check(str(none), 1, 0)[0]


def _junit_cases(tmp_path, classnames, name="c.xml"):
    cases = "".join(f'<testcase classname="{c}" name="t{i}"/>' for i, c in enumerate(classnames))
    p = tmp_path / name
    p.write_text(f'<testsuites><testsuite name="pytest" tests="{len(classnames)}" failures="0" errors="0" skipped="0" '
                 f'time="1">{cases}</testsuite></testsuites>')
    return str(p)


def test_a_required_test_package_must_really_be_in_the_run(tmp_path):
    ran = _junit_cases(tmp_path, ["tests.security.test_a"] * 3 + ["tests.billing.test_b"] * 2)
    assert res.check(ran, 1, 0, {"tests.security": 3})[0] == []
    short = res.check(ran, 1, 0, {"tests.security": 4})[0]
    assert any("only 3 tests came from tests.security" in p for p in short), short
    # a package that is simply absent from the run is a failure, not a pass
    assert res.check(_junit_cases(tmp_path, ["tests.billing.test_b"], "d.xml"), 1, 0, {"tests.security": 1})[0]
    # a prefix must match whole package names: tests.security_extra is not tests.security
    assert res.check(_junit_cases(tmp_path, ["tests.security_extra.t"], "e.xml"), 1, 0, {"tests.security": 1})[0]


def test_the_result_checker_command_line_exit_codes(tmp_path):
    ok = subprocess.run([sys.executable, str(SCRIPTS / "check_test_results.py"), str(_junit(tmp_path)), "--min-tests", "5"],
                        capture_output=True, text=True)
    assert ok.returncode == 0 and "passed" in ok.stdout
    bad = subprocess.run([sys.executable, str(SCRIPTS / "check_test_results.py"), str(_junit(tmp_path, failures=1, name="f.xml"))],
                         capture_output=True, text=True)
    assert bad.returncode == 1 and "FAILED" in bad.stdout
