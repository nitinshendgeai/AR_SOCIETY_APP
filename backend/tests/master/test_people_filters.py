"""Filtering the Residents and Tenants lists by wing, by whether they have moved in, and (tenants) by agreement,
police verification and KYC."""
from datetime import date, timedelta

import pytest

from app.models.resident import Resident
from app.models.tenant import PoliceVerificationStatus, Tenant
from app.models.wing import Wing
from tests.conftest import make_flat, make_society, make_user, make_wing

R, T = "/api/v1/residents/", "/api/v1/tenants/"


@pytest.fixture
def rig(db):
    society = make_society(db, "Filters Society")
    admin = make_user(db, "pf-admin@x.test", role="Society Admin")
    admin["user"].society_id = society.id
    wing_a = make_wing(db, society.id, "Wing A")
    wing_b = Wing(society_id=society.id, name="Wing B", code="B")
    db.add(wing_b)
    db.commit()
    flats = {"a1": make_flat(db, wing_a.id, "101"), "a2": make_flat(db, wing_a.id, "102"),
             "b1": make_flat(db, wing_b.id, "201")}
    db.commit()
    return {"society": society, "h": admin["headers"], "flats": flats, "wing_a": wing_a, "wing_b": wing_b}


def _names(client, url, h, **params):
    r = client.get(url, params={"limit": 200, **params}, headers=h)
    assert r.status_code == 200, r.text
    return sorted(x["full_name"] for x in r.json())


def test_residents_filter_by_wing_flat_and_moved_in(client, db, rig):
    f, h, today = rig["flats"], rig["h"], date.today()
    db.add_all([
        Resident(flat_id=f["a1"].id, full_name="Asha In", move_in_date=today - timedelta(days=30)),
        Resident(flat_id=f["a2"].id, full_name="Asha Waiting"),
        Resident(flat_id=f["b1"].id, full_name="Bela In", move_in_date=today - timedelta(days=5)),
        Resident(flat_id=f["b1"].id, full_name="Bela Left", move_in_date=today - timedelta(days=400),
                 move_out_date=today - timedelta(days=100)),
    ])
    db.commit()
    assert _names(client, R, h) == ["Asha In", "Asha Waiting", "Bela In", "Bela Left"]
    assert _names(client, R, h, wing_id=str(rig["wing_a"].id)) == ["Asha In", "Asha Waiting"]
    assert _names(client, R, h, wing_id=str(rig["wing_b"].id)) == ["Bela In", "Bela Left"]
    assert _names(client, R, h, flat_id=str(f["a2"].id)) == ["Asha Waiting"]
    assert _names(client, R, h, moved_in="true") == ["Asha In", "Bela In"]                # living there now
    assert _names(client, R, h, moved_in="false") == ["Asha Waiting"]                     # no move-in date yet
    assert _names(client, R, h, wing_id=str(rig["wing_b"].id), moved_in="true") == ["Bela In"]


def test_tenants_filter_by_wing_moved_in_agreement_police_and_kyc(client, db, rig):
    f, h, today = rig["flats"], rig["h"], date.today()
    db.add_all([
        Tenant(flat_id=f["a1"].id, full_name="Runs Long", move_in_date=today - timedelta(days=60),
               agreement_end_date=today + timedelta(days=200), police_verification_status=PoliceVerificationStatus.VERIFIED,
               kyc_verified=True),
        Tenant(flat_id=f["a2"].id, full_name="Expires Soon", move_in_date=today - timedelta(days=300),
               agreement_end_date=today + timedelta(days=10), police_verification_status=PoliceVerificationStatus.PENDING),
        Tenant(flat_id=f["b1"].id, full_name="Lapsed", agreement_end_date=today - timedelta(days=3)),
        Tenant(flat_id=f["b1"].id, full_name="No Dates", police_verification_status=PoliceVerificationStatus.PENDING),
        Tenant(flat_id=f["b1"].id, full_name="Old Lease", lease_end_date=today + timedelta(days=90)),   # the older column
    ])
    db.commit()
    assert len(_names(client, T, h)) == 5
    assert _names(client, T, h, wing_id=str(rig["wing_b"].id)) == ["Lapsed", "No Dates", "Old Lease"]
    assert _names(client, T, h, agreement="running") == ["Old Lease", "Runs Long"]
    assert _names(client, T, h, agreement="expiring") == ["Expires Soon"]
    assert _names(client, T, h, agreement="expired") == ["Lapsed"]
    assert _names(client, T, h, agreement="none") == ["No Dates"]
    # A tenant starts as "pending": every tenant not explicitly verified is waiting
    assert _names(client, T, h, police="pending") == ["Expires Soon", "Lapsed", "No Dates", "Old Lease"]
    assert _names(client, T, h, police="verified") == ["Runs Long"]
    assert _names(client, T, h, kyc_verified="true") == ["Runs Long"]
    assert _names(client, T, h, moved_in="true") == ["Expires Soon", "Runs Long"]
    assert _names(client, T, h, moved_in="false") == ["Lapsed", "No Dates", "Old Lease"]
    assert _names(client, T, h, wing_id=str(rig["wing_a"].id), police="pending") == ["Expires Soon"]   # filters combine
    assert client.get(T, params={"agreement": "nonsense"}, headers=h).status_code == 422
    assert client.get(T, params={"police": "nonsense"}, headers=h).status_code == 422


def test_a_wing_of_another_society_shows_nothing(client, db, rig):
    other = make_society(db, "Other Filters Society")
    other_wing = make_wing(db, other.id, "Wing X")
    other_flat = make_flat(db, other_wing.id, "301")
    db.add_all([Resident(flat_id=other_flat.id, full_name="Not Mine"), Tenant(flat_id=other_flat.id, full_name="Not Mine Either")])
    db.commit()
    assert _names(client, R, rig["h"], wing_id=str(other_wing.id)) == []
    assert _names(client, T, rig["h"], wing_id=str(other_wing.id)) == []
