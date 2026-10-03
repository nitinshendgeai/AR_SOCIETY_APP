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

## Rules (forms and API)
- Title (≤255) and description (≤5000) are trimmed and never blank; comment ≤2000, notes/reasons ≤1000; an attachment needs a name, an `http(s)://` link and a size ≥ 0.
- **Resolving needs `resolution_notes`; rejecting needs `rejection_reason`; reopening needs a reason** (422 otherwise). Rejecting is for a manager or the committee.
- **Numbers run per society** (`CMP-00001`…); the uniqueness is `(society_id, complaint_number)`. Before, it was unique platform-wide, so a second society's first complaint failed.
- **Scoping**: a complaint, its comments, attachments and the society lists never cross a society (404 / 403). Filing for another society, or a flat outside it, is refused; the assignee must be an active user of the same society.
- **Residents and tenants** see, comment on and reopen only complaints raised by them or for their flat (others → 404); their comments are never private, and staff's internal notes are left out of what they see. The complaint shows who raised it and who wrote each comment (`raised_by_name`, `author_name`).
- Lists are paged (`limit` 1–200).

## Integration Readiness
- `complaint_id` foreign key on `StaffTask` — tasks can be raised from complaints
- `complaint_id` on `ServiceRequest` (Vendor) — vendor jobs from complaints
