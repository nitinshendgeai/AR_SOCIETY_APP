# Testing Strategy

## Stack
- pytest + httpx TestClient
- SQLite in-memory (JSONB → JSON patched for SQLite compat)
- Per-test DB transaction rollback — full isolation

## Test Structure
```
backend/tests/
├── conftest.py          # fixtures, helpers, JSONB patch
├── auth/
│   └── test_auth.py    # register, login, JWT, health
├── rbac/
│   └── test_rbac.py    # role enforcement, multi-role
├── master/
│   └── test_master.py  # society, wing, flat, vehicle
└── staff/
    ├── test_attendance.py  # checkin, checkout, duplicates
    └── test_leave.py       # leave workflow, overlaps
```

## Running Tests
```bash
cd backend
make test          # verbose
make test-cov      # quiet with stats

# Or directly:
DATABASE_URL="sqlite:///./test_ar_society.db" SECRET_KEY="test-secret" \
python -m pytest tests/ -q
```

## Seed Data
```bash
# Requires live DATABASE_URL in .env or env var
make seed

# Test credentials (password: Test@12345)
admin@arsociety.com     → Admin
committee@arsociety.com → Committee
security@arsociety.com  → Security
staff1@arsociety.com    → Staff
res1@arsociety.com      → Resident
```

## Coverage Goals
| Area | Tests |
|------|-------|
| Auth | register, login, JWT, invalid token, health |
| RBAC | admin-only, committee, resident, unauthenticated, multi-role |
| Master | society CRUD, wing, flat, vehicle (duplicate prevention) |
| Staff | check-in/out (duplicates, order), leave (overlap, approval) |
