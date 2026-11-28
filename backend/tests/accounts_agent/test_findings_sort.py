"""The findings list can be ordered by severity (the default), when raised, the transaction's date or how certain the
agent is — and every order is stable from one page to the next."""
from datetime import date, datetime, timedelta

import pytest

from app.modules.accounts_agent.models.agent import AgentFinding
from tests.accounts_agent.helpers import Rig

API = "/api/v1/accounts-agent"


@pytest.fixture
def rig(db):
    return Rig(db, "sort")


def _add(db, rig, key, severity, raised_days_ago, voucher_days_ago, confidence):
    f = AgentFinding(
        society_id=rig.sid, voucher_id=None, transaction_ref=key, category="unusual_amount",
        finding_class="strongly_suspected_anomaly", severity=severity, confidence=confidence, rule_code="S-AMT-01",
        dedupe_key=f"S-AMT-01:{key}", title=f"Finding {key}", explanation="x", status="NEW",
        voucher_date=None if voucher_days_ago is None else date.today() - timedelta(days=voucher_days_ago))
    f.created_at = datetime.utcnow() - timedelta(days=raised_days_ago)
    db.add(f)
    return f


@pytest.fixture
def seeded(rig, db):
    #            key  severity   raised voucher conf
    _add(db, rig, "A", "LOW",      1,     30,    0.95)
    _add(db, rig, "B", "HIGH",     5,     10,    0.60)
    _add(db, rig, "C", "MEDIUM",   3,     None,  0.80)      # a society-wide finding: no transaction date
    _add(db, rig, "D", "HIGH",     2,     50,    0.70)
    db.commit()
    return rig


def _refs(client, rig, **params):
    r = client.get(f"{API}/findings", params=params, headers=rig.admin["headers"])
    assert r.status_code == 200, r.text
    return [x["transaction_ref"] for x in r.json()["items"]]


def test_default_is_most_severe_first_then_newest(client, seeded):
    assert _refs(client, seeded) == ["D", "B", "C", "A"]
    assert _refs(client, seeded, sort="severity") == ["D", "B", "C", "A"]


def test_newest_and_oldest_raised(client, seeded):
    assert _refs(client, seeded, sort="newest") == ["A", "D", "C", "B"]
    assert _refs(client, seeded, sort="oldest") == ["B", "C", "D", "A"]


def test_transaction_date_puts_undated_findings_last(client, seeded):
    assert _refs(client, seeded, sort="voucher_new") == ["B", "A", "D", "C"]
    assert _refs(client, seeded, sort="voucher_old") == ["D", "A", "B", "C"]


def test_most_certain_first(client, seeded):
    assert _refs(client, seeded, sort="confidence") == ["A", "C", "D", "B"]


def test_sort_works_with_filters_and_paging_is_stable(client, seeded):
    assert _refs(client, seeded, sort="newest", severity="HIGH") == ["D", "B"]
    r1 = client.get(f"{API}/findings", params={"sort": "oldest", "page_size": 2, "page": 1}, headers=seeded.admin["headers"]).json()
    r2 = client.get(f"{API}/findings", params={"sort": "oldest", "page_size": 2, "page": 2}, headers=seeded.admin["headers"]).json()
    got = [x["transaction_ref"] for x in r1["items"] + r2["items"]]
    assert got == ["B", "C", "D", "A"] and r1["total"] == 4


def test_unknown_sort_is_refused(client, seeded):
    r = client.get(f"{API}/findings", params={"sort": "random"}, headers=seeded.admin["headers"])
    assert r.status_code == 422
