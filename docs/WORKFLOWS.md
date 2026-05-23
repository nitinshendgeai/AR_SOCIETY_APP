# AR Society ERP — Workflows

## Authentication Flow

```
Client                       API
  │                           │
  ├─POST /auth/register───────►
  │                           │ hash password (bcrypt)
  │                           │ create User + assign "Resident" role
  │◄──── 201 UserOut ─────────┤
  │                           │
  ├─POST /auth/login──────────►
  │                           │ verify credentials
  │                           │ generate access + refresh JWT
  │◄──── TokenResponse ───────┤
  │                           │
  ├─GET /api/v1/auth/me ──────►  Bearer <access_token>
  │                           │  decode JWT → fetch User
  │◄──── UserOut ─────────────┤
  │                           │
  ├─POST /auth/refresh ───────►  Bearer <refresh_token>
  │                           │  rotate → new token pair
  │◄──── TokenResponse ───────┤
```

## Society Onboarding Workflow

```
Admin creates Society
  └── Admin creates Wing(s) under Society
        └── Admin creates Flat(s) under each Wing
              └── Admin/Committee creates Resident record for each Flat
                    └── Resident registers User account
                          └── Admin assigns Resident role (auto on register)
                                └── Resident linked to Flat via Resident model
```

## Tenant Move-in Workflow (Planned)

```
1. Owner (Resident) submits Tenant move-in request
2. Committee approves → status: pending_approval → approved
3. System creates Tenant record, links to Flat
4. Flat.occupancy_status updated → tenant_occupied
5. Security notified (push / SMS)
6. Tenant receives app invite via email
```

## Visitor Management Workflow (Planned)

```
1. Visitor arrives at gate
2. Security logs visitor details (name, vehicle, purpose)
3. Security calls/notifies Resident for approval
4. Resident approves via app → VisitorLog.status = approved
5. Security grants entry → records entry_time
6. On exit → Security records exit_time
7. Daily visitor report available to Committee
```

## Complaint Workflow (Planned)

```
Resident raises Complaint
  └── status: open
        └── Committee/Admin assigns to Staff member
              └── status: in_progress
                    └── Staff marks resolved
                          └── status: resolved (pending_closure)
                                └── Resident confirms → status: closed
                                      └── OR auto-close after 72h
```

## Finance / Maintenance Invoice Workflow (Planned)

```
1. Admin/Committee generates monthly maintenance invoices (bulk)
2. Residents notified via email/push
3. Resident makes payment (online gateway or manual)
4. Finance records payment → Invoice.status = paid
5. Reminder sent for overdue invoices (D+7, D+14, D+30)
6. Monthly Finance Report generated for Committee
```

## Amenity Booking Workflow (Planned)

```
Resident selects Amenity + time slot
  └── Availability check (no overlap)
        └── Booking created → status: pending
              └── Committee approves → status: confirmed
                    └── Resident notified
                          └── Post-booking: auto-release slot on completion
```
