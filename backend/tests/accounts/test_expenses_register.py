"""The expenses register (every expense booked, voucher by voucher) and the documents filed against a voucher."""
from tests.accounts.test_expenses_by_element import _ledgers, _pay
from tests.billing.test_budget_suggestions import _rig
from tests.conftest import make_society, make_user

A = "/api/v1/accounts"
PDF = b"%PDF-1.4 a supplier's bill"


def _register(client, h, sid, **params):
    r = client.get(f"{A}/registers/expenses/{sid}", params=params, headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def _file(client, h, voucher_id, name="bill.pdf", data=PDF, mime="application/pdf"):
    return client.post(f"{A}/vouchers/{voucher_id}/documents", files={"file": (name, data, mime)}, headers=h)


def test_the_register_lists_each_expense_with_whether_a_document_is_filed(client, db):
    society, admin, manager, resident = _rig(db, "er1")
    sid = str(society.id)
    L = _ledgers(client, admin, sid)
    lift = _pay(client, admin, sid, L, "security_charges", 30000, "bank", narration="Guards for the month",
                reference="SEC/114")
    _pay(client, admin, sid, L, "electricity", 8450)
    gone = _pay(client, admin, sid, L, "cctv_maintenance", 999)
    assert client.post(f"{A}/vouchers/{gone['id']}/cancel", json={"reason": "wrong head"}, headers=admin).status_code == 200

    reg = _register(client, admin, sid)
    assert reg["title"] == "Expenses Register" and reg["kind"] == "expenses"
    assert [c["key"] for c in reg["columns"]][:3] == ["date", "voucher_no", "head"]
    heads = {r["head"]: r for r in reg["rows"]}
    assert set(heads) == {"Security Charges", "Electricity Charges (Common Areas)"}                    # the cancelled voucher is not an expense
    sec = heads["Security Charges"]
    assert sec["amount"] == "30000.00" and sec["particulars"] == "Guards for the month"
    assert sec["reference"] == "SEC/114" and sec["voucher_id"] == lift["id"] and sec["document"] == "None"
    totals = {t["label"]: t["value"] for t in reg["totals"]}
    assert totals["Entries"] == "2" and totals["Spent Rs."] == "38450.00" and totals["No document"] == "2"

    assert _file(client, admin, lift["id"]).status_code == 201
    reg = _register(client, admin, sid)
    assert {r["head"]: r["document"] for r in reg["rows"]} == {"Security Charges": "1 filed", "Electricity Charges (Common Areas)": "None"}
    assert {t["label"]: t["value"] for t in reg["totals"]}["With a document"] == "1"
    only_with = _register(client, admin, sid, status="with_document")
    assert [r["head"] for r in only_with["rows"]] == ["Security Charges"]
    only_without = _register(client, admin, sid, status="without_document")
    assert [r["head"] for r in only_without["rows"]] == ["Electricity Charges (Common Areas)"]
    assert [r["head"] for r in _register(client, admin, sid, q="sec/114")["rows"]] == ["Security Charges"]


def test_a_document_is_filed_listed_opened_and_removed(client, db):
    society, admin, manager, resident = _rig(db, "er2")
    sid = str(society.id)
    L = _ledgers(client, admin, sid)
    v = _pay(client, admin, sid, L, "security_charges", 1000)
    assert client.get(f"{A}/vouchers/{v['id']}", headers=admin).json()["documents"] == []

    r = _file(client, admin, v["id"], name="C:\\scans\\sec bill.pdf")
    assert r.status_code == 201, r.text
    doc = r.json()
    assert doc["file_name"] == "sec bill.pdf" and doc["mime_type"] == "application/pdf" and doc["size_bytes"] == len(PDF)
    listed = client.get(f"{A}/vouchers/{v['id']}", headers=admin).json()["documents"]
    assert [d["id"] for d in listed] == [doc["id"]]
    assert "data" not in listed[0]                                              # the file is not part of the listing

    opened = client.get(f"{A}/voucher-documents/{doc['id']}/file", headers=admin)
    assert opened.status_code == 200 and opened.content == PDF
    assert opened.headers["content-type"] == "application/pdf"

    assert client.delete(f"{A}/voucher-documents/{doc['id']}", headers=admin).status_code == 204
    assert client.get(f"{A}/vouchers/{v['id']}", headers=admin).json()["documents"] == []
    assert client.get(f"{A}/voucher-documents/{doc['id']}/file", headers=admin).status_code == 404


def test_only_a_pdf_or_a_picture_within_the_limits_is_accepted(client, db):
    society, admin, manager, resident = _rig(db, "er3")
    sid = str(society.id)
    L = _ledgers(client, admin, sid)
    v = _pay(client, admin, sid, L, "security_charges", 1000)
    assert _file(client, admin, v["id"], "x.exe", b"MZ", "application/octet-stream").status_code == 422
    assert _file(client, admin, v["id"], "empty.pdf", b"").status_code == 422
    assert _file(client, admin, v["id"], "big.pdf", b"0" * (8 * 1024 * 1024 + 1)).status_code == 422
    assert _file(client, admin, v["id"], "photo.jpg", b"\xff\xd8\xff", "image/jpeg").status_code == 201
    for i in range(9):
        assert _file(client, admin, v["id"], f"p{i}.png", b"\x89PNG", "image/png").status_code == 201
    assert _file(client, admin, v["id"], "eleventh.png", b"\x89PNG", "image/png").status_code == 422


def test_documents_and_the_register_are_for_managers_of_the_same_society(client, db):
    society, admin, manager, resident = _rig(db, "er4")
    sid = str(society.id)
    L = _ledgers(client, admin, sid)
    v = _pay(client, admin, sid, L, "security_charges", 1000)
    doc = _file(client, admin, v["id"]).json()
    assert client.get(f"{A}/registers/expenses/{sid}", headers=resident).status_code == 403
    assert _file(client, resident, v["id"]).status_code == 403
    assert client.get(f"{A}/voucher-documents/{doc['id']}/file", headers=resident).status_code == 403
    assert client.get(f"{A}/voucher-documents/{doc['id']}/file", headers=manager).status_code == 200

    rival = make_society(db, "Rival er4")
    outsider = make_user(db, "mgr@rival-er4.com", role="Manager")
    outsider["user"].society_id = rival.id                    # a manager of another society
    db.commit()
    assert client.get(f"{A}/registers/expenses/{sid}", headers=outsider["headers"]).status_code == 403
    assert client.get(f"{A}/voucher-documents/{doc['id']}/file", headers=outsider["headers"]).status_code == 403
    assert _file(client, outsider["headers"], v["id"]).status_code == 403


def test_the_expenses_register_prints_and_exports(client, db):
    society, admin, manager, resident = _rig(db, "er5")
    sid = str(society.id)
    L = _ledgers(client, admin, sid)
    _pay(client, admin, sid, L, "security_charges", 1000, narration="Guards")
    pdf = client.get(f"{A}/registers/expenses/{sid}", params={"format": "pdf"}, headers=admin)
    assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"
    csv = client.get(f"{A}/registers/expenses/{sid}", params={"format": "csv"}, headers=admin)
    lines = csv.text.splitlines()
    assert lines[0].startswith("Date,Voucher,Expense head,Paid to") and "Security Charges" in lines[1]
