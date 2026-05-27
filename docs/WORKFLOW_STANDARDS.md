# Workflow Standards — AR Society ERP

## FSM Pattern (Required for all status-driven models)

```python
class Status(str, enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    CLOSED = "closed"

TRANSITIONS: dict = {
    Status.DRAFT:  {Status.ACTIVE},
    Status.ACTIVE: {Status.CLOSED},
    Status.CLOSED: set(),
}
```

Validate in service before every status change:
```python
allowed = TRANSITIONS.get(entity.status, set())
if new_status not in allowed:
    raise HTTPException(409, f"Cannot transition from '{entity.status}' to '{new_status}'")
```

## Common Workflow Patterns

### Approval Workflow
```
PENDING → APPROVED → COMPLETED
        → REJECTED
        → CANCELLED
```
Used by: AmenityBooking, StaffLeave, AttendanceCorrection

### Assignment → Completion
```
ASSIGNED → ACKNOWLEDGED → IN_PROGRESS → COMPLETED → VERIFIED
```
Used by: StaffTask, ServiceRequest (Vendor)

### Handover
```
DRAFT → SUBMITTED → ACCEPTED → VERIFIED → CLOSED
                  → DISPUTED → ACCEPTED
```

## Audit Logging — Required Actions

| Action | When to Log |
|--------|------------|
| `CREATE` | Any new record creation |
| `UPDATE` | Status changes, major field updates |
| `APPROVE` | Any approval action |
| `REJECT` | Any rejection action |
| `LOGIN` | Auth events (success + failure) |

## Notification Hooks (in-app only)

Notify when:
- Item assigned to a user/staff
- Approval required (pending state)
- Approval granted or rejected
- Emergency/urgent alerts
- Bill generated, payment recorded

## Validation Patterns

### Duplicate Prevention
```python
existing = db.query(Model).filter(
    Model.society_id == sid,
    Model.field == value,
    Model.is_active == True
).first()
if existing:
    raise HTTPException(409, "Already exists")
```

### Date Range Overlap
```python
overlap = db.query(Model).filter(
    Model.start_date <= end_date,
    Model.end_date   >= start_date,
    Model.status.in_([Status.ACTIVE, Status.PENDING]),
).first()
if overlap:
    raise HTTPException(409, "Date range conflicts with existing record")
```

### Quantity/Stock Validation
```python
if requested_qty > available:
    raise HTTPException(409, f"Insufficient. Available: {available}")
```

## Multi-Tenant Isolation

Every service method operating on society data must accept `society_id` and filter:
```python
def get_items(self, society_id: UUID) -> List[Model]:
    return db.query(Model).filter(
        Model.society_id == society_id,
        Model.is_active  == True
    ).all()
```

## Finance Readiness Hooks

All financial entities must include:
- `Numeric(12,2)` for monetary amounts (not `Float`)
- `tax_percent` / `tax_amount` fields for GST
- `is_reversed` flag for payment reversals
- Immutable receipt/ledger pattern (append-only)
