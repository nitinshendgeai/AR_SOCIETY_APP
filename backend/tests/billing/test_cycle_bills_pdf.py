"""All the bills of a cycle in one PDF: the print-everything step a society does each month."""
import re
import uuid

from app.modules.billing.services.billing_service import _flat_sort_key
from tests.billing.test_maintenance_billing import _generated_cycle
from tests.conftest import make_society, make_user

B = "/api/v1/billing"


def _pages(pdf: bytes) -> int:
    return len(re.findall(rb"/Type /Page(?!s)", pdf))


def test_every_bill_of_the_cycle_comes_in_one_pdf(client, db):
    society, flat1, flat2, manager, resident, other, cycle_id = _generated_cycle(client, db, "all1")
    r = client.get(f"{B}/cycles/{cycle_id}/bills.pdf", headers=manager["headers"])
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/pdf" and r.content.startswith(b"%PDF")
    assert r.headers["x-bill-count"] == "2"
    assert "Bills-" in r.headers["content-disposition"]
    # Each bill printed on its own: the one file has as many pages as the bills have apart.
    bills = client.get(f"{B}/cycles/{cycle_id}/bills", headers=manager["headers"]).json()
    apart = sum(_pages(client.get(f"{B}/bills/{b['id']}/pdf", headers=manager["headers"]).content) for b in bills)
    assert _pages(r.content) == apart >= 2


def test_it_can_be_limited_to_a_status_and_leaves_out_cancelled_bills(client, db):
    society, flat1, flat2, manager, resident, other, cycle_id = _generated_cycle(client, db, "all2")
    url = f"{B}/cycles/{cycle_id}/bills.pdf"
    assert client.get(url, headers=manager["headers"], params={"status": "generated"}).headers["x-bill-count"] == "2"
    r = client.get(url, headers=manager["headers"], params={"status": "issued"})
    assert r.status_code == 404                                    # none issued yet
    client.post(f"{B}/cycles/{cycle_id}/issue-all", headers=manager["headers"])
    assert client.get(url, headers=manager["headers"], params={"status": "issued"}).headers["x-bill-count"] == "2"
    bills = client.get(f"{B}/cycles/{cycle_id}/bills", headers=manager["headers"]).json()
    c = client.post(f"{B}/bills/{bills[0]['id']}/cancel", headers=manager["headers"], json={"reason": "Entered twice"})
    assert c.status_code == 200, c.text
    assert client.get(url, headers=manager["headers"]).headers["x-bill-count"] == "1"
    assert client.get(url, headers=manager["headers"], params={"status": "cancelled"}).headers["x-bill-count"] == "1"
    assert client.get(url, headers=manager["headers"], params={"status": "nonsense"}).status_code == 400


def test_a_wing_with_no_bills_gives_a_clear_answer(client, db):
    society, flat1, flat2, manager, resident, other, cycle_id = _generated_cycle(client, db, "all3")
    r = client.get(f"{B}/cycles/{cycle_id}/bills.pdf", headers=manager["headers"],
                   params={"wing_id": str(uuid.uuid4())})
    assert r.status_code == 404
    wing_id = client.get(f"{B}/cycles/{cycle_id}/bills", headers=manager["headers"]).json()[0]["wing_id"]
    ok = client.get(f"{B}/cycles/{cycle_id}/bills.pdf", headers=manager["headers"], params={"wing_id": wing_id})
    assert ok.status_code == 200 and ok.headers["x-bill-count"] == "2"


def test_residents_and_other_societies_cannot_print_the_cycle(client, db):
    society, flat1, flat2, manager, resident, other, cycle_id = _generated_cycle(client, db, "all4")
    url = f"{B}/cycles/{cycle_id}/bills.pdf"
    assert client.get(url, headers=resident["headers"]).status_code == 403
    rival = make_society(db, "Rival Society all4")
    who = make_user(db, "mgr@rival-all4.com", role="Manager")
    who["user"].society_id = rival.id
    db.commit()
    assert client.get(url, headers=who["headers"]).status_code == 403


def test_flats_sort_as_people_expect():
    order = sorted(["1001", "101", "2A", "10", "102", "2", "B-1"], key=_flat_sort_key)
    assert order == ["2", "2A", "10", "101", "102", "1001", "B-1"]


def test_the_bills_come_as_a_zip_of_pdfs_named_wing_flat_month_year(client, db):
    import io
    import zipfile
    society, flat1, flat2, manager, resident, other, cycle_id = _generated_cycle(client, db, "zip1")
    r = client.get(f"{B}/cycles/{cycle_id}/bills.zip", headers=manager["headers"])
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/zip" and r.headers["x-bill-count"] == "2"
    assert "attachment" in r.headers["content-disposition"] and ".zip" in r.headers["content-disposition"]
    z = zipfile.ZipFile(io.BytesIO(r.content))
    names = z.namelist()
    assert len(names) == 2 and len(set(names)) == 2
    cycle = client.get(f"{B}/cycles/{cycle_id}", headers=manager["headers"]).json()
    bills = client.get(f"{B}/cycles/{cycle_id}/bills", headers=manager["headers"]).json()
    for b in bills:
        wing = "".join(c if c.isalnum() or c == "-" else "-" for c in b["wing_name"]).strip("-")
        flat = "".join(c if c.isalnum() or c == "-" else "-" for c in b["flat_number"]).strip("-")
        expected = [n for n in names if n.startswith(f"{wing}_{flat}_")]
        assert len(expected) == 1, (names, wing, flat)
        month_year = expected[0][len(f"{wing}_{flat}_"):-len(".pdf")]
        month, year = month_year.split("_")
        assert month.isalpha() and year.isdigit() and len(year) == 4
    for n in names:
        assert n.endswith(".pdf") and z.read(n).startswith(b"%PDF")
        assert _pages(z.read(n)) >= 1


def test_the_zip_follows_the_same_selection_and_access_rules_as_the_pdf(client, db):
    society, flat1, flat2, manager, resident, other, cycle_id = _generated_cycle(client, db, "zip2")
    url = f"{B}/cycles/{cycle_id}/bills.zip"
    assert client.get(url, headers=manager["headers"], params={"status": "issued"}).status_code == 404
    assert client.get(url, headers=manager["headers"], params={"status": "nonsense"}).status_code == 400
    assert client.get(url, headers=manager["headers"], params={"wing_id": str(uuid.uuid4())}).status_code == 404
    assert client.get(url, headers=resident["headers"]).status_code == 403


def test_bill_file_names_are_wing_flat_month_year(db):
    from datetime import date
    from types import SimpleNamespace
    from app.modules.billing.services.billing_service import BillingService
    cycle = SimpleNamespace(cycle_start=date(2026, 10, 1))
    bill = SimpleNamespace(flat=SimpleNamespace(flat_number="1001", wing=SimpleNamespace(name="A Wing")))
    assert BillingService.bill_file_name(bill, cycle) == "A-Wing_1001_October_2026.pdf"
    odd = SimpleNamespace(flat=SimpleNamespace(flat_number="B/12 ", wing=SimpleNamespace(name="Tower 2")))
    assert BillingService.bill_file_name(odd, cycle) == "Tower-2_B-12_October_2026.pdf"
