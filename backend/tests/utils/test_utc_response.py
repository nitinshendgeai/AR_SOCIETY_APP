"""Server-stamped times go out marked as UTC; times the user typed do not."""
from datetime import datetime, timezone

from app.utils.utc_response import _mark
from tests.conftest import make_user, make_society


def test_stamp_keys_get_a_z():
    out = _mark({"created_at": "2026-10-09T04:01:02", "check_in_time": "2026-10-09T04:01:02.123456",
                 "nested": [{"paid_at": "2026-10-09T04:01:02"}]})
    assert out["created_at"] == "2026-10-09T04:01:02Z"
    assert out["check_in_time"] == "2026-10-09T04:01:02.123456Z"
    assert out["nested"][0]["paid_at"] == "2026-10-09T04:01:02Z"


def test_user_entered_and_other_values_are_left_alone():
    src = {
        "due_date": "2026-10-09T04:01:02",            # typed by a person
        "expected_arrival": "2026-10-09T04:01:02",
        "open_time": "09:00:00",                        # time of day
        "name": "2026-10-09T04:01:02",                  # not a stamp key
        "already_at": "2026-10-09T04:01:02Z",           # has a zone
        "offset_at": "2026-10-09T09:31:02+05:30",
        "empty_at": None,
    }
    assert _mark(src) == src


def test_visitor_check_in_time_is_sent_as_utc(client, db):
    admin = make_user(db, "adm.utc@vis.com", role="Society Admin")
    security = make_user(db, "sec.utc@vis.com", role="Security Staff")
    society = make_society(db, "Utc Society")
    payload = {"name": "Time Check", "mobile": "9876543210", "visitor_type": "guest",
               "purpose": "Meeting", "society_id": str(society.id)}
    vid = client.post("/api/v1/visitors/", json=payload, headers=security["headers"]).json()["id"]
    client.post(f"/api/v1/visitors/{vid}/approve", json={"notes": ""}, headers=admin["headers"])
    r = client.post(f"/api/v1/visitors/{vid}/checkin", json={"notes": ""}, headers=security["headers"])
    assert r.status_code == 200, r.text
    stamp = r.json()["checked_in_at"]
    assert stamp.endswith("Z"), stamp
    parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    assert abs((datetime.now(timezone.utc) - parsed).total_seconds()) < 120
    assert r.json()["created_at"].endswith("Z")
