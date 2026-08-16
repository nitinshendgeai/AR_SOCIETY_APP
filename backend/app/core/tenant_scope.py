"""
Shared tenant-scoping helpers.

Role checks (require_admin, require_committee, ...) answer "is this caller
allowed to do this kind of thing at all" — they never answer "does this
specific resource belong to the caller's own society". Historically almost
every Society/Wing/Floor/Flat/Occupancy/Vehicle endpoint in this codebase
only did the former, which let an admin/committee member of one society
read or mutate another society's data by guessing/enumerating a UUID.

Every service method that reads, updates, deletes, or creates a
society-owned resource should route its ownership check through these
helpers rather than re-implementing the comparison ad hoc.

Convention (matches the pre-existing UserRepository/UserService pattern):
a caller's `society_id` of None means "platform admin — no tenant filter";
a caller's `society_id` set means every operation must be confined to it.
"""
from typing import Optional
from uuid import UUID
from fastapi import HTTPException, status
from app.models.user import User


def assert_society_access(current_user: User, target_society_id: Optional[UUID]) -> None:
    """Raise 403 if a society-scoped caller is trying to read/act on a
    different society than their own. Platform admins (current_user.society_id
    is None) may access any society."""
    if current_user.society_id is not None and current_user.society_id != target_society_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this society",
        )


def resolve_create_society_id(current_user: User, requested_society_id: Optional[UUID]) -> UUID:
    """Resolve the society_id a new resource should be created under.

    - Society-scoped callers: must create within their own society. A
      request that explicitly names a different society is rejected
      outright (silently overriding it would hide the attempt).
    - Platform admins: must supply a target society_id explicitly.
    """
    if current_user.society_id is not None:
        if requested_society_id is not None and requested_society_id != current_user.society_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot create resources for another society",
            )
        return current_user.society_id
    if requested_society_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="society_id is required",
        )
    return requested_society_id
