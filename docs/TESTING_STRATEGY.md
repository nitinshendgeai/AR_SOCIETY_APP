# Testing Strategy — AR Society ERP

## Stack
- **pytest** with a throw-away SQLite file (no external DB needed for the test suite)
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
**Total: 1,300 backend tests (1,223 before Phase 1) and 232 Flutter tests, 0 failures** — the tree above is the original layout; see `backend/tests/` for the current one, including `security/` (Phase 1) and `ci/` (Phase 2).

## Running Tests
```bash
cd backend
make test          # verbose output
make test-cov      # quiet
# Or directly:
DATABASE_URL="sqlite:///./test_ar_society.db" SECRET_KEY="test-secret" \
python -m pytest tests/ -q
```

## Continuous integration

Three workflows in `.github/workflows/` run on every pull request and every push to `main`
(details and findings: `docs/audit/PHASE_2_CI_AUDIT.md`):

| Workflow / job | What it checks | Run the same thing locally |
|---|---|---|
| **Backend CI → Backend tests** (Python 3.12) | hash-enforced install, import check, the security regression tests, then the full suite, then a guard against a false-green run | `cd backend && pip install --require-hashes -r requirements-dev.txt && make lint test-security && python -m pytest -q -o log_cli=false` |
| **Backend CI → Migrations** (PostgreSQL 16) | one unbroken migration chain; empty database → head; last migration reversible; earlier revision → head; no missing/extra tables or columns; `/health/ready` 200 at head and 503 one revision behind | `make check-migrations` (no database) or `make check-migrations-db ADMIN_DB_URL=postgresql://user:password@localhost:5432/postgres` (a **disposable** server) |
| **Flutter CI → analyze and tests** | `flutter pub get --enforce-lockfile`, `flutter analyze --no-fatal-infos` (errors and warnings fail), `flutter test` | `cd mobile && cp .env.example .env && flutter pub get --enforce-lockfile && flutter analyze --no-fatal-infos && flutter test` |
| **Flutter CI → web release build** | the production web build compiles | `cd mobile && flutter build web --release --dart-define=API_BASE_URL=https://ci.invalid/api/v1 --no-tree-shake-icons` |
| **Secret Scan** (gitleaks) | no credential-shaped value in the working tree | see `docs/audit/PHASE_2_CI_AUDIT.md` (currently reports two Firebase web-key findings) |
| **Build Android APK** (main only) | the release APK builds | needs the Android SDK |

Notes for contributors:
- The backend dependency locks are `backend/requirements.txt` (production, installed by Railway) and
  `backend/requirements-dev.txt` (production lock + test tools). After changing `requirements.in` or
  `requirements-dev.in`, regenerate **both** with `pip-compile --generate-hashes` and keep them in step
  (`pip-compile --generate-hashes -c requirements.txt --no-header -o requirements-dev.txt requirements-dev.in`).
- Run `alembic` through its console script (as the docs do), not `python -m alembic`: the migrations folder is
  itself called `alembic` and shadows the library when you run from `backend/`.
- Dart formatting is **not** enforced (278 of 300 files differ from `dart format`); do not reformat unrelated files.

## Key Fixtures (conftest.py)
```python
db      # SQLite session with rollback per test
client  # TestClient with DB injected

make_user(db, email, password, role)    # → {user, token, headers}
make_society(db, name)                  # → Society
make_wing(db, society_id, name)         # → Wing
make_flat(db, wing_id, flat_number)     # → Flat
place_in(db, login, society)            # make a login a member of a society (a Resident/Tenant needs one)
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
