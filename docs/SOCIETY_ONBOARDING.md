# Society Onboarding Workflow

## One-Shot Registration
```
POST /api/v1/societies/register-and-initialize
```
Creates society + default roles + default users in one transaction.

## Two-Step Registration
```
POST /api/v1/societies/              → creates society
POST /api/v1/societies/{id}/initialize → creates roles + users
```

## Default Roles Created
Super Admin · Society Admin · Committee · Security · Staff · Resident

## Default Operational Users
| Email | Role |
|-------|------|
| admin@{code}.arsociety.com | Society Admin |
| security@{code}.arsociety.com | Security |
| staff@{code}.arsociety.com | Staff |

All default users: `must_change_password=True` — force reset on first login.
Temporary password returned in response (store securely, shown once).

## Idempotent
Running initialize twice is safe — skips existing users/roles.
