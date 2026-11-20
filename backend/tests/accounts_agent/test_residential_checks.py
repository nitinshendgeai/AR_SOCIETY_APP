"""Vendor bank-account changes, ownership handover, parking reconciliation and unadjusted advances."""
from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from app.models.audit_log import AuditAction, AuditLog
from app.models.resident import Resident, ResidentType
from app.models.vehicle import Vehicle, VehicleType
from app.modules.accounts_agent.legal.models import VendorBankRecord
from app.modules.billing.models.billing import OnlinePaymentSubmission, PaymentMode, ReconciliationStatus
from app.modules.parking.models.parking import AllocationStatus, ParkingAllocation, ParkingSlot, ParkingZone, SlotType
from tests.accounts_agent.legal_helpers import D, BillStatus, ChargeBasis, ChargeType, LRig


@pytest.fixture
def rig(db):
    return LRig(db, "res")


def one(rig, code):
    rows = rig.findings(code)
    assert len(rows) == 1, f"{code}: {[(f.rule_code, f.title) for f in rig.findings()]}"
    return rows[0]


def _payment(rig, flat, amount, days_ago, n=[0]):
    n[0] += 1
    p = OnlinePaymentSubmission(society_id=rig.sid, flat_id=flat.id, receipt_number=f"OP-{rig.tag}-{n[0]}",
                                amount=D(str(amount)), payment_date=rig.today - timedelta(days=days_ago),
                                payment_mode=PaymentMode.UPI, purpose=ChargeType.MAINTENANCE,
                                status=ReconciliationStatus.RECONCILED)
    rig.db.add(p)
    rig.db.commit()
    return p


# ── Vendor bank-account changes ──────────────────────────────────────────────────────────────────────────────────

def test_bank_change_detected_between_scans_and_payment_after_it(rig, db):
    ven = rig.vendor("LiftCo")
    ven.bank_name, ven.bank_account, ven.bank_ifsc = "HDFC Bank", "50100012345678", "HDFC0000123"
    db.commit()
    rig.scan()                                                         # baseline only: nothing to flag
    assert rig.findings("A-VEN-BANK-01") == []
    ven.bank_account, ven.bank_ifsc = "9988776655443322", "ICIC0000999"       # e.g. changed by an import
    db.commit()
    rig.scan()
    f = one(rig, "A-VEN-BANK-01")
    assert f.severity == "MEDIUM" and f.vendor_id == ven.id
    assert f.evidence["previous"]["account"] == "XXXX5678" and f.evidence["new"]["account"] == "XXXX3322"
    assert "50100012345678" not in str(f.evidence) and "9988776655443322" not in str(f.explanation)   # masked only
    rig.payment(0, "lift_maintenance", 40000, vendor=ven, reference="LIFT-NOV")
    rig.scan()
    f = one(rig, "A-VEN-BANK-01")                                      # same change, now with money paid after it
    assert f.severity == "HIGH" and f.evidence["payments_since"][0]["amount"] == "40000.00"
    rig.scan()                                                         # stays open; never duplicated
    assert len(rig.findings("A-VEN-BANK-01")) == 1
    assert db.query(VendorBankRecord).filter(VendorBankRecord.vendor_id == ven.id).count() == 2


def test_bank_change_reconstructed_from_audit_trail_on_first_scan(rig, db):
    ven = rig.vendor("SecureCo")
    ven.bank_name, ven.bank_account, ven.bank_ifsc = "SBI", "11112222333344", "SBIN0001111"
    db.add(AuditLog(user_id=rig.admin["user"].id, action=AuditAction.UPDATE, module="vendor", entity_type="Vendor",
                    entity_id=str(ven.id), old_values={"bank_account": "55556666777788", "bank_ifsc": "SBIN0001111"},
                    new_values={"bank_account": "11112222333344", "bank_ifsc": "SBIN0001111"}))
    db.commit()
    rig.scan()
    f = one(rig, "A-VEN-BANK-01")
    assert f.evidence["source"] == "audit_log" and f.evidence["changed_by_user_id"] == str(rig.admin["user"].id)
    assert f.evidence["previous"]["account"] == "XXXX7788"


def test_renaming_the_bank_is_not_a_change(rig, db):
    ven = rig.vendor("GardenCo")
    ven.bank_name, ven.bank_account, ven.bank_ifsc = "HDFC", "50100012345678", "hdfc0000123"
    db.commit()
    rig.scan()
    ven.bank_name, ven.bank_account, ven.bank_ifsc = "HDFC Bank Ltd", "5010 0012 345678", "HDFC0000123"
    db.commit()
    rig.scan()
    assert rig.findings("A-VEN-BANK-01") == []


def test_vendor_without_change_and_other_society_are_quiet(rig, db):
    other = LRig(db, "res2")
    ven = other.vendor("OtherCo")
    ven.bank_account, ven.bank_ifsc = "123456789012", "UTIB0000001"
    db.commit()
    rig.scan(); other.scan()
    ven.bank_account = "999999999999"
    db.commit()
    rig.scan()                                                         # society A's scan never touches B's vendors
    assert rig.findings("A-VEN-BANK-01") == []
    assert db.query(VendorBankRecord).filter(VendorBankRecord.society_id == rig.sid).count() == 0


# ── Ownership handover ───────────────────────────────────────────────────────────────────────────────────────────

def _transfer(rig, flat, days_ago=40):
    when = rig.today - timedelta(days=days_ago)
    rig.db.add_all([
        Resident(flat_id=flat.id, full_name="Old Owner", resident_type=ResidentType.OWNER,
                 move_in_date=when - timedelta(days=2000), move_out_date=when),
        Resident(flat_id=flat.id, full_name="New Owner", resident_type=ResidentType.OWNER, move_in_date=when),
    ])
    rig.db.commit()
    return when


def test_handover_dues_and_advance_of_previous_owner(rig, db):
    fl = rig.flat_rows[0]
    when = _transfer(rig, fl)
    old = rig.cycle(when - timedelta(days=60), when - timedelta(days=31), due=when - timedelta(days=20), name="Before")
    rig.bill(fl, old, [(ChargeType.MAINTENANCE, "Service Charges", 3000, 3000)])
    _payment(rig, fl, 1500, days_ago=60)                       # paid before the transfer, never set off
    rig.scan()
    dues = one(rig, "A-HND-01")
    assert dues.finding_class == "MISSING_DOCUMENTATION" and dues.flat_id == fl.id and dues.evidence["outstanding"] == "3000.00"
    adv = one(rig, "A-HND-02")
    assert adv.evidence["advance"] == "1500.00"
    assert one(rig, "A-HND-03").finding_class == "ADVISORY_OBSERVATION"          # no transfer premium recorded
    v = rig.journal(30, "bank", "transfer_premium", 25000, narration="Transfer premium flat 101")
    v.entries[1].flat_id = fl.id
    db.commit()
    rig.scan()
    assert rig.findings("A-HND-03") == []


def test_new_owner_with_previous_owner_still_on_record(rig, db):
    fl = rig.flat_rows[1]
    when = rig.today - timedelta(days=20)
    db.add_all([Resident(flat_id=fl.id, full_name="First", resident_type=ResidentType.OWNER, move_in_date=when - timedelta(days=900)),
                Resident(flat_id=fl.id, full_name="Second", resident_type=ResidentType.OWNER, move_in_date=when)])
    db.commit()
    rig.scan()
    assert one(rig, "A-HND-04").flat_id == fl.id


def test_no_transfer_no_handover_findings(rig, db):
    db.add(Resident(flat_id=rig.flat_rows[2].id, full_name="Only Owner", resident_type=ResidentType.OWNER,
                    move_in_date=rig.today - timedelta(days=500)))
    db.add(Resident(flat_id=rig.flat_rows[2].id, full_name="Spouse", resident_type=ResidentType.FAMILY,
                    move_in_date=rig.today - timedelta(days=10)))
    db.commit()
    rig.scan()
    assert not [f for f in rig.findings() if f.rule_code.startswith("A-HND")]


# ── Parking ──────────────────────────────────────────────────────────────────────────────────────────────────────

def _parking(rig):
    zone = ParkingZone(society_id=rig.sid, name="Basement")
    rig.db.add(zone)
    rig.db.flush()
    slots = [ParkingSlot(society_id=rig.sid, zone_id=zone.id, slot_number=f"B-{i}") for i in range(1, 4)]
    rig.db.add_all(slots)
    rig.db.commit()
    return slots


def _allot(rig, slot, flat, start_days_ago=200, status=AllocationStatus.ACTIVE, **kw):
    a = ParkingAllocation(society_id=rig.sid, slot_id=slot.id, flat_id=flat.id, allocation_type=SlotType.RESIDENT,
                          status=status, start_date=rig.today - timedelta(days=start_days_ago), **kw)
    rig.db.add(a)
    rig.db.commit()
    return a


def test_parking_billed_against_allotments(rig, db):
    s1, s2, _ = _parking(rig)
    rig.config("Parking", ChargeType.PARKING, ChargeBasis.PARKING, 500)
    a, b, c = rig.flat_rows[:3]
    _allot(rig, s1, a)                     # held and billed: fine
    _allot(rig, s2, b)                     # held, not billed
    cy = rig.cycle(rig.today - timedelta(days=30), rig.today - timedelta(days=1))
    rig.bill(a, cy, [(ChargeType.PARKING, "Parking", 500, 500)])
    rig.bill(b, cy, [(ChargeType.MAINTENANCE, "Service Charges", 2000, 2000)])
    rig.bill(c, cy, [(ChargeType.PARKING, "Parking", 500, 500)])          # billed, no slot
    rig.scan()
    assert one(rig, "A-PRK-01").flat_id == b.id
    assert one(rig, "A-PRK-02").flat_id == c.id


def test_two_wheeler_rate_and_released_slot_are_not_flagged(rig, db):
    s1, s2, _ = _parking(rig)
    head = rig.config("Parking", ChargeType.PARKING, ChargeBasis.PARKING, 500)
    head.two_wheeler_rate = D("100")
    db.commit()
    a, b = rig.flat_rows[:2]
    db.add(Vehicle(society_id=rig.sid, flat_id=a.id, vehicle_number="MH01AB1234", vehicle_type=VehicleType.SCOOTER))
    _allot(rig, s1, b, status=AllocationStatus.RELEASED, end_date=rig.today - timedelta(days=90))   # released long ago
    cy = rig.cycle(rig.today - timedelta(days=30), rig.today - timedelta(days=1))
    rig.bill(a, cy, [(ChargeType.PARKING, "Parking (two-wheeler)", 100, 100)])
    rig.bill(b, cy, [(ChargeType.MAINTENANCE, "Service Charges", 2000, 2000)])
    rig.scan()
    assert rig.findings("A-PRK-01") == [] and rig.findings("A-PRK-02") == []


def test_double_allotment_and_no_parking_head(rig, db):
    s1, _, _ = _parking(rig)
    _allot(rig, s1, rig.flat_rows[0], start_days_ago=100)
    _allot(rig, s1, rig.flat_rows[1], start_days_ago=20)
    rig.scan()
    assert one(rig, "A-PRK-03").severity == "HIGH"
    assert one(rig, "A-PRK-05").finding_class == "ADVISORY_OBSERVATION"


# ── Unadjusted advances ──────────────────────────────────────────────────────────────────────────────────────────

def test_advance_left_unused_while_bills_are_unpaid(rig, db):
    fl = rig.flat_rows[3]
    cy = rig.cycle(rig.today - timedelta(days=40), rig.today - timedelta(days=10))
    b = rig.bill(fl, cy, [(ChargeType.MAINTENANCE, "Service Charges", 2500, 2500)])
    _payment(rig, fl, 1000, days_ago=5)
    rig.scan()
    f = one(rig, "A-ADV-01")
    assert f.evidence["can_set_off"] == "1000.00" and f.flat_id == fl.id
    db.refresh(b)
    assert b.outstanding == D("2500.00")                        # the agent never sets anything off itself


def test_old_advance_with_nothing_due(rig, db):
    _payment(rig, rig.flat_rows[4], 700, days_ago=400)
    _payment(rig, rig.flat_rows[0], 300, days_ago=10)            # recent advance, nothing due: normal, not flagged
    rig.scan()
    f = one(rig, "A-ADV-02")
    assert f.flat_id == rig.flat_rows[4].id and rig.findings("A-ADV-01") == []


def test_new_checks_run_inside_the_scan_without_failures(rig):
    out = rig.scan()
    assert out["failed_checks"] == []
