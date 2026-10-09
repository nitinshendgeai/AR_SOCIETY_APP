"""Certificate / NOC requests: asking, deciding, dues, numbering and the PDF."""
from app.models.notification import Notification
from app.models.tenant import Tenant
from tests.billing.test_maintenance_billing import _charge, _cycle, _rig as _billing_rig
from tests.conftest import make_user


def _rig(db, tag):
    society, flat1, flat2, manager, resident, other = _billing_rig(db, tag)
    admin = make_user(db, f"cert.admin.{tag}@t.com", role="Society Admin")
    for u in (admin, resident, other):
        u["user"].society_id = society.id
    db.commit()
    return society, flat1, flat2, admin, resident, other


def _ask(client, who, society, kind="address_proof", **extra):
    return client.post(f"/api/v1/certificates/society/{society.id}", json={"kind": kind, **extra},
                       headers=who["headers"])


def _decide(client, who, rid, **body):
    return client.post(f"/api/v1/certificates/{rid}/decision", json=body, headers=who["headers"])


def test_resident_asks_office_is_told_and_approval_numbers_and_prints(client, db):
    society, flat1, _, admin, res, _ = _rig(db, "c1")
    r = _ask(client, res, society, kind="noc_renovation", purpose="Tiles in the kitchen")
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "pending" and body["flat"].endswith("101") and body["applicant_name"] == "Asha Rao"
    assert db.query(Notification).filter(Notification.user_id == admin["user"].id,
                                         Notification.module == "certificates").count() == 1

    # not downloadable until approved
    assert client.get(f"/api/v1/certificates/{body['id']}/pdf", headers=res["headers"]).status_code == 409

    d = _decide(client, admin, body["id"], approve=True)
    assert d.status_code == 200, d.text
    assert d.json()["status"] == "approved"
    assert d.json()["certificate_no"].startswith("NOC/") and d.json()["certificate_no"].endswith("/0001")
    note = db.query(Notification).filter(Notification.user_id == res["user"].id,
                                         Notification.module == "certificates").one()
    assert "approved" in note.body

    pdf = client.get(f"/api/v1/certificates/{body['id']}/pdf", headers=res["headers"])
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")

    # a second approved certificate of the same family takes the next number
    r2 = _ask(client, res, society, kind="noc_renovation")
    assert r2.status_code == 201
    assert _decide(client, admin, r2.json()["id"], approve=True).json()["certificate_no"].endswith("/0002")


def test_rejection_needs_a_reason_and_is_final(client, db):
    society, _, _, admin, res, _ = _rig(db, "c2")
    rid = _ask(client, res, society).json()["id"]
    assert _decide(client, admin, rid, approve=False).status_code == 422
    assert _decide(client, admin, rid, approve=False, note="Incomplete KYC").json()["status"] == "rejected"
    assert _decide(client, admin, rid, approve=True).status_code == 409
    assert client.get(f"/api/v1/certificates/{rid}/pdf", headers=res["headers"]).status_code == 409
    note = db.query(Notification).filter(Notification.user_id == res["user"].id,
                                         Notification.module == "certificates").one()
    assert "Incomplete KYC" in note.body


def test_a_flat_with_dues_gets_no_noc_unless_the_committee_overrides(client, db):
    society, flat1, _, admin, res, _ = _rig(db, "c3")
    h = admin["headers"]
    _charge(client, h, society.id, amount="2500.00")
    cid = _cycle(client, h, society.id).json()["id"]
    assert client.post(f"/api/v1/billing/cycles/{cid}/generate-bills", headers=h).status_code == 200
    assert client.post(f"/api/v1/billing/cycles/{cid}/issue-all", headers=h).status_code == 200

    rid = _ask(client, res, society, kind="noc_sale", party_name="Mr. Kulkarni").json()["id"]
    blocked = _decide(client, admin, rid, approve=True)
    assert blocked.status_code == 409 and "2,500.00" in blocked.json()["detail"]

    ok = _decide(client, admin, rid, approve=True, override_dues=True)
    assert ok.status_code == 200 and ok.json()["dues_at_decision"] == 2500.0
    assert client.get(f"/api/v1/certificates/{rid}/pdf", headers=res["headers"]).content.startswith(b"%PDF")

    # a certificate that does not depend on dues is not held up
    rid2 = _ask(client, res, society, kind="address_proof").json()["id"]
    assert _decide(client, admin, rid2, approve=True).status_code == 200


def test_a_clear_flat_gets_a_no_dues_certificate(client, db):
    society, _, _, admin, res, _ = _rig(db, "c4")
    rid = _ask(client, res, society, kind="no_dues").json()["id"]
    d = _decide(client, admin, rid, approve=True)
    assert d.status_code == 200 and d.json()["certificate_no"].startswith("ND/")
    assert d.json()["dues_at_decision"] == 0.0


def test_who_can_see_and_do_what(client, db):
    society, flat1, flat2, admin, res, other = _rig(db, "c5")
    rid = _ask(client, res, society).json()["id"]
    # duplicates are refused while one is pending
    assert _ask(client, res, society).status_code == 409
    # another resident cannot see it; the office sees everything, a resident only their own
    assert client.get(f"/api/v1/certificates/{rid}", headers=other["headers"]).status_code == 404
    assert len(client.get(f"/api/v1/certificates/society/{society.id}", headers=other["headers"]).json()) == 0
    assert len(client.get(f"/api/v1/certificates/society/{society.id}", headers=admin["headers"]).json()) == 1
    # residents cannot decide
    assert _decide(client, res, rid, approve=True).status_code == 403
    # a stranger from another society is turned away
    s2, _, _, admin2, _, _ = _rig(db, "c5b")
    assert client.get(f"/api/v1/certificates/society/{society.id}", headers=admin2["headers"]).status_code == 403
    # the person can withdraw, but not once decided
    assert client.post(f"/api/v1/certificates/{rid}/cancel", headers=res["headers"]).json()["status"] == "cancelled"
    rid2 = _ask(client, res, society).json()["id"]
    _decide(client, admin, rid2, approve=True)
    assert client.post(f"/api/v1/certificates/{rid2}/cancel", headers=res["headers"]).status_code == 409


def test_office_can_ask_for_a_flat_and_a_tenant_only_for_an_address_certificate(client, db):
    society, flat1, _, admin, res, _ = _rig(db, "c6")
    r = _ask(client, admin, society, kind="noc_loan", flat_id=str(flat1.id), party_name="HDFC Bank")
    assert r.status_code == 201 and r.json()["applicant_name"] == "Asha Rao"

    tenant = make_user(db, "cert.tenant.c6@t.com", role="Tenant")
    tenant["user"].society_id = society.id
    from tests.conftest import make_flat
    tflat = make_flat(db, flat1.wing_id, "9")
    db.add(Tenant(flat_id=tflat.id, user_id=tenant["user"].id, full_name="Tina Tenant"))
    db.commit()
    assert _ask(client, tenant, society, kind="noc_sale").status_code == 403
    assert _ask(client, tenant, society, kind="address_proof").status_code == 201


def test_a_login_with_no_flat_is_told_why(client, db):
    society, _, _, admin, _, _ = _rig(db, "c7")
    lone = make_user(db, "cert.lone.c7@t.com", role="Resident")
    lone["user"].society_id = society.id
    db.commit()
    r = _ask(client, lone, society)
    assert r.status_code == 422 and "not linked to a flat" in r.json()["detail"]
    assert _ask(client, lone, society, kind="nonsense").status_code in (422,)


def test_the_certificate_downloads_in_hindi_and_marathi_too(client, db):
    society, _, _, admin, res, _ = _rig(db, "c8")
    for kind in ("noc_renovation", "address_proof"):
        rid = _ask(client, res, society, kind=kind, purpose="Tiles").json()["id"]
        _decide(client, admin, rid, approve=True)
        en = client.get(f"/api/v1/certificates/{rid}/pdf", headers=res["headers"])
        assert en.status_code == 200 and b".pdf" in en.headers["content-disposition"].encode()
        for lang in ("hi", "mr"):
            r = client.get(f"/api/v1/certificates/{rid}/pdf?lang={lang}", headers=res["headers"])
            assert r.status_code == 200 and r.content.startswith(b"%PDF"), (kind, lang)
            assert f"-{lang}.pdf" in r.headers["content-disposition"]
            assert r.content != en.content
        assert client.get(f"/api/v1/certificates/{rid}/pdf?lang=fr", headers=res["headers"]).status_code == 422


def test_every_kind_has_wording_in_every_language():
    from app.modules.certificates.models.certificates import CERTIFICATE_KINDS
    from app.modules.certificates.services.certificate_text import LANGUAGES, TEXT
    for lang in LANGUAGES:
        assert set(TEXT[lang]["titles"]) == set(CERTIFICATE_KINDS) == set(TEXT[lang]["bodies"])
        assert all(TEXT[lang]["titles"].values())
