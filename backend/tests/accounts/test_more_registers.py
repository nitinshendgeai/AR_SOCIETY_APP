"""The rental, receipts and staff attendance registers: one shared shape, a printout and a spreadsheet for each."""
import re
from datetime import date, timedelta
from app.utils.local_time import local_today, zone
from decimal import Decimal

from app.models.agreement_tracker import AgreementTracker
from app.models.flat import OccupancyStatus
from app.models.tenant import Tenant
from app.modules.shops.models.shop import Shop
from app.modules.staff.models.staff import (
    AttendanceStatus, LeaveStatus, LeaveType, Staff, StaffAttendance, StaffDepartment, StaffLeave, StaffStatus,
)
from tests.accounts.test_accounts import _issued_bills
from tests.billing.test_maintenance_billing import _rig
from tests.conftest import make_society, make_user

A = "/api/v1/accounts/registers"


def _col(reg, key):
    return next(c for c in reg["columns"] if c["key"] == key)


# ── Rental register ───────────────────────────────────────────────────────────

def test_rental_register_lists_tenancies_with_rent_deposit_and_days_left(client, db):
    society, flat1, flat2, manager, *_ = _rig(db, "mr1")
    h, sid = manager["headers"], str(society.id)
    today = local_today(zone(None))
    running = Tenant(flat_id=flat1.id, full_name="Ravi Tenant", phone="9000000001", monthly_rent=Decimal("20000"),
                     security_deposit=Decimal("60000"), agreement_start_date=today - timedelta(days=100),
                     agreement_end_date=today + timedelta(days=265), agreement_channel="agent",
                     agreement_channel_name="Sai Realty")
    expiring = Tenant(flat_id=flat2.id, full_name="Meena Tenant", phone="9000000002", monthly_rent=Decimal("15000"),
                      security_deposit=Decimal("45000"), agreement_end_date=today + timedelta(days=20))
    gone = Tenant(flat_id=flat1.id, full_name="Old Tenant", move_out_date=today - timedelta(days=5),
                  agreement_end_date=today - timedelta(days=30))
    db.add_all([running, expiring, gone, Shop(society_id=society.id, shop_number="12", owner_name="Shop Owner",
                                               occupancy="rented", tenant_name="Cafe Tenant", tenant_phone="9111111111")])
    db.commit()
    reg = client.get(f"{A}/rental/{sid}", headers=h).json()
    assert reg["kind"] == "rental" and reg["title"] == "Rental Register"
    by_tenant = {r["tenant"]: r for r in reg["rows"]}
    assert set(by_tenant) == {"Ravi Tenant", "Meena Tenant", "Cafe Tenant"}                  # moved out: not listed
    r = by_tenant["Ravi Tenant"]
    assert r["rent"] == "20000.00" and r["deposit"] == "60000.00" and r["days_left"] == "265" and r["status"] == "Running"
    assert r["how"] == "Agent (Sai Realty)" and r["kind"] == "Flat" and r["unit"].endswith("101")
    assert by_tenant["Meena Tenant"]["status"] == "Expiring"
    assert by_tenant["Cafe Tenant"]["kind"] == "Shop" and by_tenant["Cafe Tenant"]["unit"] == "Shop 12"
    totals = {t["label"]: t["value"] for t in reg["totals"]}
    assert totals["Tenancies"] == "3" and totals["Rent per month Rs."] == "35000.00"
    assert totals["Deposits held Rs."] == "105000.00" and totals["Expiring in 60 days"] == "1"
    assert all(not k.startswith("_") for row in reg["rows"] for k in row)                       # no private keys leak
    # Filters and search
    assert [r["tenant"] for r in client.get(f"{A}/rental/{sid}", params={"status": "expiring"}, headers=h).json()["rows"]] \
        == ["Meena Tenant"]
    assert [r["tenant"] for r in client.get(f"{A}/rental/{sid}", params={"status": "past"}, headers=h).json()["rows"]] \
        == ["Old Tenant"]
    assert [r["tenant"] for r in client.get(f"{A}/rental/{sid}", params={"q": "cafe"}, headers=h).json()["rows"]] \
        == ["Cafe Tenant"]


def test_the_agreement_tracker_takes_precedence_for_dates_and_rent(client, db):
    society, flat1, *_ , manager, _r, _o = _rig(db, "mr2")
    h, sid = manager["headers"], str(society.id)
    today = local_today(zone(None))
    t = Tenant(flat_id=flat1.id, full_name="Tracked Tenant", monthly_rent=Decimal("1"))
    db.add(t)
    db.commit()
    db.add(AgreementTracker(society_id=society.id, flat_id=flat1.id, tenant_id=t.id, agreement_number="AGR-7",
                            start_date=today - timedelta(days=10), end_date=today + timedelta(days=350),
                            monthly_rent=Decimal("25000"), security_deposit=Decimal("75000"), channel="direct"))
    db.commit()
    row = client.get(f"{A}/rental/{sid}", headers=h).json()["rows"][0]
    assert row["agreement_no"] == "AGR-7" and row["rent"] == "25000.00" and row["how"] == "Direct"
    assert row["days_left"] == "350" and row["status"] == "Running"


# ── Receipts register ─────────────────────────────────────────────────────────

def test_receipts_register_shows_each_payment_what_it_settled_and_the_advance(client, db):
    society, flat1, flat2, manager, _res, bill1 = _issued_bills(client, db, "mr3")
    h, sid = manager["headers"], str(society.id)
    paid = client.post("/api/v1/billing/online-payments", headers=h, data={
        "flat_id": str(flat1.id), "amount": "10000.00", "payment_date": str(local_today(zone(None))), "payment_mode": "cash"})
    assert paid.status_code == 201, paid.text
    reg = client.get(f"{A}/receipts/{sid}", headers=h).json()
    assert reg["kind"] == "receipts" and reg["uses_period"] is True and len(reg["rows"]) == 1
    row = reg["rows"][0]
    assert row["amount"] == "10000.00" and row["mode"] == "Cash" and row["status"] == "Reconciled"
    assert bill1.invoice_number in row["applied_to"]                     # the bill it settled
    assert Decimal(row["advance"]) > 0                                   # ₹10,000 is more than the bill: the rest is advance
    totals = {t["label"]: t["value"] for t in reg["totals"]}
    assert totals["Received Rs."] == "10000.00" and totals["Receipts"] == "1"
    assert Decimal(totals["Held as advance Rs."]) == Decimal(row["advance"])
    assert Decimal(totals["Set off against bills Rs."]) + Decimal(totals["Held as advance Rs."]) == Decimal("10000.00")
    # Period, status and search
    assert client.get(f"{A}/receipts/{sid}", params={"date_from": str(local_today(zone(None)) + timedelta(days=1))},
                      headers=h).json()["rows"] == []
    assert client.get(f"{A}/receipts/{sid}", params={"status": "pending"}, headers=h).json()["rows"] == []
    assert len(client.get(f"{A}/receipts/{sid}", params={"q": row["receipt_no"]}, headers=h).json()["rows"]) == 1


# ── Staff attendance register ─────────────────────────────────────────────────

def _staff(db, society, name, code, department=StaffDepartment.SECURITY, status=StaffStatus.ACTIVE):
    s = Staff(society_id=society.id, employee_code=code, full_name=name, mobile=f"98{abs(hash(code)) % 10**8:08d}",
              department=department, status=status)
    db.add(s)
    db.commit()
    return s


def test_attendance_register_is_a_month_grid_with_totals(client, db):
    society = make_society(db, "Attendance Register Society")
    admin = make_user(db, "adm@attreg.com", role="Society Admin")
    admin["user"].society_id = society.id
    guard = _staff(db, society, "Guard One", "G-001")
    cleaner = _staff(db, society, "Cleaner One", "H-001", StaffDepartment.HOUSEKEEPING)
    left = _staff(db, society, "Left Long Ago", "G-099", status=StaffStatus.TERMINATED)
    db.commit()
    for day, status, hours in ((1, AttendanceStatus.PRESENT, 8.0), (2, AttendanceStatus.PRESENT, 9.0),
                               (3, AttendanceStatus.HALF_DAY, 4.0), (4, AttendanceStatus.ABSENT, None),
                               (5, AttendanceStatus.OVERTIME, 10.0)):
        db.add(StaffAttendance(society_id=society.id, staff_id=guard.id, attendance_date=date(2026, 9, day),
                               status=status, working_hours=hours, overtime_hours=2.0 if day == 5 else None))
    db.add(StaffLeave(society_id=society.id, staff_id=cleaner.id, leave_type=list(LeaveType)[0], from_date=date(2026, 9, 10),
                      to_date=date(2026, 9, 12), total_days=3, status=LeaveStatus.APPROVED))
    db.commit()
    h, sid = admin["headers"], str(society.id)
    reg = client.get(f"{A}/attendance/{sid}", params={"month": "2026-09"}, headers=h).json()
    assert reg["kind"] == "attendance" and reg["uses_month"] is True and reg["month"] == "2026-09"
    assert len([c for c in reg["columns"] if re.fullmatch(r"d\d+", c["key"])]) == 30            # September has 30 days
    names = [r["name"] for r in reg["rows"]]
    assert names == ["Cleaner One", "Guard One"] and "Left Long Ago" not in names
    g = next(r for r in reg["rows"] if r["name"] == "Guard One")
    assert [g[f"d{d}"] for d in range(1, 7)] == ["P", "P", "H", "A", "OT", ""]
    assert (g["present"], g["half"], g["absent"], g["leave"]) == ("3", "1", "1", "0")
    assert g["hours"] == "31.0" and g["overtime"] == "2.0"
    c = next(r for r in reg["rows"] if r["name"] == "Cleaner One")
    assert [c[f"d{d}"] for d in (9, 10, 11, 12, 13)] == ["", "L", "L", "L", ""] and c["leave"] == "3"
    totals = {t["label"]: t["value"] for t in reg["totals"]}
    assert totals == {"Staff": "2", "Present days": "3", "Absent days": "1", "Leave days": "3"}
    assert [s["label"] for s in reg["statuses"]] == ["All", "Housekeeping", "Security"]
    only = client.get(f"{A}/attendance/{sid}", params={"month": "2026-09", "status": "housekeeping"}, headers=h).json()
    assert [r["name"] for r in only["rows"]] == ["Cleaner One"]
    assert client.get(f"{A}/attendance/{sid}", params={"month": "2026-13"}, headers=h).status_code == 422


# ── Shared: printout, spreadsheet, access ─────────────────────────────────────

def test_every_register_prints_exports_and_stays_inside_its_society(client, db):
    society, flat1, flat2, manager, resident, other = _rig(db, "mr5")
    manager["user"].society_id = society.id                    # a manager belongs to one society
    db.commit()
    h, sid = manager["headers"], str(society.id)
    db.add(Tenant(flat_id=flat1.id, full_name="Ravi Tenant", monthly_rent=Decimal("20000")))
    db.commit()
    for kind in ("rental", "receipts", "attendance"):
        pdf = client.get(f"{A}/{kind}/{sid}", params={"format": "pdf"}, headers=h)
        assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF", kind
        csv = client.get(f"{A}/{kind}/{sid}", params={"format": "csv"}, headers=h)
        assert csv.status_code == 200 and csv.headers["content-type"].startswith("text/csv"), kind
    rows = client.get(f"{A}/rental/{sid}", params={"format": "csv"}, headers=h).text.splitlines()
    assert rows[0].startswith("Type,Unit,Owner,Tenant") and "Ravi Tenant" in rows[1]
    assert client.get(f"{A}/nonsense/{sid}", headers=h).status_code == 404
    assert client.get(f"{A}/rental/{sid}", headers=resident["headers"]).status_code == 403          # managers and above only
    rival = make_society(db, "Rival mr5")
    assert client.get(f"{A}/rental/{rival.id}", headers=h).status_code == 403
