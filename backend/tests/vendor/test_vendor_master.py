"""The vendor master in bulk: import from a file (with each vendor's TDS type and section worked out), and the TDS
review that finds and fixes vendors whose setup would deduct at the wrong rate."""
from datetime import date

import pytest

from app.modules.vendor.models.vendor import Vendor, VendorCategory
from tests.conftest import make_society, make_user

V = "/api/v1/vendors"
HEAD = "Vendor Name,Category,Type,PAN,GSTIN,TDS Section,Mobile,Email,Lower TDS Rate (%),Certificate Valid From,Certificate Valid To\n"


@pytest.fixture
def rig(db):
    society = make_society(db, "Master Society")
    admin = make_user(db, "admin@master.test", role="Society Admin")
    manager = make_user(db, "manager@master.test", role="Manager")
    for who in (admin, manager):
        who["user"].society_id = society.id
    db.commit()
    return {"db": db, "society": society, "sid": str(society.id), "admin": admin["headers"], "manager": manager["headers"]}


def _upload(client, rig, text, dry_run=True, headers=None, mapping=None):
    data = {"dry_run": "true" if dry_run else "false"}
    if mapping:
        import json
        data["mapping"] = json.dumps(mapping)
    return client.post(f"{V}/import/{rig['sid']}", headers=headers or rig["admin"], data=data,
                       files={"file": ("vendors.csv", text.encode(), "text/csv")})


def _vendors(db, rig):
    return {v.company_name: v for v in db.query(Vendor).filter(Vendor.society_id == rig["society"].id)}


def test_the_template_imports_cleanly(client, rig, db):
    tpl = client.get(f"{V}/import-template", headers=rig["admin"])
    assert tpl.status_code == 200 and tpl.text.startswith("﻿Vendor Name") or tpl.text.startswith("Vendor Name")
    r = client.post(f"{V}/import/{rig['sid']}", headers=rig["admin"], data={"dry_run": "false"},
                    files={"file": ("t.csv", tpl.content, "text/csv")})
    assert r.status_code == 200, r.text
    assert (r.json()["created"], r.json()["errors"]) == (3, 0)
    vendors = _vendors(db, rig)
    assert vendors["Sparkle Housekeeping Services"].constitution == "individual_proprietor"
    assert vendors["Shield Security Pvt Ltd"].constitution == "private_limited"
    assert str(vendors["Shield Security Pvt Ltd"].tds_lower_rate) == "0.5000"
    assert vendors["CA Mehta & Associates"].tds_section == "194J_PROF"


def test_the_type_comes_from_the_file_then_the_pan_then_the_name(client, rig, db):
    text = HEAD + "\n".join([
        "Given Type Co,Security,Partnership,,,,9876543201,,,,",                # the file says
        "Pan Person,Gardening,,ABCPK1234F,,,9876543202,,,,",                    # the PAN says: an individual
        "Name Says Pvt Ltd,Civil,,,,,9876543203,,,,",                           # the name says: a company
        "Nobody Knows,Plumbing,,,,,9876543204,,,,",                             # nothing says
    ]) + "\n"
    r = _upload(client, rig, text, dry_run=False)
    assert r.status_code == 200, r.text
    rows = {x["name"]: x for x in r.json()["rows"]}
    assert rows["Given Type Co"]["constitution"] == "partnership_firm"
    assert rows["Pan Person"]["constitution"] == "individual_proprietor" and "from its PAN" in rows["Pan Person"]["message"]
    assert rows["Name Says Pvt Ltd"]["constitution"] == "private_limited"
    assert rows["Nobody Knows"]["constitution"] is None and "Type unknown" in rows["Nobody Knows"]["message"]
    v = _vendors(db, rig)
    # the section follows the category when the file gives none, but only where the type is known
    assert v["Pan Person"].tds_section == "194C" and v["Nobody Knows"].tds_section is None


def test_a_type_that_disagrees_with_the_pan_is_refused(client, rig):
    text = HEAD + "Wrong Co,Security,Pvt Ltd,ABCPK1234F,,,9876543210,,,,\n"
    row = _upload(client, rig, text).json()["rows"][0]
    assert row["status"] == "error" and "PAN belongs to an individual" in row["message"]


def test_sections_are_read_from_words_and_no_tds_is_kept(client, rig, db):
    text = HEAD + "\n".join([
        "Fees Co,Other,Firm,,,Professional fees,9876543211,,,,",
        "Rent Co,Other,Individual,,,Rent of building,9876543212,,,,",
        "Exempt Co,Security,Pvt Ltd,,,No TDS,9876543213,,,,",
    ]) + "\n"
    assert _upload(client, rig, text, dry_run=False).status_code == 200
    v = _vendors(db, rig)
    assert v["Fees Co"].tds_section == "194J_PROF"
    assert v["Rent Co"].tds_section == "194I_LB"
    assert v["Exempt Co"].tds_section is None            # explicitly none, not the category's usual 194C


def test_bad_rows_are_listed_and_the_rest_imported(client, rig, db):
    text = HEAD + "\n".join([
        "Good Co,Security,Pvt Ltd,,,,9876543210,,,,",
        ",Security,Pvt Ltd,,,,9876543211,,,,",                      # no name
        "No Phone,Security,Pvt Ltd,,,,,,,,",                        # no mobile
        "Bad Pan,Security,Pvt Ltd,NOTAPAN,,,9876543212,,,,",
        "Bad Rate,Security,Pvt Ltd,,,,9876543213,,50,,",            # a lower rate above 30%
        "Bad Dates,Security,Pvt Ltd,,,,9876543214,,1,01/04/2027,01/04/2026",
    ]) + "\n"
    out = _upload(client, rig, text, dry_run=False).json()
    assert (out["created"], out["errors"]) == (1, 5)
    assert list(_vendors(db, rig)) == ["Good Co"]


def test_a_vendor_already_there_is_skipped_so_the_file_can_be_imported_again(client, rig, db):
    text = HEAD + "Repeat Co,Security,Pvt Ltd,,27AABCS1234P1Z5,,9876543210,,,,\nOther Co,Security,Pvt Ltd,,27AABCS1234P1Z5,,9876543211,,,,\n"
    first = _upload(client, rig, text, dry_run=False).json()
    assert (first["created"], first["duplicates"]) == (1, 1)            # the second has the first's GSTIN
    again = _upload(client, rig, text, dry_run=False).json()
    assert (again["created"], again["duplicates"]) == (0, 2)
    assert len(_vendors(db, rig)) == 1


def test_a_preview_saves_nothing_and_codes_continue_the_series(client, rig, db):
    preview = _upload(client, rig, HEAD + "A Co,Security,Pvt Ltd,,,,9876543210,,,,\n").json()
    assert preview["dry_run"] and preview["ready"] == 1 and _vendors(db, rig) == {}
    _upload(client, rig, HEAD + "A Co,Security,Pvt Ltd,,,,9876543210,,,,\n", dry_run=False)
    _upload(client, rig, HEAD + "B Co,Security,Pvt Ltd,,,,9876543211,,,,\n", dry_run=False)
    assert sorted(v.vendor_code for v in _vendors(db, rig).values()) == ["VND-0001", "VND-0002"]


def test_columns_can_be_pointed_at_fields_and_missing_ones_are_reported(client, rig, db):
    text = "Party,Cell\nMapped Co,9876543210\n"
    assert _upload(client, rig, text).json()["rows"][0]["status"] == "ready"      # both headings are known names
    text = "Firm Detail,Number\nMapped Co,9876543210\n"
    pre = _upload(client, rig, text).json()
    assert "Vendor name" in pre["message"] and pre["rows"] == []
    assert _upload(client, rig, text, dry_run=False).status_code == 422
    ok = _upload(client, rig, text, dry_run=False, mapping={"Firm Detail": "company_name", "Number": "mobile"})
    assert ok.status_code == 200 and ok.json()["created"] == 1


def test_only_admin_or_committee_import_and_only_their_own_society(client, rig, db):
    assert _upload(client, rig, HEAD, headers=rig["manager"]).status_code == 403
    other = make_society(db, "Other")
    r = client.post(f"{V}/import/{other.id}", headers=rig["admin"], data={"dry_run": "false"},
                    files={"file": ("v.csv", (HEAD + "X Co,Security,Pvt Ltd,,,,9876543210,,,,\n").encode(), "text/csv")})
    assert r.status_code == 403 and db.query(Vendor).count() == 0


def test_an_imported_vendor_is_deducted_at_the_rate_its_type_gives(client, rig, db):
    """A company under 194C is 2%, an individual 1%: the import's whole point."""
    _upload(client, rig, HEAD + "Co Pvt Ltd,Security,Pvt Ltd,AABCC1234F,,194C,9876543210,,,,\n"
                              "Person Services,Security,Proprietor,ABCPC1234F,,194C,9876543211,,,,\n", dry_run=False)
    v = _vendors(db, rig)
    rates = {}
    for name in ("Co Pvt Ltd", "Person Services"):
        inv = client.post(f"{V}/invoices", headers=rig["manager"], json={
            "society_id": rig["sid"], "vendor_id": str(v[name].id), "invoice_number": name[:3],
            "invoice_date": str(date.today().replace(day=1)), "amount": "200000", "gst_amount": "0",
            "total_amount": "200000"})
        assert inv.status_code == 201, inv.text
        prev = client.get(f"{V}/invoices/{inv.json()['id']}/payment-preview", headers=rig["manager"],
                          params={"amount": "200000", "paid_date": str(date.today())}).json()
        rates[name] = prev["tds"]["amount"] if "tds" in prev else prev.get("tds_amount")
    assert (float(rates["Co Pvt Ltd"]), float(rates["Person Services"])) == (4000.0, 2000.0)


# ── TDS review ────────────────────────────────────────────────────────────────

def _raw(db, rig, name, category=VendorCategory.HOUSEKEEPING, pan=None, constitution=None, section=None, n=[0]):
    n[0] += 1
    v = Vendor(society_id=rig["society"].id, vendor_code=f"VND-{n[0]:04d}", company_name=name, mobile=f"98765432{n[0]:02d}",
               category=category, pan_number=pan, constitution=constitution, tds_section=section)
    db.add(v)
    db.commit()
    return v


def test_the_review_finds_what_would_be_deducted_wrongly(client, rig, db):
    _raw(db, rig, "No Type Co", pan="AABCC1234F")                                       # type from the PAN
    _raw(db, rig, "Clash Co", pan="ABCPK1234F", constitution="private_limited", section="194C")
    _raw(db, rig, "No Section Co", constitution="private_limited", pan="AABCC1234G")
    _raw(db, rig, "No Pan Co", constitution="private_limited", section="194C")
    _raw(db, rig, "Fine Co", constitution="private_limited", section="194C", pan="AABCC1234H")
    out = client.get(f"{V}/society/{rig['sid']}/tds-review", headers=rig["manager"]).json()
    by = {r["company_name"]: r for r in out["vendors"]}
    codes = lambda n: [i["code"] for i in by[n]["issues"]]
    assert codes("No Type Co")[0] == "no_type"
    assert by["No Type Co"]["suggested_constitution"] == "private_limited"
    assert codes("Clash Co") == ["pan_mismatch"] and by["Clash Co"]["suggested_constitution"] == "individual_proprietor"
    assert "no_section" in codes("No Section Co") and by["No Section Co"]["suggested_section"] == "194C"
    assert codes("No Pan Co") == ["no_pan"] and not by["No Pan Co"]["can_fix"]
    assert by["Fine Co"]["issues"] == []
    assert (out["total"], out["with_issues"]) == (5, 4)
    only = client.get(f"{V}/society/{rig['sid']}/tds-review", params={"only_issues": True}, headers=rig["manager"]).json()
    assert "Fine Co" not in {r["company_name"] for r in only["vendors"]}


def test_applying_suggestions_fixes_type_and_section_together(client, rig, db):
    a = _raw(db, rig, "No Type Co", pan="AABCC1234F")
    b = _raw(db, rig, "Clash Co", pan="ABCPK1234F", constitution="private_limited", section="194C")
    c = _raw(db, rig, "Nothing Known Co")
    r = client.post(f"{V}/society/{rig['sid']}/tds-review/apply", json={"use_suggestions": True}, headers=rig["admin"])
    assert r.status_code == 200, r.text
    assert {x["company_name"] for x in r.json()["fixed"]} == {"No Type Co", "Clash Co"} and r.json()["failed"] == []
    for v in (a, b, c):
        db.refresh(v)
    assert (a.constitution, a.tds_section) == ("private_limited", "194C")
    assert (b.constitution, b.tds_section) == ("individual_proprietor", "194C")
    assert (c.constitution, c.tds_section) == (None, None)                 # nothing to go on: left for a person


def test_an_explicit_fix_must_agree_with_the_pan_and_a_failure_changes_nothing(client, rig, db):
    a = _raw(db, rig, "Person Co", pan="ABCPK1234F")
    b = _raw(db, rig, "Open Co")
    body = {"items": [{"vendor_id": str(a.id), "constitution": "private_limited"},
                      {"vendor_id": str(b.id), "constitution": "llp", "tds_section": "194J_PROF"}]}
    r = client.post(f"{V}/society/{rig['sid']}/tds-review/apply", json=body, headers=rig["admin"]).json()
    assert [x["company_name"] for x in r["fixed"]] == ["Open Co"]
    assert r["failed"][0]["company_name"] == "Person Co" and "PAN belongs to an individual" in r["failed"][0]["message"]
    db.refresh(a)
    db.refresh(b)
    assert a.constitution is None and (b.constitution, b.tds_section) == ("llp", "194J_PROF")


def test_review_access(client, rig, db):
    v = _raw(db, rig, "Some Co")
    assert client.post(f"{V}/society/{rig['sid']}/tds-review/apply", json={"use_suggestions": True},
                       headers=rig["manager"]).status_code == 403             # changing the master is the committee's
    other = make_society(db, "Elsewhere")
    assert client.get(f"{V}/society/{other.id}/tds-review", headers=rig["manager"]).status_code == 403
    foreign = client.post(f"{V}/society/{rig['sid']}/tds-review/apply", headers=rig["admin"],
                          json={"items": [{"vendor_id": "00000000-0000-0000-0000-000000000000", "constitution": "llp"}]})
    assert foreign.status_code == 422
