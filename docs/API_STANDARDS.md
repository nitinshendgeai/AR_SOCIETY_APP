# API Standards — AR Society ERP

## URL Structure
```
/api/v1/{module}/{resource}
/api/v1/{module}/{resource}/{id}/{action}
```

## HTTP Methods
| Operation | Method | Status |
|-----------|--------|--------|
| Create | POST | 201 |
| Read | GET | 200 |
| Update (partial) | PATCH | 200 |
| Delete (soft) | DELETE | 204 |
| Workflow action | POST `/{id}/action` | 200 |

## Response Envelope
All responses return the model directly (no wrapper). Errors use FastAPI's default:
```json
{"detail": "Human-readable error message"}
```

Validation errors (422):
```json
{"message": "Validation failed", "errors": [{"field": "...", "msg": "..."}]}
```

## Pagination
```
GET /resource?skip=0&limit=50
```
Default: `skip=0, limit=50`. Max limit: 100.

## Authentication
All protected routes require:
```
Authorization: Bearer <access_token>
```
- Access token: 30 min expiry
- Refresh token: 7 days expiry
- Endpoint: `POST /api/v1/auth/refresh`

## RBAC Enforcement Pattern
```python
# Route-level (no user object needed):
@router.get("/", dependencies=[Depends(require_roles("Admin", "Committee"))])

# Route-level (user object needed):
@router.post("/")
def create(user: User = Depends(require_roles("Admin"))):
    ...
```

## Naming Conventions
| Pattern | Example |
|---------|---------|
| List endpoint | `GET /amenities/society/{society_id}` |
| Get one | `GET /amenities/{id}` |
| Create | `POST /amenities/` |
| Workflow action | `POST /amenities/bookings/{id}/approve` |
| Filtered list | `GET /staff/society/{id}/department/{dept}` |

## Auto-Generated Codes
| Entity | Format | Example |
|--------|--------|---------|
| Invoice | `INV-{YEAR}-{NNNNN}` | `INV-2026-00001` |
| Receipt | `RCP-{YEAR}-{NNNNN}` | `RCP-2026-00001` |
| Staff | `EMP-{NNNN}` | `EMP-0001` |
| Asset | `AST-{NNNN}` | `AST-0001` |
| Inventory | `INV-{NNNNN}` | `INV-00001` |
| Vendor | `VND-{NNNN}` | `VND-0001` |
| AMC Contract | `AMC-{YEAR}-{NNNN}` | `AMC-2026-0001` |
| Service Request | `SRQ-{NNNNN}` | `SRQ-00001` |

## Error Status Codes
| Code | Meaning |
|------|---------|
| 400 | Duplicate / bad request |
| 401 | Invalid/expired token |
| 403 | Insufficient role |
| 404 | Not found |
| 409 | FSM conflict / duplicate active record |
| 422 | Validation error |
| 500 | Unhandled server error |
