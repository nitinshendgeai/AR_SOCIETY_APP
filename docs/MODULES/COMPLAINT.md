# Complaint Module

## Purpose
Resident complaint lifecycle from submission to resolution with escalation readiness.

## Core Entities
| Entity | Table | Purpose |
|--------|-------|---------|
| Complaint | `complaints` | Master complaint with FSM status |
| ComplaintComment | `complaint_comments` | Threaded comments |
| ComplaintAttachment | `complaint_attachments` | File URLs |
| ComplaintStatusHistory | `complaint_status_history` | Immutable status trail |

## Workflow
```
OPEN → ASSIGNED → IN_PROGRESS → RESOLVED → CLOSED
     → REJECTED
```

## RBAC
| Action | Roles |
|--------|-------|
| Create complaint | Any member |
| Assign/update | Admin, Committee, Staff |
| Close/reject | Admin, Committee |
| View society complaints | Admin, Committee |
| View own complaints | Resident |

## Integration Readiness
- `complaint_id` foreign key on `StaffTask` — tasks can be raised from complaints
- `complaint_id` on `ServiceRequest` (Vendor) — vendor jobs from complaints
