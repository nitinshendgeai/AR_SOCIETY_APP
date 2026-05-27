# RBAC Matrix — AR Society ERP

## Roles

| Role | Description |
|------|------------|
| Admin | Full system access |
| Committee | Society management, approvals |
| Resident | Own flat, complaints, bookings |
| Security | Gate, visitor, parking operations |
| Staff | Maintenance, housekeeping, tasks |

## Permission Matrix

`✓` = Allowed · `✗` = Denied · `own` = Own records only

### Society & Master
| Action | Admin | Committee | Resident | Security | Staff |
|--------|-------|-----------|----------|----------|-------|
| Create/delete society | ✓ | ✗ | ✗ | ✗ | ✗ |
| Update society | ✓ | ✓ | ✗ | ✗ | ✗ |
| View society | ✓ | ✓ | ✓ | ✓ | ✓ |
| Manage wings/flats | ✓ | ✓ | ✗ | ✗ | ✗ |
| Register vehicle | ✓ | ✓ | ✓ | ✓ | ✓ |
| Move-in / move-out | ✓ | ✓ | ✗ | ✗ | ✗ |

### User Management
| Action | Admin | Committee | Resident | Security | Staff |
|--------|-------|-----------|----------|----------|-------|
| List all users | ✓ | ✗ | ✗ | ✗ | ✗ |
| Assign roles | ✓ | ✗ | ✗ | ✗ | ✗ |
| View own profile | ✓ | ✓ | ✓ | ✓ | ✓ |

### Visitor & Gate
| Action | Admin | Committee | Resident | Security | Staff |
|--------|-------|-----------|----------|----------|-------|
| Create visitor entry | ✓ | ✓ | ✗ | ✓ | ✗ |
| Approve visitor | ✓ | ✓ | ✓ | ✗ | ✗ |
| View visitor list | ✓ | ✓ | own | ✓ | ✗ |

### Complaints
| Action | Admin | Committee | Resident | Security | Staff |
|--------|-------|-----------|----------|----------|-------|
| Create complaint | ✓ | ✓ | ✓ | ✓ | ✓ |
| Assign/update | ✓ | ✓ | ✗ | ✗ | ✓ |
| Close/reject | ✓ | ✓ | ✗ | ✗ | ✗ |

### Amenities
| Action | Admin | Committee | Resident | Security | Staff |
|--------|-------|-----------|----------|----------|-------|
| Configure amenity/rules | ✓ | ✓ | ✗ | ✗ | ✗ |
| Create booking | ✓ | ✓ | ✓ | ✓ | ✓ |
| Approve/reject booking | ✓ | ✓ | ✗ | ✗ | ✗ |
| View availability | ✓ | ✓ | ✓ | ✓ | ✓ |

### Staff Operations
| Action | Admin | Committee | Resident | Security | Staff |
|--------|-------|-----------|----------|----------|-------|
| Create/manage staff | ✓ | ✓ | ✗ | ✗ | ✗ |
| Check-in/out | ✓ | ✓ | ✗ | ✗ | ✓ |
| Assign duty/task | ✓ | ✓ | ✗ | ✗ | ✗ |
| Update task status | ✓ | ✓ | ✗ | ✗ | ✓ |
| Apply leave | ✓ | ✓ | ✗ | ✗ | ✓ |
| Approve leave | ✓ | ✓ | ✗ | ✗ | ✗ |
| Create handover | ✓ | ✓ | ✗ | ✓ | ✓ |
| Verify handover | ✓ | ✓ | ✗ | ✗ | ✓ |
| Workload analytics | ✓ | ✓ | ✗ | ✗ | ✗ |

### Inventory & Assets
| Action | Admin | Committee | Resident | Security | Staff |
|--------|-------|-----------|----------|----------|-------|
| Manage items/assets | ✓ | ✓ | ✗ | ✗ | ✗ |
| Issue/return items | ✓ | ✓ | ✗ | ✗ | ✓ |
| View stock | ✓ | ✓ | ✗ | ✗ | ✓ |

### Parking
| Action | Admin | Committee | Resident | Security | Staff |
|--------|-------|-----------|----------|----------|-------|
| Manage zones/slots | ✓ | ✓ | ✗ | ✗ | ✗ |
| Allocate slots | ✓ | ✓ | ✗ | ✗ | ✗ |
| Assign visitor parking | ✓ | ✓ | ✗ | ✓ | ✗ |
| Report violations | ✓ | ✓ | ✗ | ✓ | ✗ |
| View own allocation | ✓ | ✓ | ✓ | ✓ | ✓ |

### Billing
| Action | Admin | Committee | Resident | Security | Staff |
|--------|-------|-----------|----------|----------|-------|
| Generate/issue bills | ✓ | ✓ | ✗ | ✗ | ✗ |
| Record payments | ✓ | ✓ | ✗ | ✗ | ✗ |
| View own bills | ✓ | ✓ | ✓ | ✗ | ✓ |
| View outstanding reports | ✓ | ✓ | ✗ | ✗ | ✗ |

### Vendor & AMC
| Action | Admin | Committee | Resident | Security | Staff |
|--------|-------|-----------|----------|----------|-------|
| Manage vendors/contracts | ✓ | ✓ | ✗ | ✗ | ✗ |
| Create service requests | ✓ | ✓ | ✗ | ✗ | ✓ |
| Assign vendor | ✓ | ✓ | ✗ | ✗ | ✗ |
| Update SR / log visits | ✓ | ✓ | ✗ | ✗ | ✓ |

### Notice & Communication
| Action | Admin | Committee | Resident | Security | Staff |
|--------|-------|-----------|----------|----------|-------|
| Create/publish notices | ✓ | ✓ | ✗ | ✗ | ✗ |
| Trigger emergency alert | ✓ | ✓ | ✗ | ✗ | ✗ |
| Acknowledge notice | ✓ | ✓ | ✓ | ✓ | ✓ |
| View notices | ✓ | ✓ | ✓ | ✓ | ✓ |

## Code Reference

```python
# Common dependency groups
admin_only       = require_roles("Admin")
admin_committee  = require_roles("Admin", "Committee")
supervisor_above = require_roles("Admin", "Committee", "Staff")
security_above   = require_roles("Admin", "Committee", "Security")
any_staff        = require_roles("Admin", "Committee", "Staff", "Security")
any_member       = require_roles("Admin", "Committee", "Resident", "Staff", "Security")
```
