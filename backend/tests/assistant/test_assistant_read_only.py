"""The assistant never changes state and never calls the endpoints/services that seed on a plain read."""
import ast
import pathlib

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.modules.assistant import diagnostics
from app.modules.assistant.diagnostics import ReadOnlyViolation, read_only_session

API = "/api/v1/assistant"
PKG = pathlib.Path(diagnostics.__file__).parent


def snapshot(db):
    """Row counts of every table plus the full content of the tables diagnostics reads."""
    from app.modules.accounts.models.accounts import Account
    from app.modules.accounts.models.taxes import TaxConfiguration
    from app.modules.billing.models.billing import MaintenanceChargeConfig, MaintenanceElement, MaintenanceSettings
    counts = {t.name: db.execute(select(func.count()).select_from(t)).scalar() for t in Base.metadata.sorted_tables}
    content = {m.__name__: sorted(repr([getattr(r, c.key) for c in m.__table__.columns]) for r in db.query(m).all())
               for m in (Account, TaxConfiguration, MaintenanceChargeConfig, MaintenanceElement, MaintenanceSettings)}
    return counts, content


def test_every_assistant_path_leaves_the_database_untouched(client, db, world, monkeypatch):
    commits = []
    real = Session.commit
    monkeypatch.setattr(Session, "commit", lambda self: (commits.append(1), real(self))[1])
    before = snapshot(db)
    n_before = len(commits)
    everyone = [world.resident_a, world.security_a, world.supervisor_a, world.manager_a, world.committee_a,
                world.admin_a, world.admin_b, world.platform]
    for who in everyone:
        h = who["headers"]
        client.get(f"{API}/status", headers=h)
        for q in ("How do I link maintenance elements to ledgers?", "How do I add a vendor and set TDS?",
                  "How is the chart of accounts and bank ledger set up?", "Show me dues of flat A-101"):
            client.post(f"{API}/ask", json={"question": q, "include_diagnostics": True,
                                            **({"target_society_id": str(world.A.id)} if who is world.platform else {})}, headers=h)
        client.post(f"{API}/diagnostics", json={**({"target_society_id": str(world.B.id)} if who is world.platform else {})}, headers=h)
    assert snapshot(db) == before
    assert len(commits) == n_before, "an assistant call committed"


def test_fresh_society_is_reported_not_seeded(client, db, world):
    from app.modules.accounts.models.accounts import Account
    assert db.query(Account).filter(Account.society_id == world.A.id).count() == 0
    f = {x["topic"]: x["status"] for x in client.post(f"{API}/diagnostics", json={}, headers=world.manager_a["headers"]).json()["findings"]}
    assert f["chart_of_accounts"] == "not_initialised" and f["maintenance_elements"] == "not_initialised"
    assert db.query(Account).filter(Account.society_id == world.A.id).count() == 0


def test_seeding_and_mutating_reads_are_never_invoked(client, world, monkeypatch):
    """Booby-trap every known mutating read; all diagnostic topics must still work."""
    from app.modules.accounts.services import accounts_service, chart_of_accounts
    from app.modules.billing.services.billing_service import BillingService
    from app.modules.vendor.services import vendor_tds

    def boom(*a, **k):
        raise AssertionError("a mutating read was called by the assistant")
    for target, name in ((accounts_service.AccountsService, "ensure_chart"), (accounts_service.AccountsService, "chart"),
                         (accounts_service.AccountsService, "list_accounts"), (accounts_service.AccountsService, "system_account"),
                         (accounts_service.AccountsService, "member_balances"), (accounts_service.AccountsService, "summary"),
                         (chart_of_accounts, "seed_chart_of_accounts"), (BillingService, "list_elements"),
                         (vendor_tds, "ensure_default_rules")):
        monkeypatch.setattr(target, name, boom)
    r = client.post(f"{API}/diagnostics", json={}, headers=world.manager_a["headers"])
    assert r.status_code == 200 and len(r.json()["findings"]) == len(diagnostics.TOPICS)
    r = client.post(f"{API}/ask", json={"question": "How do accounts, ledgers, vendors and billing elements work?",
                                        "include_diagnostics": True}, headers=world.manager_a["headers"])
    assert r.status_code == 200 and r.json()["config_gaps"]


def test_assistant_package_does_not_import_or_name_mutating_code():
    forbidden_modules = ("app.modules.accounts.services", "app.modules.billing.services", "app.modules.vendor.services",
                         "app.modules.accounts.routes", "app.modules.billing.routes", "app.modules.vendor.routes")
    forbidden_names = {"ensure_chart", "seed_chart_of_accounts", "seed_standard_elements", "ensure_default_rules",
                       "list_elements", "list_accounts", "AccountsService", "BillingService"}
    write_calls = {"add", "add_all", "delete", "merge", "flush", "commit", "bulk_save_objects", "bulk_insert_mappings"}
    for path in PKG.rglob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert not node.module.startswith(forbidden_modules), f"{path.name} imports {node.module}"
            if isinstance(node, ast.Import):
                assert not any(a.name.startswith(forbidden_modules) for a in node.names), path.name
            if isinstance(node, ast.Name) and node.id in forbidden_names:
                raise AssertionError(f"{path.name} names {node.id}")
            if isinstance(node, ast.Attribute) and node.attr in forbidden_names:
                raise AssertionError(f"{path.name} uses .{node.attr}")
            # no write call on a session-like object; diagnostics.py names `db.commit` only to replace it with a refusal
            if (isinstance(node, ast.Attribute) and node.attr in write_calls and isinstance(node.value, ast.Name)
                    and node.value.id in ("db", "session", "self.db")):
                assert path.name == "diagnostics.py" and node.attr == "commit", f"{path.name} uses {node.value.id}.{node.attr}"


def test_read_only_session_blocks_writes_and_restores_commit(db, world):
    from app.models.society import Society
    original = db.__dict__.get("commit")
    with read_only_session(db):
        with pytest.raises(ReadOnlyViolation):
            db.commit()
        db.add(Society(name="Sneaky", city="x", state="y"))
        with pytest.raises(ReadOnlyViolation):
            db.flush()
    db.expunge_all()
    assert db.__dict__.get("commit") is original
    assert db.query(Society).filter(Society.name == "Sneaky").count() == 0


def test_read_only_session_blocks_updates_and_deletes(db, world):
    world.A.name = "Renamed by assistant"
    with read_only_session(db):
        with pytest.raises(ReadOnlyViolation):
            db.flush()
    db.expire_all()
    db.delete(world.flat_a)
    with read_only_session(db):
        with pytest.raises(ReadOnlyViolation):
            db.flush()
    db.expunge_all()
