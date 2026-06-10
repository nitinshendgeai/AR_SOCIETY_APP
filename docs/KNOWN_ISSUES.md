# Known Issues — AR Society ERP

Last updated: 2026-06-10

---

## Active Issues

### [KNOWN GAP] Staff approval routing is role-convention, not enforced by FK

The supervisor-scoped attendance approval endpoint (`GET /staff/attendance/pending/supervisor/{society_id}?department=security`) relies on the calling user passing their own department — the backend does not re-derive the department from the authenticated token. A future improvement should extract department from the user's staff record and enforce it server-side.

### [KNOWN GAP] Complaint-to-department assignment does not auto-notify

When a manager assigns a complaint to a department via `POST /staff/complaints/assign-department`, the assigned supervisor receives no push notification. Notification infrastructure would be needed to close this gap.

### [KNOWN GAP] Manager/Supervisor dashboard approval counts are live-fetched per load

`approvalProvider` in `ManagerDashboardScreen` and `SupervisorDashboardScreen` makes individual API calls per session load. Consider WebSocket or SSE for real-time count updates in a future iteration.

## Recent Staff Workflow Update (2026-06-10)

Full staff hierarchy approval system implemented:
- Punch-in and punch-out approval with two-phase workflow
- Supervisor-scoped attendance filtering by department
- TECHNICAL and GYM departments added to enum
- Reporting Manager FK on staff records
- Complaint → department assignment by manager
- Manager Dashboard and Supervisor Dashboard screens in Flutter
- AttendanceApprovalScreen, DutyAssignScreen, StaffListScreen added

---

## Resolved Issues

### [FIXED 2026-06-06] FloorForm crash — WingModel passed as Map

**Symptom:** `TypeError: Instance of 'WingModel' type 'WingModel' is not a subtype of type 'Map<String,dynamic>'` when tapping Add Floor on the Floors screen.

**Root cause:** `FloorListScreen` Add Floor button passed `extra: wing` (raw `WingModel`) to `AppRoutes.floorForm`. The GoRouter builder for that route casts `state.extra as Map<String, dynamic>`, causing a type mismatch at runtime.

**Fix:** Changed `floor_list_screen.dart` line 27:
```dart
// Before (wrong)
extra: wing,

// After (correct)
extra: {'wing': wing, 'floor': null},
```

**Affected file:** `mobile/lib/features/society_structure/presentation/screens/floor_list_screen.dart`

---

### [FIXED 2026-06-06] GET /api/v1/societies/ → 500 Internal Server Error

**Symptom:** Society Settings screen showed no data; browser console reported CORS error (misleading).

**Root cause:** `SocietyOut.trial_start_date: Optional[str]` but SQLAlchemy returns `datetime.date` objects. Pydantic v2 in strict mode raises `ValidationError` → FastAPI returns 500 before setting CORS headers.

**Fix:** Changed `backend/app/schemas/society.py` field types from `Optional[str]` to `Optional[date]`.

---

### [FIXED 2026-06-06] Flutter login fails after successful API response

**Symptom:** API returns 200 with tokens; Flutter logs `[LOGIN_ERROR] Unexpected: OperationError`.

**Root cause (1):** `flutter_secure_storage` throws `OperationError` on Chrome localhost via Web Crypto AES-GCM. Token save appeared to succeed but read-back failed.

**Root cause (2):** GoRouter was recreated on every `authProvider` state change (because `appRouterProvider` used `ref.watch(authProvider)`), resetting the nav stack to splash during login.

**Fix:** Platform-aware token storage (`SharedPreferences` on web via `kIsWeb`); single GoRouter instance with `refreshListenable: _RouterNotifier`.

---

### [FIXED 2026-06-06] Users & Roles screen showing users from ALL societies

**Symptom:** Admin of Society A could see users from Society B.

**Root cause:** `users` table had no `society_id` column. All user queries were unscoped.

**Fix:** Added `society_id` FK to `users` table (migration `b1c2d3e4f5a6`); all repository/service/route methods scoped by `society_id` extracted from the authenticated admin's token.
