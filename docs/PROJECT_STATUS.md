# Project Status — AR Society ERP

Last updated: 2026-06-13

---

## Completed Modules

### Backend

| Module | Status | Notes |
|--------|--------|-------|
| Auth (JWT + refresh) | ✅ Done | login, logout, change-password, /me |
| Society (CRUD) | ✅ Done | multi-tenant, trial dates as `date` type |
| Society Structure | ✅ Done | Wings, Floors, Flats with society_id isolation |
| Users & Roles (RBAC) | ✅ Done | society-scoped queries, 16 default roles (Manager + Gym Trainer added) |
| Onboarding (self-register) | ✅ Done | 9 default users, trial 30-day, audit log |
| Visitors | ✅ Done | create, list, approve, society-level |
| Complaints | ✅ Done | create, list, detail, society-level |
| Staff | ✅ Done | attendance, duties, handover, punch-in/punch-out approval hierarchy, checkout approval, supervisor-scoped endpoints, attendance summary (with late count), complaint→dept assignment, reporting_manager_id, address+notes fields, auto-user creation on email |
| Amenities | ✅ Done | booking FSM |
| Billing | ✅ Done | maintenance FSM |
| Inventory | ✅ Done | |
| Notices | ✅ Done | |
| Parking | ✅ Done | |
| Vendors | ✅ Done | |

### Flutter

| Feature | Status | Notes |
|---------|--------|-------|
| Auth flow | ✅ Done | GoRouter stable, web storage fix |
| Login screen | ✅ Done | |
| Change password screen | ✅ Done | |
| Role dashboards | ✅ Done | Admin, Committee, Resident, Security, Staff, Manager, Supervisor |
| Dashboard redesign | ✅ Done | Replaced large tile menu with compact summary cards, operational widgets, quick actions, and drawer navigation |
| Trial success screen | ✅ Done | Shows all 9 credentials, Copy All, Sign in as Admin |
| Society self-registration | ✅ Done | |
| Society Settings screen | ✅ Done | |
| Users list/detail/create/edit | ✅ Done | |
| Role assignment screen | ✅ Done | |
| Wings list + form | ✅ Done | |
| Floors list + form | ✅ Done | floorForm crash fixed 2026-06-06 |
| Flats list + form + detail | ✅ Done | |
| Visitors | ✅ Done | |
| Complaints | ✅ Done | |
| Staff (complete module) | ✅ Done | Staff Master (List/Add/Edit/Detail), all fields (photo, address, notes, emergency contact), auto-user creation with temp password + credentials dialog, Punch-in/out approval hierarchy, supervisor-scoped filters, duty assignment, complaint assignment, Manager Dashboard (live: pending checkin/checkout/absent/late/complaints), Supervisor Dashboard (live present/absent) |
| Setup Wizard | ✅ Done | 5-step |

---

## Known Security Fixes Applied

| Fix | Date | Details |
|-----|------|---------|
| Multi-tenant user isolation | 2026-06-06 | Added `society_id` FK to `users` table; all queries scoped |
| Society API 500 (Pydantic date type) | 2026-06-06 | `trial_start_date`/`trial_end_date` changed from `str` to `date` |
| GoRouter recreation on auth change | 2026-06-06 | `_RouterNotifier` + single GoRouter instance |
| Flutter web token storage | 2026-06-06 | `SharedPreferences` on web, `FlutterSecureStorage` on native |

---

## Deployment

- Backend: Railway (auto-deploy on push to `main`)
- Database: PostgreSQL on Railway
- Flutter: Web build served from Railway; native builds via CI
- API base: `https://arsocietyapp-production.up.railway.app/api/v1`
