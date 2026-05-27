# AI Development Rules — AR Society ERP

> **This is the permanent instruction base for all future AI-assisted development.**
> Start every session by reading this file + the relevant module doc.

---

## 1. Before Writing Any Code

```
1. git log --oneline -5          # understand recent changes
2. ls backend/app/modules/       # know what exists
3. Read relevant MODULES/*.md    # source of truth for that module
4. grep existing models/routes   # confirm what's already built
```

**Never assume — always inspect first.**

---

## 2. Golden Rules

| Rule | Detail |
|------|--------|
| **Don't duplicate** | If it exists and works, skip it |
| **Don't overwrite** | Only fix broken or incomplete code |
| **Minimal tokens** | Write only what's missing |
| **Preserve arch** | Follow routes → services → repositories always |
| **Validate before commit** | App imports, tests pass, migrations valid |

---

## 3. Architecture Pattern (Non-Negotiable)

```
routes/          → HTTP layer only (Pydantic in/out, Depends)
services/        → Business logic, FSM, validations, notifications
repositories/    → DB queries only (extend BaseRepository)
models/          → SQLAlchemy + TimestampMixin + enums + FSM dict
schemas/         → Pydantic v2 (OrmBase / TimestampSchema)
```

Every module lives in `backend/app/modules/{name}/` with this exact structure.

---

## 4. New Module Checklist

```
□ models/      — SQLAlchemy models + enums + FSM transitions dict
□ schemas/     — Pydantic in/out schemas
□ repositories/ — Queries extending BaseRepository
□ services/    — Business logic
□ routes/      — Registered in app/api/__init__.py
□ __init__.py  — Models registered in app/models/__init__.py
□ Migration    — alembic revision, written manually (not autogenerate)
□ Tests        — At least happy path + key validations
□ Docs         — MODULES/{NAME}.md updated
```

---

## 5. FSM Workflows

Every workflow with status transitions **must** use a `dict` constant:

```python
BOOKING_TRANSITIONS: dict = {
    BookingStatus.PENDING:   {BookingStatus.APPROVED, BookingStatus.CANCELLED},
    BookingStatus.APPROVED:  {BookingStatus.COMPLETED, BookingStatus.CANCELLED},
    ...
}
```

Validate in service:
```python
allowed = TRANSITIONS.get(entity.status, set())
if new_status not in allowed:
    raise HTTPException(409, f"Cannot transition from {entity.status} to {new_status}")
```

---

## 6. Required on Every Model

```python
class MyModel(Base, TimestampMixin):   # includes id, created_at, updated_at, is_active
    __tablename__ = "my_models"
    society_id = Column(UUID, ForeignKey("societies.id", ondelete="CASCADE"), index=True)
```

---

## 7. Audit Logging

**Required on:** create, approve, reject, cancel, major status changes.

```python
AuditService.log(db=db, action=AuditAction.CREATE, module="module_name",
                 entity_id=str(obj.id), entity_type="ModelName",
                 user=user, request=request,
                 new_values={"key": "value"})
```

---

## 8. Notifications

**Required on:** assignment, approval, rejection, alerts. Always `in_app` — no external providers yet.

```python
NotificationService.send(db=db, user_id=user_id, title="...", body="...",
    type=NotificationType.INFO, channel=NotificationChannel.IN_APP,
    module="module_name", entity_id=str(entity.id))
```

---

## 9. Migrations

- **Always written manually** — never use `--autogenerate` in production
- **Chain**: always set `down_revision` to the previous migration's `revision`
- **One revision per sprint** unless modules are truly independent
- **Verify chain**: `alembic heads` must show exactly one head

```bash
alembic revision -m "description"   # generates file
# Then manually fill upgrade()/downgrade()
```

---

## 10. Validation & Commit Sequence

```bash
# 1. Test imports
DATABASE_URL="..." SECRET_KEY="x" python -c "from app.main import app; print(len(app.routes))"

# 2. Run tests
make test   # must be 0 failures

# 3. Check migrations
alembic heads   # must be exactly 1

# 4. Commit
git add -A && git commit -m "feat/fix/test/docs: description"
git push origin main
```

---

## 11. Society Isolation

Every query on multi-tenant data **must** filter by `society_id`:
```python
db.query(Model).filter(Model.society_id == society_id, Model.is_active == True)
```

---

## 12. RBAC Enforcement

```python
# In routes — use dependency factories:
admin_committee = require_roles("Admin", "Committee")
any_member      = require_roles("Admin", "Committee", "Resident", "Staff", "Security")

@router.post("/", dependencies=[Depends(admin_committee)])
```

Never bypass RBAC with `get_current_user` alone on protected endpoints.

---

## 13. File Naming Conventions

| Type | Convention | Example |
|------|-----------|---------|
| Model | snake_case | `staff_attendance.py` |
| Route prefix | plural noun | `/staff`, `/amenities` |
| Enum values | lowercase snake | `"partially_paid"` |
| Migration msg | snake_case | `"staff_operations_module"` |
| Auto-codes | PREFIX-NNNN | `EMP-0001`, `INV-00001` |

---

## 14. What NOT To Do

- ❌ Don't use `--autogenerate` for migrations
- ❌ Don't hardcode rules (use DB-driven rule engine)
- ❌ Don't put business logic in routes
- ❌ Don't use `db.query().all()` without `is_active == True` filter
- ❌ Don't commit without running tests
- ❌ Don't add pytest/faker to `requirements.txt` (use `requirements-dev.txt`)
- ❌ Don't start new modules when stabilization is needed
