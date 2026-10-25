"""TDS on vendor payments. The vendor's type (individual, firm, company...) and usual section are set once in the master;
when a bill is paid the TDS is worked out, shown first, saved on the payment and posted: Dr creditors, Cr bank, Cr TDS payable."""
from datetime import date
from decimal import Decimal
from uuid import UUID

import pytest

from app.modules.accounts.models.accounts import Voucher
from tests.conftest import make_society, make_user

V = "/api/v1/vendors"
COMPANY_PAN, PERSON_PAN, FIRM_PAN = "ABCCE1234F", "ABCPE1234F", "ABCFE1234F"


@pytest.fixture
def rig(db):
    society = make_society(db, "TDS Society")
    admin = make_user(db, "admin@tds.test", role="Society Admin")
    manager = make_user(db, "manager@tds.test", role="Manager")
    for who in (admin, manager):
        who["user"].society_id = society.id
    db.commit()
    return {"db": db, "society": society, "sid": str(society.id), "admin": admin["headers"], "manager": manager["headers"]}


def _vendor(client, rig, name="Sparkle Services", **over):
    body = {"society_id": rig["sid"], "company_name": name, "mobile": "9876543210", "category": "housekeeping",
            "constitution": "private_limited", "pan_number": COMPANY_PAN, **over}
    r = client.post(f"{V}/", json=body, headers=rig["admin"])
    assert r.status_code == 201, r.text
    return r.json()


def _bill(client, rig, vendor_id, amount="100000", gst="0", number="B-1", on=None, **over):
    total = str(Decimal(amount) + Decimal(gst))
    body = {"society_id": rig["sid"], "vendor_id": vendor_id, "invoice_number": number,
            "invoice_date": str(on or date.today().replace(day=1)), "amount": amount, "gst_amount": gst,
            "total_amount": total, **over}
    if Decimal(gst) > 0:
        body["gst_component"] = "CGST_SGST"
    r = client.post(f"{V}/invoices", json=body, headers=rig["manager"])
    assert r.status_code == 201, r.text
    return r.json()


def _pay(client, rig, inv_id, amount, on=None, expect=200):
    r = client.post(f"{V}/invoices/{inv_id}/payments", headers=rig["manager"], json={
        "amount": str(amount), "paid_date": str(on or date.today()), "payment_mode": "neft", "payment_ref": "UTR1"})
    assert r.status_code == expect, r.text
    return r.json()


def _preview(client, rig, inv_id, amount, on=None):
    r = client.get(f"{V}/invoices/{inv_id}/payment-preview", headers=rig["manager"],
                   params={"amount": str(amount), "paid_date": str(on or date.today())})
    assert r.status_code == 200, r.text
    return r.json()


def _last_payment(inv):
    return [p for p in inv["payments"] if not p["is_reversed"]][-1]


def _lines(rig, payment_id):
    v = rig["db"].query(Voucher).filter(Voucher.source_type == "vendor_payment", Voucher.source_id == UUID(payment_id),
                                        Voucher.is_cancelled == False).one()  # noqa: E712
    return {e.account.system_key or e.account.name: (Decimal(e.debit), Decimal(e.credit)) for e in v.entries}


# ── The vendor master ────────────────────────────────────────────────────────

def test_the_form_gets_vendor_types_and_sections(client, rig):
    o = client.get(f"{V}/tds/options", headers=rig["manager"]).json()
    types = {c["value"] for c in o["constitutions"]}
    assert {"individual_proprietor", "huf", "partnership_firm", "llp", "private_limited", "public_limited"} <= types
    assert {s["value"] for s in o["sections"]} >= {"194C", "194J_PROF", "194J_TECH"}
    assert o["category_default_section"]["housekeeping"] == "194C" and o["category_default_section"]["it"] == "194J_TECH"


def test_a_vendor_with_a_type_starts_with_the_usual_section_for_its_kind(client, rig):
    v = _vendor(client, rig)
    assert v["constitution"] == "private_limited" and v["tds_section"] == "194C"
    shown = client.get(f"{V}/{v['id']}", headers=rig["manager"]).json()
    assert "Private Limited" in shown["constitution_label"] and shown["tds_section_label"].startswith("194C")
    it = _vendor(client, rig, "Net Techies", category="it", mobile="9876543211", pan_number=None)
    assert it["tds_section"] == "194J_TECH"
    plain = client.post(f"{V}/", headers=rig["admin"], json={
        "society_id": rig["sid"], "company_name": "Old Vendor", "mobile": "9876543212", "category": "civil"}).json()
    assert plain["constitution"] is None and plain["tds_section"] is None       # nothing is deducted until it is set


def test_the_type_the_pan_and_the_section_must_agree(client, rig):
    clash = client.post(f"{V}/", headers=rig["admin"], json={
        "society_id": rig["sid"], "company_name": "Mismatch", "mobile": "9876543213", "category": "civil",
        "constitution": "private_limited", "pan_number": PERSON_PAN})
    assert clash.status_code == 422 and "belongs to an individual" in clash.text
    no_type = client.post(f"{V}/", headers=rig["admin"], json={
        "society_id": rig["sid"], "company_name": "No type", "mobile": "9876543213", "category": "civil",
        "tds_section": "194C"})
    assert no_type.status_code == 422 and "type" in no_type.text.lower()
    for bad in ({"constitution": "pirate"}, {"constitution": "huf", "tds_section": "999Z", "pan_number": None},
                {"constitution": "llp", "tds_lower_rate": "45", "pan_number": None}):
        r = client.post(f"{V}/", headers=rig["admin"], json={
            "society_id": rig["sid"], "company_name": "Bad", "mobile": "9876543213", "category": "civil", **bad})
        assert r.status_code == 422, bad
    v = _vendor(client, rig, "Firm & Sons", constitution="partnership_firm", pan_number=FIRM_PAN, mobile="9876543214")
    again = client.patch(f"{V}/{v['id']}", headers=rig["admin"], json={"pan_number": PERSON_PAN})
    assert again.status_code == 422                                     # an update is held to the same rule
    ok = client.patch(f"{V}/{v['id']}", headers=rig["admin"], json={"constitution": "llp"})
    assert ok.status_code == 200 and ok.json()["constitution"] == "llp"   # a firm and an LLP both hold an 'F' PAN


# ── At payment ───────────────────────────────────────────────────────────────

def test_a_company_is_deducted_two_percent_and_the_entry_is_posted(client, rig):
    inv = _bill(client, rig, _vendor(client, rig)["id"], "100000")
    shown = _preview(client, rig, inv["id"], "100000")
    assert shown["applies"] and shown["section"] == "194C" and shown["rate"] == "2.0000"
    assert shown["tds_amount"] == "2000.00" and shown["net_payable"] == "98000.00" and "194C contract" in shown["note"]

    paid = _pay(client, rig, inv["id"], "100000")
    p = _last_payment(paid)
    assert paid["is_paid"] is True and paid["paid_amount"] == "100000.00"
    assert (p["tds_amount"], p["tds_section"], p["net_paid"]) == ("2000.00", "194C", "98000.00")
    lines = _lines(rig, p["id"])
    assert lines["tds_payable"] == (Decimal(0), Decimal("2000.00"))                 # owed to the government
    assert lines["sundry_creditors"] == (Decimal("100000.00"), Decimal(0))          # the bill is settled in full
    assert sum(c for _, c in lines.values()) == sum(d for d, _ in lines.values()) == Decimal("100000.00")
    bank = [k for k in lines if k not in ("tds_payable", "sundry_creditors")]
    assert len(bank) == 1 and lines[bank[0]][1] == Decimal("98000.00")              # the vendor gets the rest


def test_an_individual_is_deducted_one_percent(client, rig):
    inv = _bill(client, rig, _vendor(client, rig, "Ramesh Plumber", constitution="individual_proprietor",
                                     pan_number=PERSON_PAN, mobile="9876543215", category="plumbing")["id"], "50000")
    p = _last_payment(_pay(client, rig, inv["id"], "50000"))
    assert (p["tds_rate"], p["tds_amount"]) == ("1.0000", "500.00")


def test_a_huf_is_taxed_like_an_individual(client, rig):
    inv = _bill(client, rig, _vendor(client, rig, "Joshi HUF", constitution="huf", pan_number="ABCHE1234F",
                                     mobile="9876543216")["id"], "40000")
    assert _preview(client, rig, inv["id"], "40000")["tds_amount"] == "400.00"


def test_gst_on_the_bill_is_left_out_of_the_tds(client, rig):
    inv = _bill(client, rig, _vendor(client, rig)["id"], "100000", gst="18000")
    shown = _preview(client, rig, inv["id"], "118000")
    assert shown["taxable_value"] == "100000.00" and shown["tds_amount"] == "2000.00" and shown["net_payable"] == "116000.00"
    half = _preview(client, rig, inv["id"], "59000")                        # a part payment takes its share
    assert half["taxable_value"] == "50000.00" and half["tds_amount"] == "1000.00"


def test_small_payments_are_left_alone_until_the_years_limit_is_crossed(client, rig):
    vid = _vendor(client, rig)["id"]
    bills = [_bill(client, rig, vid, "20000", number=f"S-{i}") for i in range(6)]
    for b in bills[:5]:                                                       # 5 x 20,000 = the 1,00,000 limit, not over it
        shown = _preview(client, rig, b["id"], "20000")
        assert not shown["applies"] and "No TDS: under" in shown["note"]
        assert _last_payment(_pay(client, rig, b["id"], "20000"))["tds_amount"] == "0.00"
    last = _preview(client, rig, bills[5]["id"], "20000")                     # the 6th takes it over: all 1,20,000 is taxed
    assert last["applies"] and last["tds_base"] == "120000.00" and last["tds_amount"] == "2400.00"
    assert "paid earlier this year" in last["note"]
    p = _last_payment(_pay(client, rig, bills[5]["id"], "20000"))
    assert p["tds_amount"] == "2400.00"
    # the catch-up is not taken twice
    more = _bill(client, rig, vid, "10000", number="S-7")
    assert _preview(client, rig, more["id"], "10000")["tds_amount"] == "200.00"


def test_one_payment_over_the_single_limit_is_taxed_on_its_own(client, rig):
    vid = _vendor(client, rig)["id"]
    inv = _bill(client, rig, vid, "35000")
    shown = _preview(client, rig, inv["id"], "35000")
    assert shown["applies"] and shown["tds_base"] == "35000.00" and shown["tds_amount"] == "700.00"


def test_the_years_total_starts_again_on_the_first_of_april(client, rig):
    vid = _vendor(client, rig)["id"]
    march = _bill(client, rig, vid, "90000", number="M-1", on=date(2026, 3, 1))
    _pay(client, rig, march["id"], "90000", on=date(2026, 3, 20))              # TDS (over the 30,000 single limit)
    april = _bill(client, rig, vid, "20000", number="A-1", on=date(2026, 4, 1))
    shown = _preview(client, rig, april["id"], "20000", on=date(2026, 4, 5))   # a new year: nothing carried over
    assert not shown["applies"] and "No TDS: under" in shown["note"]


def test_no_pan_means_twenty_percent(client, rig):
    inv = _bill(client, rig, _vendor(client, rig, "Cash Contractor", pan_number=None, mobile="9876543217")["id"], "50000")
    shown = _preview(client, rig, inv["id"], "50000")
    assert shown["rate"] == "20" or shown["rate"].startswith("20")
    assert shown["tds_amount"] == "10000.00" and "no PAN" in shown["note"]


def test_a_lower_deduction_certificate_applies_only_while_it_is_valid(client, rig):
    v = _vendor(client, rig, "Certified Co", mobile="9876543218", tds_lower_rate="0.5", tds_lower_cert_no="LDC/2026/77",
                tds_lower_valid_from="2026-04-01", tds_lower_valid_to="2026-09-30")
    inv = _bill(client, rig, v["id"], "100000", on=date(2026, 5, 1))
    inside = _preview(client, rig, inv["id"], "100000", on=date(2026, 6, 1))
    assert inside["tds_amount"] == "500.00" and "LDC/2026/77" in inside["note"]
    outside = _preview(client, rig, inv["id"], "100000", on=date(2026, 10, 10))
    assert outside["tds_amount"] == "2000.00"


def test_a_vendor_with_no_type_set_is_paid_in_full_and_told_why(client, rig):
    plain = client.post(f"{V}/", headers=rig["admin"], json={
        "society_id": rig["sid"], "company_name": "Legacy Vendor", "mobile": "9876543219", "category": "civil"}).json()
    inv = _bill(client, rig, plain["id"], "100000")
    shown = _preview(client, rig, inv["id"], "100000")
    assert not shown["applies"] and shown["tds_amount"] == "0.00" and shown["note"] == ""
    p = _last_payment(_pay(client, rig, inv["id"], "100000"))
    assert p["tds_amount"] == "0.00" and p["net_paid"] == "100000.00"
    assert "tds_payable" not in _lines(rig, p["id"])


def test_tds_already_taken_on_the_bill_is_not_taken_again(client, rig):
    from app.modules.vendor.models.vendor import VendorInvoice
    inv = _bill(client, rig, _vendor(client, rig)["id"], "100000", number="X-1")
    row = rig["db"].query(VendorInvoice).filter(VendorInvoice.id == UUID(inv["id"])).one()
    row.tds_applicable, row.tds_amount, row.tds_section = True, Decimal("2000.00"), "194C"   # taken when the bill was booked
    rig["db"].commit()
    shown = _preview(client, rig, inv["id"], "98000")
    assert not shown["applies"] and "already deducted" in shown["note"]


def test_a_reversed_payment_takes_its_tds_with_it(client, rig):
    vid = _vendor(client, rig)["id"]
    one = _bill(client, rig, vid, "50000", number="R-1")
    paid = _pay(client, rig, one["id"], "50000")
    p = _last_payment(paid)
    assert client.post(f"{V}/payments/{p['id']}/reverse", headers=rig["manager"], json={"reason": "wrong bank"}).status_code == 200
    register = client.get(f"{V}/tds/register/{rig['sid']}", headers=rig["manager"]).json()
    assert register["rows"] == [] and register["total_tds"] == "0"
    again = _bill(client, rig, vid, "35000", number="R-2")
    assert _preview(client, rig, again["id"], "35000")["tds_base"] == "35000.00"    # the reversed one no longer counts


def test_the_register_lists_what_was_deducted_and_when_it_is_due(client, rig):
    vid = _vendor(client, rig)["id"]
    a = _bill(client, rig, vid, "60000", number="G-1", on=date(2026, 3, 1))
    b = _bill(client, rig, vid, "70000", number="G-2", on=date(2026, 5, 1))
    _pay(client, rig, a["id"], "60000", on=date(2026, 3, 15))
    _pay(client, rig, b["id"], "70000", on=date(2026, 5, 20))
    out = client.get(f"{V}/tds/register/{rig['sid']}", headers=rig["manager"]).json()
    rows = {r["payment_date"]: r for r in out["rows"]}
    assert rows["2026-03-15"]["deposit_due"] == "2026-04-30"                  # March's is due on 30 April
    assert rows["2026-05-20"]["deposit_due"] == "2026-06-07"                  # others on the 7th of the next month
    assert rows["2026-05-20"]["tds_amount"] == "1400.00" and rows["2026-05-20"]["pan"] == COMPANY_PAN
    assert out["total_tds"] == "2600.00"
    only_may = client.get(f"{V}/tds/register/{rig['sid']}", headers=rig["manager"],
                          params={"from_date": "2026-05-01", "to_date": "2026-05-31"}).json()
    assert len(only_may["rows"]) == 1


def test_a_payment_before_any_rule_applies_is_not_taxed_and_says_so(client, rig):
    vid = _vendor(client, rig)["id"]
    inv = _bill(client, rig, vid, "100000", number="E-1", on=date(2025, 2, 1))
    shown = _preview(client, rig, inv["id"], "100000", on=date(2025, 3, 1))
    assert not shown["applies"] and "No TDS rate is set" in shown["note"]


# ── The society's rules ──────────────────────────────────────────────────────

def test_the_societys_rules_are_filled_in_and_can_be_corrected_by_the_admin(client, rig):
    rules = client.get(f"{V}/tds/rules/{rig['sid']}", headers=rig["manager"]).json()
    by = {r["code"]: r for r in rules}
    assert by["TDS-194C-individual_huf"]["rate"] == "1.0000" and by["TDS-194C-other"]["rate"] == "2.0000"
    assert by["TDS-194C-other"]["yearly_limit"] == "100000.00" and by["TDS-194C-other"]["single_limit"] == "30000.00"
    assert by["TDS-194J_PROF-any"]["rate"] == "10.0000" and by["TDS-194J_TECH-any"]["rate"] == "2.0000"
    assert len(rules) == 7

    inv = _bill(client, rig, _vendor(client, rig)["id"], "100000")
    assert client.patch(f"{V}/tds/rules/{by['TDS-194C-other']['id']}", headers=rig["manager"],
                        json={"rate": "5"}).status_code == 403
    ok = client.patch(f"{V}/tds/rules/{by['TDS-194C-other']['id']}", headers=rig["admin"], json={"rate": "1.5"})
    assert ok.status_code == 200
    assert _preview(client, rig, inv["id"], "100000")["tds_amount"] == "1500.00"
    assert len(client.get(f"{V}/tds/rules/{rig['sid']}", headers=rig["manager"]).json()) == 7    # edits are not overwritten


def test_another_society_cannot_see_or_change_these_rules(client, db, rig):
    other = make_society(db, "Other TDS Society")
    outsider = make_user(db, "admin@other-tds.test", role="Society Admin")
    outsider["user"].society_id = other.id
    db.commit()
    assert client.get(f"{V}/tds/rules/{rig['sid']}", headers=outsider["headers"]).status_code in (403, 404)
    rule = client.get(f"{V}/tds/rules/{rig['sid']}", headers=rig["manager"]).json()[0]
    assert client.patch(f"{V}/tds/rules/{rule['id']}", headers=outsider["headers"], json={"rate": "9"}).status_code in (403, 404)


def test_residents_cannot_use_the_tds_endpoints(client, db, rig):
    res = make_user(db, "res@tds.test", role="Resident")
    res["user"].society_id = rig["society"].id
    db.commit()
    assert client.get(f"{V}/tds/options", headers=res["headers"]).status_code == 403
    assert client.get(f"{V}/tds/register/{rig['sid']}", headers=res["headers"]).status_code == 403


# ── The starting rates, held to the FY 2026-27 chart (section 393 of the Income-tax Act, 2025) ─────────────────

def test_default_rules_match_the_fy_2026_27_chart():
    """section, payee class -> (rate %, yearly limit, single-payment limit). If the law changes, change the chart and
    docs/TDS_RATES.md with the rules."""
    from app.modules.vendor.services.vendor_tds import DEFAULT_RULES
    chart = {
        ("194C", "individual_huf"): ("1", "100000", "30000"),
        ("194C", "other"): ("2", "100000", "30000"),
        ("194J_PROF", "any"): ("10", "50000", None),
        ("194J_TECH", "any"): ("2", "50000", None),
        ("194I_PM", "any"): ("2", "600000", None),
        ("194I_LB", "any"): ("10", "600000", None),
        ("194H", "any"): ("2", "20000", None),
    }
    assert {(s, k): (r, y, one) for s, k, r, y, one, _ in DEFAULT_RULES} == chart


def test_a_vendors_filing_status_never_changes_the_rate():
    """Section 206AB was omitted from 1 April 2025, so nothing in the TDS code should ask whether the vendor files returns."""
    import inspect
    from app.modules.vendor.services import vendor_tds
    code = inspect.getsource(vendor_tds.compute_payment_tds).lower()
    assert "itr" not in code and "non_filer" not in code and "206ab" not in code
