from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID

from app.db.session import get_db
from app.models.role import Role
from app.models.user import User, UserRole
from app.models.permission import Permission, RolePermission
from app.core.dependencies import get_current_user, require_admin
from app.core.rbac_seed import PERMISSION_DEFINITIONS
from pydantic import BaseModel


class RoleListItem(BaseModel):
    id:          str
    name:        str
    description: Optional[str] = None

    model_config = {"from_attributes": True}


class PermissionListItem(BaseModel):
    code:        str
    name:        str
    description: Optional[str] = None


class RolePermissionMatrixRow(BaseModel):
    role_id:          str
    role_name:        str
    permission_codes: List[str]


class UpdateRolePermissionsRequest(BaseModel):
    permission_codes: List[str]


router = APIRouter(prefix="/roles", tags=["Roles"])


@router.get("/", response_model=List[RoleListItem])
def list_roles(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return roles that are in use within the caller's society.
    Superadmins / users without a society get all platform roles.
    """
    if not current_user.society_id:
        # Platform admin — show all
        roles = db.query(Role).order_by(Role.name).all()
    else:
        # Return distinct roles assigned to users in this society
        roles = (
            db.query(Role)
            .join(UserRole, UserRole.role_id == Role.id)
            .join(User, User.id == UserRole.user_id)
            .filter(User.society_id == current_user.society_id, User.is_active == True)
            .distinct()
            .order_by(Role.name)
            .all()
        )
        # If the society has no users yet, fall back to all platform roles
        if not roles:
            roles = db.query(Role).order_by(Role.name).all()

    return [RoleListItem(id=str(r.id), name=r.name, description=r.description)
            for r in roles]


@router.get("/permissions", response_model=List[PermissionListItem])
def list_permissions(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """The fixed set of access tiers the Permission Matrix can grant. These
    map 1:1 to the require_* guards in app.core.dependencies — see
    app.core.rbac_seed for the canonical definitions and default grants."""
    permissions = db.query(Permission).order_by(Permission.code).all()
    if not permissions:
        # Defensive fallback in case a deployment hasn't run the seed
        # migration yet — surface the static definitions rather than 404ing.
        return [PermissionListItem(code=code, name=name, description=desc)
                for code, name, desc in PERMISSION_DEFINITIONS]
    return [PermissionListItem(code=p.code, name=p.name, description=p.description)
            for p in permissions]


@router.get("/permission-matrix", response_model=List[RolePermissionMatrixRow])
def get_permission_matrix(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Every role in the system with the permission codes currently granted
    to it — the data backing the Permission Matrix editor screen."""
    roles = db.query(Role).order_by(Role.name).all()
    rows = []
    for role in roles:
        codes = sorted({
            rp.permission.code for rp in role.role_permissions if rp.permission
        })
        rows.append(RolePermissionMatrixRow(
            role_id=str(role.id), role_name=role.name, permission_codes=codes,
        ))
    return rows


@router.put("/{role_id}/permissions", response_model=RolePermissionMatrixRow)
def update_role_permissions(
    role_id: UUID,
    payload: UpdateRolePermissionsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Replace the full set of permissions granted to a role. Admin-only —
    this is the write path behind the Permission Matrix editor screen."""
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    valid_codes = {p.code for p in db.query(Permission).all()}
    unknown = set(payload.permission_codes) - valid_codes
    if unknown:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown permission code(s): {', '.join(sorted(unknown))}",
        )

    db.query(RolePermission).filter(RolePermission.role_id == role.id).delete()
    db.flush()

    permissions_by_code = {p.code: p for p in db.query(Permission)
                            .filter(Permission.code.in_(payload.permission_codes)).all()}
    for code in payload.permission_codes:
        db.add(RolePermission(role_id=role.id, permission_id=permissions_by_code[code].id))

    db.commit()

    codes = sorted(payload.permission_codes)
    return RolePermissionMatrixRow(role_id=str(role.id), role_name=role.name, permission_codes=codes)
