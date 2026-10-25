"""The SQLite test database must hand back exactly the UUID it was given, however the hex digits fall."""
import uuid

import pytest

from app.models.society import Society

# Digits only (stored as an integer under numeric affinity) and digits with one "e" (read as a float).
_AWKWARD = [
    uuid.UUID("12345678-1234-1234-1234-123456789012"),
    uuid.UUID("12345678-1234-1234-1234-12345678e012"),
]


@pytest.mark.parametrize("sid", _AWKWARD, ids=["digits-only", "digits-and-e"])
def test_ids_that_look_like_numbers_round_trip(db, sid):
    db.add(Society(id=sid, name=f"Awkward {sid}", society_code=f"AW{sid.hex[-6:]}"))
    db.flush()
    db.expire_all()
    assert db.query(Society).filter(Society.id == sid).one().id == sid
