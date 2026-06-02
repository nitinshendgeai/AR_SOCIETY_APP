# Testing Strategy — AR Society ERP

## Stack
- **pytest** with SQLite in-memory (no external DB needed)
- JSONB → JSON patched in conftest for SQLite compat
- Per-test transaction rollback — full isolation
- `TestClient` with dependency injection override

## Structure
```
backend/tests/
├── conftest.py              # fixtures, DB setup, helper factories
├── auth/
│   ├── test_auth.py         # register, login, JWT, health (12 tests)
│   └── test_auth_hardening.py # edge cases, security (24 tests)
├── rbac/
│   ├── test_rbac.py         # role enforcement (10 tests)
│   └── test_rbac_hardening.py # privilege escalation, boundaries (15 tests)
├── master/
│   ├── test_master.py       # society, wing, flat, vehicle (10 tests)
│   └── test_society_onboarding.py # initialization workflow (6 tests)
├── staff/
│   ├── test_attendance.py   # check-in/out, duplicates (5 tests)
│   ├── test_leave.py        # leave workflow, overlaps (7 tests)
│   ├── test_handover.py     # handover FSM (6 tests)
│   └── test_tasks.py        # task FSM, RBAC (7 tests)
├── complaint/
│   └── test_complaint.py    # FSM lifecycle, RBAC, comments (16 tests)
├── billing/
│   └── test_billing.py      # periods, charge config, bills, payment (11 tests)
├── visitor/
│   └── test_visitor.py      # gate CRUD, visitor workflow (12 tests)
├── amenity/
│   └── test_amenity.py      # amenity CRUD, booking workflow (7 tests)
├── parking/
│   └── test_parking.py      # zone, slot, allocation (7 tests)
├── inventory/
│   └── test_inventory.py    # item CRUD, stock-in, issue (7 tests)
├── notice/
│   └── test_notice.py       # notice CRUD, publish, acknowledge (7 tests)
└── vendor/
    └── test_vendor.py       # vendor CRUD, service requests (7 tests)
```
**Total: 171 tests, 0 failures**

## Running Tests
```bash
cd backend
make test          # verbose output
make test-cov      # quiet
# Or directly:
DATABASE_URL="sqlite:///./test_ar_society.db" SECRET_KEY="test-secret" \
python -m pytest tests/ -q
```

## Key Fixtures (conftest.py)
```python
db      # SQLite session with rollback per test
client  # TestClient with DB injected

make_user(db, email, password, role)    # → {user, token, headers}
make_society(db, name)                  # → Society
make_wing(db, society_id, name)         # → Wing
make_flat(db, wing_id, flat_number)     # → Flat
```

## Seed Data
```bash
make seed   # requires live DATABASE_URL in .env
```
Creates: 1 society, 3 wings, 15 flats, 10 users, 5 residents, 3 vehicles, 2 staff, 5-day attendance.

Test credentials (password: `Test@12345`):
```
admin@arsociety.com     Admin
committee@arsociety.com Committee
security@arsociety.com  Security
staff1@arsociety.com    Staff
res1@arsociety.com      Resident
```

## Test Coverage Goals

| Category | What to test |
|----------|-------------|
| Happy path | Every endpoint returns expected status |
| Validation | 422 on bad input, 409 on conflicts |
| RBAC | 403 when wrong role, 401 when no token |
| FSM | Invalid transitions return 409 |
| Duplicate prevention | 409 on second create |
| Edge cases | Inactive users, tampered tokens, SQL injection |

## Adding New Tests

1. Create `tests/{module}/test_{name}.py`
2. Import fixtures from `conftest.py`
3. Use `make_user(db, email, role=)` for authenticated requests
4. Keep tests independent (each creates its own data)
5. Run `make test` — must be 0 failures before committing
