"""
Shared vehicle-number normalization.

Previously this exact transform was copy-pasted into VehicleCreate
(app/api/routes/vehicle.py) and VisitorParkingCreate (parking module), and
never applied at all to ViolationCreate/AccessLogCreate (also parking) —
so the same physical vehicle could be stored as "MH01AB1234" in one place
and "MH01-AB 1234" in another, breaking any equality-based lookup between
the Vehicle master and parking violation/access-log records. Import this
one function everywhere a vehicle_number is accepted instead of
re-declaring the transform.
"""


def normalize_vehicle_number(value: str) -> str:
    return value.upper().replace(" ", "").replace("-", "")
