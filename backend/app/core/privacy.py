"""Field-level privacy for records every member of a society may look up.

The resident and tenant registers are readable by any member (a neighbour's name and flat), but a member must not see
another person's identity documents, date of birth, emergency contacts, rent or deposit. The office (manager and above)
sees everything, and so does a person looking at their own record.
"""
from typing import Iterable

from pydantic import BaseModel

from app.core.dependencies import _user_has_permission
from app.models.user import User

RESIDENT_PRIVATE_FIELDS = (
    "date_of_birth", "id_proof_type", "id_proof_number", "kyc_doc_url",
    "emergency_contact_name", "emergency_contact_phone",
)
TENANT_PRIVATE_FIELDS = (
    "monthly_rent", "security_deposit", "agreement_doc_url", "id_proof_type", "id_proof_number", "kyc_doc_url",
    "police_verification_status", "police_verification_date", "emergency_contact_name", "emergency_contact_phone",
    "remarks",
)


def hide_private(item: BaseModel, user: User, fields: Iterable[str]) -> BaseModel:
    """`item` with the private `fields` emptied, unless `user` is the office or the person it describes."""
    if _user_has_permission(user, "manager_above"):
        return item
    owner = getattr(item, "user_id", None)
    if owner is not None and str(owner) == str(user.id):
        return item
    return item.model_copy(update={f: None for f in fields if hasattr(item, f)})
