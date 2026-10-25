"""Setting the possession date of many flats from a sheet: added where there is none, replaced where there is one."""
from datetime import date

from tests.conftest import make_flat, make_society, make_user, make_wing

URL = "/api/v1/flats/possession-import"


def _rig(db, tag):
    society = make_society(db, f"Possession Society {tag}")
    who = make_user(db, f"adm@poss{tag}.test", role="Society Admin")
    who["user"].society_id = society.id
    db.commit()
    return society, who["headers"]


def _post(client, h, rows, dry_run=False):
    return client.post(URL, headers=h, json={"rows": rows, "dry_run": dry_run})


def test_dates_are_added_and_replaced(client, db):
    society, h = _rig(db, "p1")
    wing = make_wing(db, society.id, "Wing A")
    a101, a102 = make_flat(db, wing.id, "101"), make_flat(db, wing.id, "102")
    a102.possession_date = date(2018, 1, 1)
    db.commit()
    r = _post(client, h, [
        {"line": 2, "wing": "Wing A", "flat_number": "101", "possession_date": "2019-04-01"},
        {"line": 3, "wing": "wing a", "flat_number": "102", "possession_date": "2020-06-15"},
    ])
    assert r.status_code == 200, r.text
    assert [x["status"] for x in r.json()] == ["updated", "updated"]
    assert r.json()[1]["previous"] == "2018-01-01"
    db.refresh(a101); db.refresh(a102)
    assert a101.possession_date == date(2019, 4, 1) and a102.possession_date == date(2020, 6, 15)


def test_dry_run_writes_nothing_and_same_date_is_unchanged(client, db):
    society, h = _rig(db, "p2")
    wing = make_wing(db, society.id, "Wing A")
    flat = make_flat(db, wing.id, "101")
    flat.possession_date = date(2019, 4, 1)
    db.commit()
    r = _post(client, h, [{"flat_number": "101", "possession_date": "2019-04-01"}])
    assert r.json()[0]["status"] == "unchanged"
    r = _post(client, h, [{"flat_number": "101", "possession_date": "2021-01-01"}], dry_run=True)
    assert r.json()[0]["status"] == "updated"
    db.refresh(flat)
    assert flat.possession_date == date(2019, 4, 1)


def test_bad_rows_are_reported_and_the_rest_go_in(client, db):
    society, h = _rig(db, "p3")
    from app.models.wing import Wing
    wing_a = make_wing(db, society.id, "Wing A")
    wing_b = Wing(society_id=society.id, name="Wing B", code="B")
    db.add(wing_b)
    db.commit()
    flat = make_flat(db, wing_a.id, "101")
    make_flat(db, wing_b.id, "101")
    make_flat(db, wing_b.id, "202")
    db.commit()
    r = _post(client, h, [
        {"line": 2, "wing": "Wing A", "flat_number": "101", "possession_date": "2019-04-01"},
        {"line": 3, "flat_number": "101", "possession_date": "2019-04-01"},                 # in two wings
        {"line": 4, "wing": "Wing A", "flat_number": "999", "possession_date": "2019-04-01"},
        {"line": 5, "wing": "Wing A", "flat_number": "101", "possession_date": "2019-05-01"},  # again
        {"line": 6, "flat_number": "202", "possession_date": ""},
        {"line": 7, "flat_number": "202", "possession_date": "1900-01-01"},
        {"line": 8, "flat_number": "202", "possession_date": "2019-02-30"},
        {"line": 9, "flat_number": "202", "possession_date": "2022-03-03"},                  # no wing needed
    ]).json()
    assert [x["status"] for x in r] == ["updated", "error", "error", "error", "error", "error", "error", "updated"]
    assert "more than one wing" in r[1]["message"] and "No flat 999" in r[2]["message"]
    db.refresh(flat)
    assert flat.possession_date == date(2019, 4, 1)


def test_other_societies_flats_are_out_of_reach_and_residents_cannot_import(client, db):
    society, h = _rig(db, "p4")
    other = make_society(db, "Possession Society other")
    theirs = make_flat(db, make_wing(db, other.id, "Wing A").id, "101")
    r = _post(client, h, [{"flat_number": "101", "possession_date": "2019-04-01"}]).json()
    assert r[0]["status"] == "error"
    db.refresh(theirs)
    assert theirs.possession_date is None
    resident = make_user(db, "res@possp4.test", role="Resident")
    resident["user"].society_id = society.id
    db.commit()
    assert _post(client, resident["headers"], []).status_code == 403
