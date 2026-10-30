"""A flat's occupancy follows who has moved in: tenant occupied when an active tenant has a move-in date, owner
occupied when an active resident has one, otherwise vacant. A possession date (the handover) does not by itself make a
flat occupied. And the one-time correction of existing flats (migration 0e4f5a6b7c8d)."""
import importlib.util
import pathlib
from datetime import date, timedelta

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations

from app.models.flat import Flat, OccupancyStatus
from app.models.resident import Resident
from app.models.tenant import Tenant
from tests.conftest import make_flat, make_society, make_user, make_wing

R = "/api/v1/residents"
O = "/api/v1/occupancy"


@pytest.fixture
def rig(db):
    society = make_society(db, "Rule Society")
    admin = make_user(db, "rule@admin.com", role="Society Admin")
    admin["user"].society_id = society.id
    wing = make_wing(db, society.id, "A")
    flats = {n: make_flat(db, wing.id, n) for n in ("101", "102", "103", "104", "105")}
    db.commit()
    return {"society": society, "h": admin["headers"], "flats": flats}


def _status(db, flat):
    db.expire_all()
    return db.get(Flat, flat.id).occupancy_status


def _resident(client, rig, flat, name="Owner", **extra):
    r = client.post(f"{R}/", headers=rig["h"], json={"flat_id": str(rig["flats"][flat].id), "full_name": name,
                                                      "resident_type": "owner", **extra})
    assert r.status_code == 201, r.text
    return r.json()


def test_a_resident_without_a_move_in_date_does_not_make_the_flat_occupied(client, db, rig):
    flat = rig["flats"]["101"]
    _resident(client, rig, "101")
    assert _status(db, flat) == OccupancyStatus.VACANT
    flat.possession_date = date.today() - timedelta(days=400)        # handed over, but nobody has moved in
    db.commit()
    assert _status(db, flat) == OccupancyStatus.VACANT


def test_the_move_in_date_makes_the_flat_owner_occupied_and_the_last_move_out_vacant(client, db, rig):
    flat = rig["flats"]["102"]
    owner = _resident(client, rig, "102", move_in_date=str(date.today()))
    assert _status(db, flat) == OccupancyStatus.OWNER_OCCUPIED
    family = _resident(client, rig, "102", name="Family", move_in_date=str(date.today()))
    out = lambda r: client.post(f"{O}/resident/move-out", headers=rig["h"], json={
        "flat_id": str(flat.id), "resident_id": r["id"], "move_out_date": str(date.today())})
    assert out(owner).status_code == 200
    assert _status(db, flat) == OccupancyStatus.OWNER_OCCUPIED       # the family member is still in
    assert out(family).status_code == 200
    assert _status(db, flat) == OccupancyStatus.VACANT


def test_a_resident_with_no_move_in_date_does_not_keep_the_flat_occupied(client, db, rig):
    flat = rig["flats"]["103"]
    owner = _resident(client, rig, "103", move_in_date=str(date.today()))
    _resident(client, rig, "103", name="Listed, never moved in")      # no move-in date
    r = client.post(f"{O}/resident/move-out", headers=rig["h"], json={
        "flat_id": str(flat.id), "resident_id": owner["id"], "move_out_date": str(date.today())})
    assert r.status_code == 200
    assert _status(db, flat) == OccupancyStatus.VACANT


def test_a_tenant_with_a_move_in_date_makes_it_tenant_occupied_and_moving_out_frees_it(client, db, rig):
    flat = rig["flats"]["104"]
    t = client.post("/api/v1/tenants/", headers=rig["h"], json={
        "flat_id": str(flat.id), "full_name": "Meena", "move_in_date": str(date.today())}).json()
    assert _status(db, flat) == OccupancyStatus.TENANT_OCCUPIED
    r = client.post(f"{O}/tenant/move-out", headers=rig["h"], json={
        "flat_id": str(flat.id), "tenant_id": t["id"], "move_out_date": str(date.today())})
    assert r.status_code == 200
    assert _status(db, flat) == OccupancyStatus.VACANT


# ── the one-time correction ──────────────────────────────────────────────────

def _run_migration(db):
    path = pathlib.Path(__file__).resolve().parents[2] / "alembic/versions/0e4f5a6b7c8d_sync_flat_occupancy.py"
    spec = importlib.util.spec_from_file_location("sync_flat_occupancy", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    db.commit()
    conn = db.connection()
    with Operations.context(MigrationContext.configure(conn)):
        module.upgrade()
    db.expire_all()


def test_the_correction_sets_flats_with_occupants_from_their_move_in_dates_and_leaves_the_rest(db, rig):
    f = rig["flats"]
    today = date.today()

    def resident(flat, moved_in, **kw):
        db.add(Resident(flat_id=f[flat].id, full_name=f"R{flat}", move_in_date=today if moved_in else None, **kw))

    # 101: a resident has moved in, but the flat says vacant            -> owner occupied
    resident("101", True)
    f["101"].occupancy_status = OccupancyStatus.VACANT
    # 102: a tenant has moved in, the flat says owner occupied          -> tenant occupied
    db.add(Tenant(flat_id=f["102"].id, full_name="T102", move_in_date=today))
    f["102"].occupancy_status = OccupancyStatus.OWNER_OCCUPIED
    # 103: a resident with no move-in date, the flat says occupied      -> vacant
    resident("103", False)
    f["103"].occupancy_status = OccupancyStatus.OWNER_OCCUPIED
    # 104: a tenant who moved out and a resident who is in             -> owner occupied
    db.add(Tenant(flat_id=f["104"].id, full_name="Old", move_in_date=today - timedelta(days=90),
                  move_out_date=today - timedelta(days=1), is_active=False))
    resident("104", True)
    f["104"].occupancy_status = OccupancyStatus.VACANT
    # 105: nobody on record at all, marked let out                      -> left as it is
    f["105"].occupancy_status = OccupancyStatus.TENANT_OCCUPIED
    db.commit()

    _run_migration(db)
    got = {n: db.get(Flat, f[n].id).occupancy_status for n in f}
    assert got == {"101": OccupancyStatus.OWNER_OCCUPIED, "102": OccupancyStatus.TENANT_OCCUPIED,
                   "103": OccupancyStatus.VACANT, "104": OccupancyStatus.OWNER_OCCUPIED,
                   "105": OccupancyStatus.TENANT_OCCUPIED}


def _run_reset(db):
    path = pathlib.Path(__file__).resolve().parents[2] / "alembic/versions/0f5a6b7c8d9e_reset_unoccupied_flats.py"
    spec = importlib.util.spec_from_file_location("reset_unoccupied_flats", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    db.commit()
    with Operations.context(MigrationContext.configure(db.connection())):
        module.upgrade()
    db.expire_all()


def test_flats_with_nobody_on_record_are_set_to_vacant_and_the_rest_are_left(db, rig):
    f = rig["flats"]
    today = date.today()
    f["101"].occupancy_status = OccupancyStatus.OWNER_OCCUPIED        # nobody on record      -> vacant
    f["102"].occupancy_status = OccupancyStatus.TENANT_OCCUPIED       # let out, no tenant    -> vacant
    f["103"].occupancy_status = OccupancyStatus.OWNER_OCCUPIED        # a resident has moved in -> stays
    db.add(Resident(flat_id=f["103"].id, full_name="R103", move_in_date=today))
    f["104"].occupancy_status = OccupancyStatus.VACANT                # already vacant       -> stays
    f["105"].occupancy_status = OccupancyStatus.TENANT_OCCUPIED       # a tenant has moved in -> stays
    db.add(Tenant(flat_id=f["105"].id, full_name="T105", move_in_date=today))
    db.commit()

    _run_reset(db)
    got = {n: db.get(Flat, f[n].id).occupancy_status for n in f}
    assert got == {"101": OccupancyStatus.VACANT, "102": OccupancyStatus.VACANT, "103": OccupancyStatus.OWNER_OCCUPIED,
                   "104": OccupancyStatus.VACANT, "105": OccupancyStatus.TENANT_OCCUPIED}
