"""The printed Tenants report follows the filters the list is showing, and is for the office only."""
from datetime import date, timedelta
from io import BytesIO

import pytest
from pdfminer.high_level import extract_text

from app.models.tenant import PoliceVerificationStatus, Tenant
from app.models.wing import Wing
from tests.conftest import make_flat, make_society, make_user, make_wing

URL = "/api/v1/tenants/report.pdf"


def _text(r) -> str:
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:5] == b"%PDF-"
    return extract_text(BytesIO(r.content))


@pytest.fixture
def rig(db):
    society = make_society(db, "Report Society")
    admin = make_user(db, "tr-admin@x.test", role="Society Admin")
    admin["user"].society_id = society.id
    resident = make_user(db, "tr-resident@x.test", role="Resident")
    resident["user"].society_id = society.id
    wing_a = make_wing(db, society.id, "Wing A")
    wing_b = Wing(society_id=society.id, name="Wing B", code="B")
    db.add(wing_b)
    db.commit()
    flats = {"a1": make_flat(db, wing_a.id, "101"), "b1": make_flat(db, wing_b.id, "201")}
    other = make_society(db, "Other Society")
    other_wing = make_wing(db, other.id, "Wing Z")
    other_flat = make_flat(db, other_wing.id, "901")
    today = date.today()
    db.add_all([
        Tenant(flat_id=flats["a1"].id, full_name="Alpha Tenant", phone="9876500001", monthly_rent=18000,
               move_in_date=today - timedelta(days=60), agreement_end_date=today + timedelta(days=200),
               police_verification_status=PoliceVerificationStatus.VERIFIED, kyc_verified=True),
        Tenant(flat_id=flats["b1"].id, full_name="Bravo Tenant", phone="9876500002", monthly_rent=22000,
               move_in_date=today - timedelta(days=30), agreement_end_date=today + timedelta(days=10),
               police_verification_status=PoliceVerificationStatus.PENDING),
        Tenant(flat_id=other_flat.id, full_name="Outsider Tenant", phone="9876500003"),
    ])
    db.commit()
    return {"h": admin["headers"], "resident_h": resident["headers"], "wing_a": wing_a, "wing_b": wing_b}


def test_unfiltered_report_lists_this_societys_tenants_only(client, rig):
    text = _text(client.get(URL, headers=rig["h"]))
    assert "TENANTS REPORT" in text
    assert "Alpha Tenant" in text and "Bravo Tenant" in text
    assert "Outsider Tenant" not in text                       # another society's tenant never prints
    assert "2 tenants" in text


def test_the_report_follows_the_filters_on_the_list(client, rig):
    h = rig["h"]
    by_wing = _text(client.get(URL, params={"wing_id": str(rig["wing_a"].id)}, headers=h))
    assert "Alpha Tenant" in by_wing and "Bravo Tenant" not in by_wing
    assert "wing Wing A" in by_wing and "1 tenant" in by_wing and "1 tenants" not in by_wing

    expiring = _text(client.get(URL, params={"agreement": "expiring"}, headers=h))
    assert "Bravo Tenant" in expiring and "Alpha Tenant" not in expiring
    assert "agreement expiring in 30 days" in expiring

    searched = _text(client.get(URL, params={"search": "alpha"}, headers=h))
    assert "Alpha Tenant" in searched and "Bravo Tenant" not in searched

    kyc = _text(client.get(URL, params={"kyc_verified": "true"}, headers=h))
    assert "Alpha Tenant" in kyc and "Bravo Tenant" not in kyc


def test_a_filter_that_matches_nobody_still_prints_a_report(client, rig):
    text = _text(client.get(URL, params={"police": "rejected"}, headers=rig["h"]))
    assert "No tenant matches these filters." in text


def test_a_resident_cannot_print_the_report(client, rig):
    assert client.get(URL, headers=rig["resident_h"]).status_code == 403


def test_the_report_needs_a_login(client, rig):
    assert client.get(URL).status_code in (401, 403)
