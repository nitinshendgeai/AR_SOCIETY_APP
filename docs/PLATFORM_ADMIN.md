# Platform Admin — AR Society ERP

## What Is Platform Admin

Platform Admin is the AR Society App internal operations role.
It is NOT a society-level role — it is cross-society.

Platform Admin users:
- Are identified by `User.is_superadmin = True`
- Do not belong to any single society
- Access all societies from a single dashboard
- Use the same auth system (JWT) but get a different permission check

## How Platform Admin Is Identified

```python
# In dependencies.py
def require_platform_admin():
    def _checker(current_user: User = Depends(get_current_user)):
        if not current_user.is_superadmin:
            raise HTTPException(403, "Platform Admin access required")
        return current_user
    return _checker
```

## Platform Admin Capabilities

| Action | Endpoint |
|--------|----------|
| List all societies | `GET /api/v1/platform-admin/societies` |
| Get society detail | `GET /api/v1/platform-admin/societies/{id}` |
| Extend trial | `POST /api/v1/platform-admin/societies/{id}/extend-trial` |
| Suspend society | `POST /api/v1/platform-admin/societies/{id}/suspend` |
| Activate society | `POST /api/v1/platform-admin/societies/{id}/activate` |
| List all trials | `GET /api/v1/platform-admin/trials` |
| View usage stats | `GET /api/v1/platform-admin/stats` |
| Create platform admin | `POST /api/v1/platform-admin/admins` |

## Creating a Platform Admin User

Platform admin users are created via a seeded CLI command or the API itself
(first platform admin must be created by database seed or Django-style `createsuperuser`).

```python
# Seed script (run once on production):
user = User(
    email="ops@arsocietyapp.com",
    full_name="Platform Operations",
    hashed_password=hash_password("SecurePass@123"),
    status=UserStatus.ACTIVE,
    is_superadmin=True,
    must_change_password=False,
)
db.add(user)
db.commit()
```

## Security Isolation

- Platform Admin routes are under `/api/v1/platform-admin/` prefix
- All routes require `require_platform_admin()` dependency — no exceptions
- Society admin tokens cannot access platform admin routes
- Platform admin tokens CAN access society-level routes (for support purposes)
- All platform admin actions are audit-logged with `module="platform_admin"`

## Flutter (Future)

A separate Platform Admin Flutter app or web dashboard is planned.
Current implementation is API-only. Society-facing Flutter app does not
include any Platform Admin screens.
