"""The Residents report: only the columns chosen, as a PDF or an Excel file, following the list's filters, for the office
only, with identity numbers cut to their last four characters."""
from datetime import date
from io import BytesIO

import pytest
from openpyxl import load_workbook
from pdfminer.high_level import extract_text

from app.models.resident import Resident, ResidentType
from app.models.wing import Wing
from tests.conftest import make_flat, make_society, make_user, make_wing

URL = "/api/v1/residents/report"


@pytest.fixture
def rig(db):
    society = make_society(db, "Residents Report Society")
    admin = make_user(db, "rr-admin@x.test", role="Society Admin")
    admin["user"].society_id = society.id
    resident = make_user(db, "rr-resident@x.test", role="Resident")
    resident["user"].society_id = society.id
    wing_a = make_wing(db, society.id, "Wing A")
    wing_b = Wing(society_id=society.id, name="Wing B", code="B")
    db.add(wing_b)
    db.commit()
    a1, b1 = make_flat(db, wing_a.id, "101"), make_flat(db, wing_b.id, "201")
    other = make_society(db, "Other Society")
    other_flat = make_flat(db, make_wing(db, other.id, "Wing Z").id, "901")
    db.add_all([
        Resident(flat_id=a1.id, full_name="Asha Rao", resident_type=ResidentType.OWNER, is_primary=True,
                 phone="09876500001", email="asha@x.test", date_of_birth=date(1980, 5, 17),
                 move_in_date=date(2020, 4, 1), id_proof_type="Aadhaar", id_proof_number="123456789012",
                 emergency_contact_name="Ravi", emergency_contact_phone="9000000001"),
        Resident(flat_id=a1.id, full_name="=HYPERLINK(\"http://evil\")", resident_type=ResidentType.FAMILY, phone="+919000000002"),
        Resident(flat_id=b1.id, full_name="Vik Mehta", resident_type=ResidentType.OWNER, is_primary=True, phone="9876500003"),
        Resident(flat_id=other_flat.id, full_name="Outsider Person", resident_type=ResidentType.OWNER, is_primary=True),
    ])
    db.commit()
    return {"h": admin["headers"], "resident_h": resident["headers"], "wing_a": wing_a}


def _pdf_text(r) -> str:
    assert r.status_code == 200, r.text
    assert r.content[:5] == b"%PDF-"
    return extract_text(BytesIO(r.content))


def _sheet(r):
    assert r.status_code == 200, r.text
    assert "spreadsheetml" in r.headers["content-type"]
    return load_workbook(BytesIO(r.content))["Residents"]


def _table(ws):
    """(header row, data rows) below the title block."""
    rows = [[c.value for c in row] for row in ws.iter_rows(min_row=6)]
    return rows[0], rows[1:]


def test_the_picker_lists_the_columns_with_a_default_set(client, rig):
    cols = client.get(f"{URL}-columns", headers=rig["h"]).json()
    by = {c["key"]: c for c in cols}
    assert by["name"]["default"] and by["flat"]["default"] and not by["id_proof"]["default"]
    assert by["id_proof"]["sensitive"] and by["dob"]["sensitive"] and not by["phone"]["sensitive"]


def test_only_the_chosen_columns_are_in_the_excel_file(client, rig):
    ws = _sheet(client.get(URL, params={"format": "xlsx", "columns": "name,phone,move_in"}, headers=rig["h"]))
    head, rows = _table(ws)
    assert head == ["Sr.", "Name", "Mobile", "Moved in"]                    # the catalogue's order, nothing else
    asha = next(r for r in rows if r[1] == "Asha Rao")
    assert asha[2] == "09876500001"                                          # kept as text: the leading zero survives
    assert asha[3].date() == date(2020, 4, 1)                                # a real date, not text
    assert len(rows) == 3 and all(r[1] != "Outsider Person" for r in rows)   # this society's residents only


def test_default_columns_when_none_are_chosen_and_the_pdf_follows_them(client, rig):
    head, _ = _table(_sheet(client.get(URL, params={"format": "xlsx"}, headers=rig["h"])))
    assert head == ["Sr.", "Flat", "Name", "Type", "Mobile", "Email"]
    text = _pdf_text(client.get(URL, headers=rig["h"]))
    assert "RESIDENTS REPORT" in text and "Asha Rao" in text and "Vik Mehta" in text
    assert "Outsider Person" not in text and "3 residents" in text
    picked = _pdf_text(client.get(URL, params={"columns": "name,email"}, headers=rig["h"]))
    assert "asha@x.test" in picked and "9876500001" not in picked          # a column not chosen is not printed


def test_identity_numbers_are_never_printed_in_full(client, rig):
    pdf = _pdf_text(client.get(URL, params={"columns": "name,id_proof"}, headers=rig["h"]))
    xl = _sheet(client.get(URL, params={"format": "xlsx", "columns": "name,id_proof"}, headers=rig["h"]))
    cell = next(r[2] for r in _table(xl)[1] if r[1] == "Asha Rao")
    assert cell == "Aadhaar XXXXXXXX9012"
    assert "123456789012" not in pdf and "9012" in pdf


def test_a_name_that_looks_like_a_formula_stays_text(client, rig):
    ws = _sheet(client.get(URL, params={"format": "xlsx", "columns": "name"}, headers=rig["h"]))
    evil = next(c for row in ws.iter_rows(min_row=7) for c in row if isinstance(c.value, str) and c.value.startswith("=HYPERLINK"))
    assert evil.data_type == "s"


def test_the_report_follows_the_filters_on_the_list(client, rig):
    h = rig["h"]
    wing = _table(_sheet(client.get(URL, params={"format": "xlsx", "columns": "name", "wing_id": str(rig["wing_a"].id)}, headers=h)))[1]
    assert sorted(r[1] for r in wing) == sorted(["Asha Rao", '=HYPERLINK("http://evil")'])
    searched = _pdf_text(client.get(URL, params={"search": "vik"}, headers=h))
    assert "Vik Mehta" in searched and "Asha Rao" not in searched and 'search "vik"' in searched and "1 resident" in searched
    typed = _table(_sheet(client.get(URL, params={"format": "xlsx", "columns": "name,type", "resident_type": "family"}, headers=h)))[1]
    assert len(typed) == 1 and typed[0][2] == "Family"


def test_unknown_columns_and_formats_are_refused_and_residents_cannot_print(client, rig):
    assert client.get(URL, params={"columns": "name,salary"}, headers=rig["h"]).status_code == 422
    assert client.get(URL, params={"format": "docx"}, headers=rig["h"]).status_code == 422
    assert client.get(URL, headers=rig["resident_h"]).status_code == 403            # phone numbers: the office only
    assert client.get(f"{URL}-columns", headers=rig["resident_h"]).status_code == 403
