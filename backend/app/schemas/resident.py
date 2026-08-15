from typing import Optional, List
from uuid import UUID
from datetime import date
from pydantic import model_validator
from app.schemas.common import OrmBase, TimestampSchema
from app.models.resident import ResidentType, CommunicationPreference

_PRIMARY_ALLOWED_TYPES = (ResidentType.OWNER, ResidentType.CO_OWNER)


class ResidentCreate(OrmBase):
    # No society_id — scope is always derived from flat_id -> wing -> society,
    # never trusted from the client (see app/core/tenant_scope.py and
    # ResidentService.create()).
    flat_id:          UUID
    full_name:        str
    resident_type:    ResidentType = ResidentType.OWNER
    is_primary:       bool = False
    phone:            Optional[str] = None
    email:            Optional[str] = None
    date_of_birth:    Optional[date] = None
    id_proof_type:    Optional[str] = None
    id_proof_number:  Optional[str] = None
    kyc_verified:     bool = False
    kyc_doc_url:      Optional[str] = None
    emergency_contact_name:  Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    comm_preference:  Optional[CommunicationPreference] = CommunicationPreference.APP_ONLY
    photo_url:        Optional[str] = None
    user_id:          Optional[UUID] = None
    # If supplied, ResidentService.create() delegates to the existing
    # OccupancyService.resident_move_in() instead of re-implementing
    # occupancy-transition logic (audit log, OccupancyLog entry,
    # Flat.occupancy_status update all already exist there).
    move_in_date:     Optional[date] = None

    @model_validator(mode="after")
    def check_primary_type(self):
        if self.is_primary and self.resident_type not in _PRIMARY_ALLOWED_TYPES:
            raise ValueError(
                "A primary resident must be OWNER or CO_OWNER "
                f"(got resident_type={self.resident_type.value})"
            )
        return self


class ResidentUpdate(OrmBase):
    # Deliberately excludes: flat_id (immutable — see Phase M1.1 §5, a "move"
    # is modeled as move-out + a new Resident row, not an in-place flat
    # change), society_id (doesn't exist on this entity), family_member_count
    # (computed on read, never client-settable — see ResidentOut), and
    # move_in_date/move_out_date (owned by the Occupancy move-in/move-out
    # endpoints, not a generic edit).
    full_name:        Optional[str] = None
    resident_type:    Optional[ResidentType] = None
    is_primary:       Optional[bool] = None
    phone:            Optional[str] = None
    email:            Optional[str] = None
    date_of_birth:    Optional[date] = None
    id_proof_type:    Optional[str] = None
    id_proof_number:  Optional[str] = None
    kyc_verified:     Optional[bool] = None
    kyc_doc_url:      Optional[str] = None
    emergency_contact_name:  Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    comm_preference:  Optional[CommunicationPreference] = None
    photo_url:        Optional[str] = None
    user_id:          Optional[UUID] = None

    @model_validator(mode="after")
    def check_primary_type_if_both_given(self):
        # Only catches the case where a single PATCH sets both fields
        # inconsistently; the authoritative check (merging against the
        # existing DB row) happens in ResidentService.update() since a
        # partial update might only touch one of the two fields.
        if self.is_primary is True and self.resident_type is not None \
                and self.resident_type not in _PRIMARY_ALLOWED_TYPES:
            raise ValueError(
                "A primary resident must be OWNER or CO_OWNER "
                f"(got resident_type={self.resident_type.value})"
            )
        return self


class ResidentOut(TimestampSchema):
    flat_id:          UUID
    user_id:          Optional[UUID]
    full_name:        str
    resident_type:    ResidentType
    is_primary:       bool
    phone:            Optional[str]
    email:            Optional[str]
    date_of_birth:    Optional[date]
    move_in_date:     Optional[date]
    move_out_date:    Optional[date]
    id_proof_type:    Optional[str]
    id_proof_number:  Optional[str]
    kyc_verified:     bool
    kyc_doc_url:      Optional[str]
    emergency_contact_name:  Optional[str]
    emergency_contact_phone: Optional[str]
    comm_preference:  Optional[CommunicationPreference]
    photo_url:        Optional[str]
    # Computed by ResidentService on read — COUNT of active FAMILY/DEPENDENT
    # residents on the same flat_id. Never sourced from the (legacy, dead)
    # residents.family_member_count column directly.
    family_member_count: int = 0


class ResidentCreateOut(ResidentOut):
    """Response for POST /residents only — carries non-blocking duplicate
    warnings (Phase M1.1 §10) alongside the created record. GET/PATCH use
    the plain ResidentOut with no warnings field."""
    warnings: List[str] = []
