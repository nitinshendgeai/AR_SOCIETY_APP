"""The channel a tenant's agreement came through (direct, agent, online app, other) and the bulk import of tenants."""
from datetime import date, timedelta

import pytest

from app.models.agreement_tracker import AgreementTracker
from app.models.flat import Flat, OccupancyStatus
from app.models.tenant import Tenant
from app.models.wing import Wing
from app.services.tenant_import import parse_channel, parse_date, parse_money
from tests.conftest import make_flat, make_society, make_user, make_wing

T = "/api/v1/tenants"


@pytest.fixture
def rig(db):
    society = make_society(db, "Rent Society")
    admin = make_user(db, "rent@admin.com", role="Society Admin")
    admin["user"].society_id = society.id
    wing_a = make_wing(db, society.id, "A")
    wing_b = Wing(society_id=society.id, name="B", code="B")      # make_wing gives every wing the code "A"
    db.add(wing_b)
    db.commit()
    flats = {n: make_flat(db, wing_a.id, n) for n in ("101", "102", "103")}
    flats["B101"] = make_flat(db, wing_b.id, "101")
    db.commit()
    return {"society": society, "h": admin["headers"], "flats": flats, "wings": (wing_a, wing_b)}


def _create(client, rig, flat, **extra):
    r = client.post(f"{T}/", headers=rig["h"], json={"flat_id": str(rig["flats"][flat].id), "full_name": "Asha Rao",
                                                      **extra})
    assert r.status_code == 201, r.text
    return r.json()


# ── the channel ──────────────────────────────────────────────────────────────

def test_the_channel_is_kept_on_the_tenant_and_its_agreement(client, db, rig):
    today = date.today()
    t = _create(client, rig, "101", agreement_start_date=str(today), agreement_end_date=str(today + timedelta(days=330)),
                move_in_date=str(today), agreement_channel="agent", agreement_channel_name="Ramesh Estates")
    assert t["agreement_channel"] == "agent" and t["agreement_channel_name"] == "Ramesh Estates"
    agr = client.get(f"{T}/{t['id']}/agreements", headers=rig["h"]).json()[0]
    assert agr["channel"] == "agent" and agr["channel_name"] == "Ramesh Estates"


def test_the_channel_must_be_one_of_the_known_ones(client, db, rig):
    r = client.post(f"{T}/", headers=rig["h"], json={"flat_id": str(rig["flats"]["101"].id), "full_name": "X Y",
                                                     "agreement_channel": "telepathy"})
    assert r.status_code == 422


def test_changing_the_channel_updates_the_current_agreement_and_direct_clears_the_name(client, db, rig):
    today = date.today()
    t = _create(client, rig, "101", agreement_start_date=str(today), agreement_end_date=str(today + timedelta(days=330)),
                move_in_date=str(today), agreement_channel="online_app", agreement_channel_name="NoBroker")
    r = client.patch(f"{T}/{t['id']}", headers=rig["h"], json={"agreement_channel": "direct"})
    assert r.status_code == 200, r.text
    assert r.json()["agreement_channel"] == "direct" and r.json()["agreement_channel_name"] is None
    agr = client.get(f"{T}/{t['id']}/agreements", headers=rig["h"]).json()[0]
    assert agr["channel"] == "direct" and agr["channel_name"] is None


def test_a_renewal_keeps_the_channel_unless_it_gives_another(client, db, rig):
    today = date.today()
    t = _create(client, rig, "101", agreement_start_date=str(today), agreement_end_date=str(today + timedelta(days=330)),
                move_in_date=str(today), agreement_channel="agent", agreement_channel_name="Ramesh Estates")
    start, end = today + timedelta(days=331), today + timedelta(days=700)
    r = client.post(f"{T}/{t['id']}/renew-agreement", headers=rig["h"],
                    json={"start_date": str(start), "end_date": str(end)})
    assert r.status_code == 201, r.text
    assert r.json()["channel"] == "agent" and r.json()["channel_name"] == "Ramesh Estates"
    start2, end2 = end + timedelta(days=1), end + timedelta(days=400)
    r = client.post(f"{T}/{t['id']}/renew-agreement", headers=rig["h"],
                    json={"start_date": str(start2), "end_date": str(end2), "channel": "direct"})
    assert r.status_code == 201, r.text
    assert r.json()["channel"] == "direct" and r.json()["channel_name"] is None
    assert client.get(f"{T}/{t['id']}", headers=rig["h"]).json()["agreement_channel"] == "direct"


# ── reading the cells ────────────────────────────────────────────────────────

def test_channel_words_are_understood():
    for text, want in [("Direct", "direct"), ("owner", "direct"), ("Agent", "agent"), ("Broker - Ramesh", "agent"),
                       ("Online App", "online_app"), ("NoBroker", "online_app"), ("housing.com", "online_app"),
                       ("Friend", "other"), ("", None), (None, None)]:
        assert parse_channel(text) == want, text


def test_dates_and_amounts_are_read_as_typed():
    assert parse_date("2026-04-01") == date(2026, 4, 1) and parse_date("01/04/2026") == date(2026, 4, 1)
    assert parse_date("1-4-26") == date(2026, 4, 1) and parse_date("") is None
    with pytest.raises(ValueError):
        parse_date("next week")
    assert str(parse_money("₹ 25,000")) == "25000" and str(parse_money("Rs. 1,50,000.50")) == "150000.50"
    with pytest.raises(ValueError):
        parse_money("a lot")


# ── the import ───────────────────────────────────────────────────────────────

def _row(line, flat="101", wing="A", name="Meena Shah", **extra):
    return {"line": line, "wing": wing, "flat_number": flat, "full_name": name, "agreement_start_date": "01/04/2026",
            "agreement_end_date": "28/02/2027", "monthly_rent": "25,000", "security_deposit": "75000",
            "channel": "Online App", "channel_name": "NoBroker", **extra}


def _import(client, rig, rows, dry_run=False):
    r = client.post(f"{T}/import", headers=rig["h"], json={"rows": rows, "dry_run": dry_run})
    assert r.status_code == 200, r.text
    return r.json()


def test_a_dry_run_checks_every_row_and_writes_nothing(client, db, rig):
    got = _import(client, rig, [_row(2), _row(3, flat="999")], dry_run=True)
    assert [g["status"] for g in got] == ["created", "error"] and "no flat" in got[1]["message"]
    assert db.query(Tenant).count() == 0


def test_rows_become_tenants_with_agreement_rent_and_channel(client, db, rig):
    got = _import(client, rig, [_row(2), _row(3, flat="102", name="Karan Joshi", channel="Direct", channel_name="")])
    assert [g["status"] for g in got] == ["created", "created"]
    db.expire_all()
    meena = db.query(Tenant).filter_by(full_name="Meena Shah").one()
    assert (str(meena.monthly_rent), str(meena.security_deposit)) == ("25000.00", "75000.00")
    assert (meena.agreement_channel, meena.agreement_channel_name) == ("online_app", "NoBroker")
    assert meena.move_in_date == date(2026, 4, 1)                         # the agreement's start
    agr = db.query(AgreementTracker).filter_by(tenant_id=meena.id).one()
    assert agr.start_date == date(2026, 4, 1) and agr.end_date == date(2027, 2, 28) and agr.channel == "online_app"
    karan = db.query(Tenant).filter_by(full_name="Karan Joshi").one()
    assert (karan.agreement_channel, karan.agreement_channel_name) == ("direct", None)
    assert db.get(Flat, rig["flats"]["101"].id).occupancy_status == OccupancyStatus.TENANT_OCCUPIED


def test_each_row_stands_alone_and_a_second_import_skips_what_is_in(client, db, rig):
    rows = [_row(2), _row(3, flat="102", agreement_end_date="not a date"), _row(4, flat="103", name=""),
            _row(5, flat="", name="No Flat"), _row(6, flat="101", wing="")]
    got = _import(client, rig, rows)
    assert [g["status"] for g in got] == ["created", "error", "error", "error", "error"]
    assert "dd/mm/yyyy" in got[1]["message"] and "name is required" in got[2]["message"]
    assert "Flat number is required" in got[3]["message"]
    assert "more than one wing" in got[4]["message"]                       # flat 101 is in wings A and B
    again = _import(client, rig, [_row(2)])
    assert again[0]["status"] == "skipped" and "already the tenant" in again[0]["message"]
    assert db.query(Tenant).count() == 1


def test_another_tenant_in_the_flat_and_a_repeated_flat_are_refused(client, db, rig):
    _create(client, rig, "101", move_in_date=str(date.today()))
    got = _import(client, rig, [_row(2, name="Someone Else"), _row(3, flat="102"), _row(4, flat="102", name="Twin")])
    assert got[0]["status"] == "error" and "already active" in got[0]["message"]
    assert got[1]["status"] == "created"
    assert got[2]["status"] == "error" and "appears again" in got[2]["message"]


def test_the_import_is_for_the_committee_and_the_own_society(client, db, rig):
    manager = make_user(db, "rent@mgr.com", role="Manager")
    manager["user"].society_id = rig["society"].id
    db.commit()
    assert client.post(f"{T}/import", headers=manager["headers"], json={"rows": [_row(2)]}).status_code == 403
    other = make_society(db, "Other Society")
    other_admin = make_user(db, "other@admin.com", role="Society Admin")
    other_admin["user"].society_id = other.id
    db.commit()
    got = client.post(f"{T}/import", headers=other_admin["headers"], json={"rows": [_row(2)]}).json()
    assert got[0]["status"] == "error" and "no flat" in got[0]["message"]      # this society has no such flat
