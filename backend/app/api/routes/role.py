from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID

from app.db.session import get_db
from app.models.role import Role
from app.models.user import User, UserRole
from app.models.permission import Permission, RolePermission
from app.models.form import Form, RoleForm
from app.core.dependencies import get_current_user, require_admin
from app.models.audit_log import AuditAction
from app.services.audit_service import AuditService
from app.core.rbac_seed import PERMISSION_DEFINITIONS, FORM_DEFINITIONS

PLATFORM_FORM = "platform_admin"
from pydantic import BaseModel


class RoleListItem(BaseModel):
    id:          str
    name:        str
    description: Optional[str] = None
    # A role the caller's society made for itself (it can be renamed and deleted); the standard roles are shared.
    is_custom:   bool = False
    # How many users of the caller's society hold it (every society's, for a platform admin)
    user_count:  int = 0

    model_config = {"from_attributes": True}


class CreateRoleRequest(BaseModel):
    name:             str
    description:      Optional[str] = None
    # Start from what another role may do (its permissions and screens); they can be changed afterwards
    copy_from_role_id: Optional[UUID] = None


class UpdateRoleRequest(BaseModel):
    name:        Optional[str] = None
    description: Optional[str] = None


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


class FormListItem(BaseModel):
    code:        str
    name:        str
    description: Optional[str] = None


class RoleFormMatrixRow(BaseModel):
    role_id:    str
    role_name:  str
    form_codes: List[str]


class UpdateRoleFormsRequest(BaseModel):
    form_codes: List[str]


class MyFormsResponse(BaseModel):
    form_codes: List[str]


router = APIRouter(prefix="/roles", tags=["Roles"])

PLATFORM_ROLE = "Platform Admin"


def _visible_roles(db: Session, user: User):
    """Roles a caller may see and edit: the standard roles and the caller's own society's roles. The Platform Admin role
    belongs to the platform team, so a society's admin never sees it; another society's own roles are not theirs to see."""
    q = db.query(Role)
    if not user.is_superadmin:
        q = q.filter((Role.society_id.is_(None)) | (Role.society_id == user.society_id), Role.name != PLATFORM_ROLE)
    return q.order_by(Role.name).all()


def _role_or_404(db: Session, role_id: UUID, user: User) -> Role:
    """A role the caller may touch. Another society's own role reads as not found."""
    role = db.query(Role).filter(Role.id == role_id).first()
    if role is None or (not user.is_superadmin and role.society_id not in (None, user.society_id)):
        raise HTTPException(status_code=404, detail="Role not found")
    return role


def _guard_platform_role(role: Role, user: User) -> None:
    if role.name == PLATFORM_ROLE and not user.is_superadmin:
        raise HTTPException(status_code=403, detail="Only a platform admin can change the Platform Admin role")


def _clean_role_name(db: Session, name: str, society_id, exclude_id=None) -> str:
    """A name a society's own role may take: trimmed, 3 to 60 characters with a letter in it, and not a standard role's
    name nor another role of the society's (compared without regard to case)."""
    cleaned = " ".join((name or "").split())
    if not 3 <= len(cleaned) <= 60 or not any(c.isalpha() for c in cleaned) or any(ord(c) < 32 for c in cleaned):
        raise HTTPException(status_code=422, detail="A role name is 3 to 60 characters and has a letter in it")
    if cleaned.lower() == PLATFORM_ROLE.lower():                 # the platform team's role, which a society never sees
        raise HTTPException(status_code=409, detail=f"'{PLATFORM_ROLE}' is already a standard role")
    taken = db.query(Role).filter(func.lower(Role.name) == cleaned.lower(),
                                  (Role.society_id.is_(None)) | (Role.society_id == society_id))
    if exclude_id is not None:
        taken = taken.filter(Role.id != exclude_id)
    other = taken.first()
    if other is not None:
        what = "a standard role" if other.society_id is None else "a role of your society"
        raise HTTPException(status_code=409, detail=f"'{other.name}' is already {what}")
    return cleaned


def _custom_role_of_caller(db: Session, role_id: UUID, user: User) -> Role:
    role = _role_or_404(db, role_id, user)
    if role.society_id is None:
        raise HTTPException(status_code=403, detail="A standard role is shared by every society and can't be changed "
                                                    "here; set what it may do in the Permission and Forms matrices")
    return role


@router.get("/", response_model=List[RoleListItem])
def list_roles(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return every assignable role: the standard roles, which are shared, and the caller's own society's roles. A
    society must be able to pick any standard role (e.g. Manager, Security Staff) even before anyone in the society
    holds it.
    """
    roles = _visible_roles(db, current_user)
    counts = db.query(UserRole.role_id, func.count(UserRole.id)).join(User, User.id == UserRole.user_id)
    if current_user.society_id is not None and not current_user.is_superadmin:
        counts = counts.filter(User.society_id == current_user.society_id)
    counts = dict(counts.group_by(UserRole.role_id).all())
    return [RoleListItem(id=str(r.id), name=r.name, description=r.description, is_custom=r.society_id is not None,
                         user_count=int(counts.get(r.id, 0)))
            for r in roles]


@router.post("/", response_model=RoleListItem, status_code=201)
def create_role(
    payload: CreateRoleRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """A society's admin adds a role for the society: a name, a description, and optionally another role to start from
    (its permissions and screens are copied). Only this society sees and can give out the new role."""
    if current_user.society_id is None:
        raise HTTPException(status_code=403, detail="Roles are added by a society's admin")
    name = _clean_role_name(db, payload.name, current_user.society_id)
    description = (payload.description or "").strip() or None
    if description and len(description) > 500:
        raise HTTPException(status_code=422, detail="The description can be at most 500 characters")
    source = None
    if payload.copy_from_role_id:
        source = _role_or_404(db, payload.copy_from_role_id, current_user)
        _guard_platform_role(source, current_user)
    role = Role(name=name, description=description, society_id=current_user.society_id)
    db.add(role)
    db.flush()
    if source is not None:
        for rp in source.role_permissions:
            db.add(RolePermission(role_id=role.id, permission_id=rp.permission_id))
        for rf in source.role_forms:
            if rf.form and rf.form.code != PLATFORM_FORM:
                db.add(RoleForm(role_id=role.id, form_id=rf.form_id))
    db.commit()
    AuditService.log(db=db, action=AuditAction.CREATE, module="rbac", entity_id=str(role.id), entity_type="Role",
                     new_values={"name": name, "copied_from": source.name if source else None},
                     notes=f"Role '{name}' added", user=current_user)
    return RoleListItem(id=str(role.id), name=role.name, description=role.description, is_custom=True, user_count=0)


@router.patch("/{role_id}", response_model=RoleListItem)
def update_role(
    role_id: UUID,
    payload: UpdateRoleRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Rename a role of the society's own, or change its description. The standard roles are not changed here."""
    role = _custom_role_of_caller(db, role_id, current_user)
    before = {"name": role.name, "description": role.description}
    changes = payload.model_dump(exclude_unset=True)
    if changes.get("name") is not None:
        role.name = _clean_role_name(db, changes["name"], role.society_id, exclude_id=role.id)
    if "description" in changes:
        description = (changes["description"] or "").strip() or None
        if description and len(description) > 500:
            raise HTTPException(status_code=422, detail="The description can be at most 500 characters")
        role.description = description
    db.commit()
    AuditService.log(db=db, action=AuditAction.UPDATE, module="rbac", entity_id=str(role.id), entity_type="Role",
                     old_values=before, new_values={"name": role.name, "description": role.description},
                     notes=f"Role '{before['name']}' changed", user=current_user)
    held = db.query(func.count(UserRole.id)).join(User, User.id == UserRole.user_id).filter(
        UserRole.role_id == role.id, User.society_id == role.society_id).scalar()
    return RoleListItem(id=str(role.id), name=role.name, description=role.description, is_custom=True,
                        user_count=int(held or 0))


@router.delete("/{role_id}", status_code=204)
def delete_role(
    role_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Delete a role of the society's own, once nobody holds it. Its permissions and screens go with it."""
    role = _custom_role_of_caller(db, role_id, current_user)
    held = db.query(func.count(UserRole.id)).filter(UserRole.role_id == role.id).scalar() or 0
    if held:
        raise HTTPException(status_code=409, detail=f"{held} user{' holds' if held == 1 else 's hold'} this role. "
                                                    "Remove it from them first")
    name, rid = role.name, str(role.id)
    db.delete(role)
    db.commit()
    AuditService.log(db=db, action=AuditAction.DELETE, module="rbac", entity_id=rid, entity_type="Role",
                     old_values={"name": name}, notes=f"Role '{name}' deleted", user=current_user)


@router.get("/forms/mine", response_model=MyFormsResponse)
def get_my_forms(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """The current user's own granted form codes — every authenticated user
    can read this (it's about themselves), unlike the admin-only matrix
    endpoints below. The mobile app calls this on login and uses the result
    to decide which navigation items to render, instead of hardcoding role
    checks client-side."""
    codes = set()
    for ur in current_user.user_roles:
        role = ur.role
        if not role:
            continue
        for rf in role.role_forms:
            if rf.form:
                codes.add(rf.form.code)
    # Menu items of a service the platform owner has switched off for this society are not offered.
    if current_user.society_id is not None and not getattr(current_user, "is_superadmin", False):
        from app.core.services_catalog import SERVICES, effective_services
        on = effective_services(db, current_user.society_id)
        for service in SERVICES:
            if service.key not in on:
                codes.difference_update(service.form_codes)
    return MyFormsResponse(form_codes=sorted(codes))


@router.get("/forms", response_model=List[FormListItem])
def list_forms(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """The fixed set of top-level screens the Forms Matrix can grant. See
    app.core.rbac_seed for the canonical definitions and default grants."""
    forms = db.query(Form).order_by(Form.code).all()
    if not current_user.is_superadmin:
        forms = [f for f in forms if f.code != PLATFORM_FORM]      # a society admin never grants the console
    if not forms:
        # Defensive fallback in case a deployment hasn't run the seed
        # migration yet — surface the static definitions rather than 404ing.
        return [FormListItem(code=code, name=name, description=desc)
                for code, name, desc in FORM_DEFINITIONS]
    return [FormListItem(code=f.code, name=f.name, description=f.description)
            for f in forms]


@router.get("/form-matrix", response_model=List[RoleFormMatrixRow])
def get_form_matrix(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Every role in the system with the form codes currently granted to
    it — the data backing the Forms Matrix editor screen."""
    rows = []
    for role in _visible_roles(db, current_user):
        codes = sorted({
            rf.form.code for rf in role.role_forms if rf.form
            and (current_user.is_superadmin or rf.form.code != PLATFORM_FORM)
        })
        rows.append(RoleFormMatrixRow(
            role_id=str(role.id), role_name=role.name, form_codes=codes,
        ))
    return rows


@router.put("/{role_id}/forms", response_model=RoleFormMatrixRow)
def update_role_forms(
    role_id: UUID,
    payload: UpdateRoleFormsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Replace the full set of forms granted to a role. Admin-only — this
    is the write path behind the Forms Matrix editor screen."""
    role = _role_or_404(db, role_id, current_user)

    _guard_platform_role(role, current_user)
    valid_codes = {f.code for f in db.query(Form).all()
                   if current_user.is_superadmin or f.code != PLATFORM_FORM}
    unknown = set(payload.form_codes) - valid_codes
    if unknown:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown form code(s): {', '.join(sorted(unknown))}",
        )

    old_codes = sorted(rf.form.code for rf in role.role_forms if rf.form)
    db.query(RoleForm).filter(RoleForm.role_id == role.id).delete()
    db.flush()

    forms_by_code = {f.code: f for f in db.query(Form)
                      .filter(Form.code.in_(payload.form_codes)).all()}
    for code in payload.form_codes:
        db.add(RoleForm(role_id=role.id, form_id=forms_by_code[code].id))

    db.commit()

    codes = sorted(payload.form_codes)
    # Roles are shared by every society, so a matrix change reaches them all: leave a trail of who changed what.
    AuditService.log(db=db, action=AuditAction.UPDATE, module="rbac", entity_id=str(role.id), entity_type="Role",
                     old_values={"form_codes": old_codes}, new_values={"form_codes": codes},
                     notes=f"Forms matrix changed for role '{role.name}'", user=current_user)
    return RoleFormMatrixRow(role_id=str(role.id), role_name=role.name, form_codes=codes)


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
    rows = []
    for role in _visible_roles(db, current_user):
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
    role = _role_or_404(db, role_id, current_user)

    _guard_platform_role(role, current_user)

    valid_codes = {p.code for p in db.query(Permission).all()}
    unknown = set(payload.permission_codes) - valid_codes
    if unknown:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown permission code(s): {', '.join(sorted(unknown))}",
        )

    old_codes = sorted(rp.permission.code for rp in role.role_permissions if rp.permission)
    db.query(RolePermission).filter(RolePermission.role_id == role.id).delete()
    db.flush()

    permissions_by_code = {p.code: p for p in db.query(Permission)
                            .filter(Permission.code.in_(payload.permission_codes)).all()}
    for code in payload.permission_codes:
        db.add(RolePermission(role_id=role.id, permission_id=permissions_by_code[code].id))

    db.commit()

    codes = sorted(payload.permission_codes)
    AuditService.log(db=db, action=AuditAction.UPDATE, module="rbac", entity_id=str(role.id), entity_type="Role",
                     old_values={"permission_codes": old_codes}, new_values={"permission_codes": codes},
                     notes=f"Permission matrix changed for role '{role.name}'", user=current_user)
    return RolePermissionMatrixRow(role_id=str(role.id), role_name=role.name, permission_codes=codes)
