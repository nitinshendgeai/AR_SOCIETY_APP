# AR Society ERP — Roadmap

## ✅ Phase 1 — Foundation (Complete)

## ✅ Phase 1.5 — Backend Hardening (Complete)

- [x] Standardized API response envelopes (SuccessResponse, ErrorResponse, PaginatedResponse)
- [x] Global exception handlers (ValidationError, IntegrityError, generic 500)
- [x] AuditLog model + AuditService (CREATE/UPDATE/DELETE/LOGIN/APPROVE/REJECT)
- [x] Notification model + NotificationService (in_app/email/sms/push stubs)
- [x] Notification routes (GET unread, PATCH mark-read)
- [x] Alembic migration: audit_logs + notifications tables
- [x] Response helpers (success, created, error, not_found, forbidden)
- [x] Structured logging across all layers

- [x] FastAPI project scaffold (clean architecture)
- [x] PostgreSQL + SQLAlchemy 2.0 ORM
- [x] UUID primary keys + BaseModel mixin (created_at, updated_at, is_active)
- [x] JWT Authentication (access + refresh token rotation)
- [x] bcrypt password hashing
- [x] RBAC system (Admin, Committee, Resident, Security, Staff)
- [x] Multi-role per user (UserRole junction table)
- [x] CRUD APIs: Society, Wing, Flat, User
- [x] routes → services → repositories architecture
- [x] Railway deployment config (Procfile, runtime.txt)
- [x] CORS middleware
- [x] GET /health endpoint
- [x] Documentation (Architecture, RBAC, Workflows, Roadmap)

---

## 🔄 Phase 2 — Resident & Tenant Management

- [ ] Resident CRUD API + schemas
- [ ] Tenant CRUD API + lease tracking
- [ ] Resident self-service profile update
- [ ] Document upload (ID proof, agreement)
- [ ] Flat occupancy status auto-update on resident/tenant change
- [ ] Move-in / move-out workflow

---

## 🔄 Phase 3 — Visitor & Gate Management

- [ ] VisitorLog model (name, vehicle, purpose, entry/exit timestamps)
- [ ] Gate pass generation (QR code)
- [ ] Security dashboard API
- [ ] Resident approval workflow (webhook / push notification hook)
- [ ] Daily visitor report endpoint

---

## 🔄 Phase 4 — Complaints & Helpdesk

- [ ] Complaint model (category, priority, status FSM)
- [ ] Assignment to Staff member
- [ ] Status transitions: open → in_progress → resolved → closed
- [ ] Resident confirmation / auto-close
- [ ] Complaint analytics endpoint

---

## 🔄 Phase 5 — Finance ERP

- [ ] MaintenanceInvoice model (flat, period, amount, due_date)
- [ ] Bulk invoice generation (monthly)
- [ ] Payment recording (manual + gateway webhook)
- [ ] Overdue reminders (background task / Celery)
- [ ] Finance reports (collected, outstanding, flat-wise)
- [ ] GST calculation support

---

## 🔄 Phase 6 — Amenities Management

- [ ] Amenity model (name, location, capacity, pricing)
- [ ] TimeSlot model (availability matrix)
- [ ] Booking model + overlap prevention
- [ ] Approval workflow
- [ ] Booking history + cancellations
- [ ] Revenue reporting per amenity

---

## 🔄 Phase 7 — Staff & Payroll

- [ ] Staff model (designation, joining date, bank details)
- [ ] Attendance tracking (daily mark-in / mark-out)
- [ ] Payroll calculation (base + allowances + deductions)
- [ ] Payslip generation (PDF)
- [ ] Leave management (types, approval)

---

## 🔄 Phase 8 — Inventory Management

- [ ] InventoryItem model (name, category, unit, quantity)
- [ ] Stock-in / stock-out transactions
- [ ] Low-stock alerts
- [ ] Vendor management
- [ ] Purchase order workflow

---

## 🔄 Phase 9 — Workflow Engine

- [ ] Generic WorkflowDefinition model (BPMN-lite)
- [ ] WorkflowInstance + step tracking
- [ ] Rule-based auto-transitions
- [ ] Notification hooks per step
- [ ] Pluggable approval chains

---

## 🔄 Phase 10 — Platform

- [ ] Alembic migrations (replace create_all)
- [ ] Async SQLAlchemy (asyncpg)
- [ ] Redis caching layer
- [ ] Celery background tasks (reminders, reports)
- [ ] Email service integration (SendGrid / SES)
- [ ] Push notification service (Firebase FCM)
- [ ] Multi-tenancy isolation (RLS or schema-per-tenant)
- [ ] Admin super-dashboard (aggregate across societies)
- [ ] Audit log (every write action stored)
- [ ] Rate limiting (slowapi)
- [ ] OpenAPI SDK generation (TypeScript, Flutter)
