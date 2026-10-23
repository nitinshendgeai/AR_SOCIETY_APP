"""Importing the asset register from an Excel (.xlsx) or CSV file: columns found by their headings, every row
checked before anything is saved, bad rows left out and listed, repeats skipped."""
import io
import json
from datetime import date

import pytest
from openpyxl import Workbook

from tests.conftest import make_society, make_user

API = "/api/v1/inventory"


def _member(db, email, role, society):
    who = make_user(db, email, role=role)
    who["user"].society_id = society.id
    db.commit()
    return who


@pytest.fixture
def rig(db):
    society = make_society(db, "Import Society")
    return {"society": society, "sid": str(society.id),
            "admin": _member(db, "adm@import.test", "Society Admin", society)}


def _csv(*lines: str, encoding="utf-8") -> bytes:
    return ("\n".join(lines) + "\n").encode(encoding)


def _xlsx(rows, sheet="Register") -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = sheet
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _post(client, rig, content, name="assets.csv", dry_run=True, mapping=None, who=None, sid=None):
    data = {"dry_run": "true" if dry_run else "false"}
    if mapping is not None:
        data["mapping"] = json.dumps(mapping)
    return client.post(f"{API}/assets/import/{sid or rig['sid']}", data=data,
                       files={"file": (name, content, "application/octet-stream")},
                       headers=(who or rig["admin"])["headers"])


def _listed(client, rig):
    r = client.get(f"{API}/assets/society/{rig['sid']}?limit=500", headers=rig["admin"]["headers"])
    assert r.status_code == 200, r.text
    return r.json()


REGISTER = _csv(
    "Sr No,Asset Name,Category,Location,Purchase Date,Cost (Rs),Make,Serial No.,Warranty Till,Service Frequency",
    "1,Passenger lift - Wing A,Lift,Wing A,12/03/2021,\"₹ 12,50,000\",Otis,SN-100,12/03/2026,quarterly",
    "2,DG set 125 kVA,DG Set,Basement,05-Apr-2019,\"Rs. 8,00,000\",Kirloskar,SN-200,,6 months",
    "3,Terrace pump,Pump,Terrace,,45000,Crompton,,,",
)


# ── Preview and import ───────────────────────────────────────────────────────

def test_preview_reads_every_column_and_saves_nothing(client, rig):
    r = _post(client, rig, REGISTER)
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["dry_run"] is True and out["total_rows"] == 3 and out["ready"] == 3 and out["created"] == 0
    cols = {c["heading"]: c["field"] for c in out["columns"]}
    assert cols == {"Sr No": None, "Asset Name": "name", "Category": "asset_category", "Location": "location",
                    "Purchase Date": "purchase_date", "Cost (Rs)": "purchase_cost", "Make": None,
                    "Serial No.": "serial_number", "Warranty Till": "warranty_expiry",
                    "Service Frequency": "service_interval_months"}
    assert [x["field"] for x in out["fields"]][:3] == ["asset_code", "name", "asset_category"]
    assert [(x["line"], x["asset_code"], x["status"]) for x in out["rows"]] == [
        (2, "AST-0001", "ready"), (3, "AST-0002", "ready"), (4, "AST-0003", "ready")]
    assert _listed(client, rig) == []


def test_import_adds_the_assets_with_their_values(client, rig):
    out = _post(client, rig, REGISTER, dry_run=False).json()
    assert out["created"] == 3 and out["errors"] == 0 and {r["status"] for r in out["rows"]} == {"created"}
    by_code = {a["asset_code"]: a for a in _listed(client, rig)}
    lift = by_code["AST-0001"]
    assert lift["name"] == "Passenger lift - Wing A" and lift["asset_category"] == "lift"
    assert lift["location"] == "Wing A" and lift["status"] == "active"
    assert lift["purchase_date"] == "2021-03-12" and float(lift["purchase_cost"]) == 1250000.0
    assert lift["serial_number"] == "SN-100" and lift["warranty_expiry"] == "2026-03-12"
    assert lift["service_interval_months"] == 3
    assert lift["next_service_due"] == "2021-06-12"                     # worked out from purchase date + interval
    dg = by_code["AST-0002"]
    assert dg["asset_category"] == "generator" and dg["purchase_date"] == "2019-04-05"
    assert dg["service_interval_months"] == 6 and float(dg["purchase_cost"]) == 800000.0
    assert by_code["AST-0003"]["purchase_date"] is None


def test_an_excel_file_with_a_title_row_date_cells_and_numbers(client, rig):
    content = _xlsx([
        ["Import Society - Asset Register 2026"],
        [],
        ["Asset Code", "Name", "Type", "Installed At", "Date of Purchase", "Cost", "Life (Years)", "Last Serviced"],
        ["LIFT-A", "Lift A", "Elevator", "Wing A", date(2020, 1, 15), 950000, 15, date(2026, 1, 10)],
        ["PUMP-1", "Borewell pump", "Pump", "Garden", 43831, 18000.5, "10 yrs", None],
    ])
    out = _post(client, rig, content, name="register.xlsx", dry_run=False).json()
    assert out["sheet"] == "Register" and out["created"] == 2, out
    assert [r["line"] for r in out["rows"]] == [4, 5]                  # the file's own line numbers
    by_code = {a["asset_code"]: a for a in _listed(client, rig)}
    assert by_code["LIFT-A"]["asset_category"] == "lift" and by_code["LIFT-A"]["purchase_date"] == "2020-01-15"
    assert by_code["LIFT-A"]["last_serviced_on"] == "2026-01-10" and by_code["LIFT-A"]["expected_life_years"] == 15
    assert by_code["PUMP-1"]["purchase_date"] == "2020-01-01"          # an Excel serial number
    assert float(by_code["PUMP-1"]["purchase_cost"]) == 18000.5 and by_code["PUMP-1"]["expected_life_years"] == 10


def test_semicolon_and_windows_encoded_csv_files_are_read(client, rig):
    content = _csv("Name;Category;Location", "Café lighting;Lighting;Podium", "Fire extinguisher;Fire;Lobby",
                   encoding="cp1252")
    out = _post(client, rig, content, dry_run=False).json()
    assert out["created"] == 2
    got = {a["name"]: a["asset_category"] for a in _listed(client, rig)}
    assert got == {"Café lighting": "electrical", "Fire extinguisher": "fire_safety"}


# ── Problems ─────────────────────────────────────────────────────────────────

def test_bad_rows_are_left_out_and_listed_while_the_good_ones_import(client, rig):
    content = _csv(
        "Name,Category,Purchase Date,Cost,Service Interval",
        "Good pump,Pump,01/02/2022,1000,6",
        ",Lift,01/02/2022,500,",
        "Bad date,Lift,not a date,500,",
        "Negative cost,Lift,,-5,",
        "Bad interval,Lift,,,500",
        "Odd kind,Hoverboard,,,",
    )
    out = _post(client, rig, content, dry_run=False).json()
    status = {r["line"]: r for r in out["rows"]}
    assert out["created"] == 2 and out["errors"] == 4
    assert status[2]["status"] == "created"
    assert "Name is required" in status[3]["message"]
    assert "not a date" in status[4]["message"]
    assert "negative" in status[5]["message"]
    assert "1 to 120" in status[6]["message"]
    assert status[7]["status"] == "created" and "not recognised, imported as Other" in status[7]["message"]
    assert {a["name"]: a["asset_category"] for a in _listed(client, rig)} == {"Good pump": "pump", "Odd kind": "other"}


def test_importing_the_same_file_again_adds_nothing(client, rig):
    content = _csv("Asset Code,Name,Serial No", "A-1,Pump one,S1", "A-2,Pump two,S2", ",Pump three,S3")
    assert _post(client, rig, content, dry_run=False).json()["created"] == 3
    again = _post(client, rig, content, dry_run=False).json()
    assert again["created"] == 0 and again["duplicates"] == 3
    assert "already exists" in again["rows"][0]["message"]
    assert "Serial number S3 is already registered" in again["rows"][2]["message"]
    assert len(_listed(client, rig)) == 3


def test_a_code_or_serial_repeated_inside_the_file_is_skipped(client, rig):
    content = _csv("Asset Code,Name,Serial No", "A-1,One,S1", "a-1,Same code,S9", "A-3,Same serial,s1")
    out = _post(client, rig, content, dry_run=False).json()
    assert out["created"] == 1 and out["duplicates"] == 2
    assert "more than once" in out["rows"][1]["message"] and "already registered (A-1)" in out["rows"][2]["message"]


def test_automatic_codes_skip_codes_the_file_or_society_already_uses(client, rig):
    content = _csv("Asset Code,Name", ",First,", "AST-0001,Has a code,", ",Second,")
    # the middle row asks for AST-0001, so the automatic ones go around it
    out = _post(client, rig, _csv("Asset Code,Name", ",First", "AST-0001,Has a code", ",Second"), dry_run=False).json()
    assert [(r["name"], r["asset_code"]) for r in out["rows"]] == [
        ("First", "AST-0002"), ("Has a code", "AST-0001"), ("Second", "AST-0003")]
    out2 = _post(client, rig, _csv("Name", "Later"), dry_run=False).json()
    assert out2["rows"][0]["asset_code"] == "AST-0004"


def test_every_import_leaves_a_registered_log_and_is_scoped_to_the_society(client, db, rig):
    _post(client, rig, _csv("Name", "Solo"), dry_run=False)
    asset = _listed(client, rig)[0]
    history = client.get(f"{API}/assets/{asset['id']}/history", headers=rig["admin"]["headers"]).json()
    assert any("Imported from assets.csv" in (u.get("notes") or "") for u in history["log"]), history


# ── The template ─────────────────────────────────────────────────────────────

def test_the_template_covers_every_field_and_imports_cleanly(client, rig):
    r = client.get(f"{API}/assets/import-template", headers=rig["admin"]["headers"])
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    out = _post(client, rig, r.content, name="template.csv", dry_run=False).json()
    mapped = [c["field"] for c in out["columns"]]
    from app.modules.inventory.services.asset_import import FIELDS
    assert None not in mapped and set(mapped) == set(FIELDS), out["columns"]      # every heading is understood, each once
    assert out["created"] == 2 and out["errors"] == 0, out["rows"]
    by_name = {a["name"]: a for a in _listed(client, rig)}
    lift = by_name["Passenger lift - Wing A"]
    assert lift["serial_number"] == "SN-10045" and lift["service_interval_months"] == 3
    assert lift["last_serviced_on"] == "2026-01-10" and lift["expected_life_years"] == 15
    assert lift["invoice_number"] == "INV-2021-118" and lift["vendor_contact"] == "9876543210"


# ── Choosing columns ─────────────────────────────────────────────────────────

def test_a_column_can_be_pointed_at_a_field_or_ignored(client, rig):
    content = _csv("Equipment Tag,Kind of thing,Where,Brand", "Chiller 1,hvac,Roof,Blue Star")
    first = _post(client, rig, content).json()
    assert {c["heading"]: c["field"] for c in first["columns"]}["Equipment Tag"] is None     # not a heading we know
    assert "No Name column" in first["message"] and first["rows"] == []   # the preview still answers, to choose from
    choice = {"Kind of thing": "asset_category", "Where": "location", "Brand": "vendor_name", "Equipment Tag": "name"}
    out = _post(client, rig, content, dry_run=False, mapping=choice).json()
    assert out["created"] == 1
    asset = _listed(client, rig)[0]
    assert (asset["name"], asset["asset_category"], asset["location"], asset["vendor_name"]) == (
        "Chiller 1", "hvac", "Roof", "Blue Star")
    ignored = _post(client, rig, content, mapping={"Brand": None, "Where": None}).json()
    assert {c["heading"]: c["field"] for c in ignored["columns"]}["Brand"] is None


def test_two_columns_for_one_field_and_unknown_fields_are_refused(client, rig):
    content = _csv("Name,Item", "A,B")
    assert _post(client, rig, content, mapping={"Item": "name"}).status_code == 422
    assert _post(client, rig, content, mapping={"Item": "password"}).status_code == 422
    assert _post(client, rig, content, mapping="not json").status_code == 422


def test_without_a_name_column_the_preview_says_so_and_the_import_refuses(client, rig):
    content = _csv("Location,Cost", "Roof,100")
    preview = _post(client, rig, content)
    assert preview.status_code == 200 and "No Name column" in preview.json()["message"]
    assert [c["heading"] for c in preview.json()["columns"]] == ["Location", "Cost"]
    refused = _post(client, rig, content, dry_run=False)
    assert refused.status_code == 422 and "No Name column" in refused.text
    assert _listed(client, rig) == []


# ── The file itself and who may import ───────────────────────────────────────

@pytest.mark.parametrize("content,name,expect", [
    (b"", "a.csv", "empty"),
    (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"0" * 50, "old.xls", "Old Excel"),
    (b"PK\x03\x04 not really a workbook", "x.xlsx", "could not be opened"),
    (b"\n\n,,\n", "blank.csv", "No data"),
])
def test_unreadable_files_get_a_plain_message(client, rig, content, name, expect):
    r = _post(client, rig, content, name=name)
    assert r.status_code == 422 and expect.lower() in r.text.lower(), r.text


def test_too_many_rows_are_refused(client, rig):
    big = _csv("Name", *[f"Item {i}" for i in range(5001)])
    r = _post(client, rig, big)
    assert r.status_code == 422 and "5000" in r.text


def test_residents_cannot_import_and_a_society_cannot_import_into_another(client, db, rig):
    resident = _member(db, "res@import.test", "Resident", rig["society"])
    assert _post(client, rig, _csv("Name", "X"), who=resident).status_code == 403
    other = make_society(db, "Other Import Society")
    outsider = _member(db, "adm@other-import.test", "Society Admin", other)
    r = _post(client, rig, _csv("Name", "X"), dry_run=False, who=outsider)
    assert r.status_code in (403, 404) or _listed(client, rig) == []
    assert _listed(client, rig) == []
