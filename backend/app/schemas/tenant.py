from typing import Optional, List
from uuid import UUID
from datetime import date
from decimal import Decimal
from pydantic import model_validator, field_validator
from app.schemas.common import OrmBase, TimestampSchema
from app.models.tenant import PoliceVerificationStatus
from app.utils.phone import validate_mobile_number


class TenantCreate(OrmBase):
    # No society_id — scope is always derived from flat_id -> wing -> society,
    # never trusted from the client (mirrors ResidentCreate, Phase M1.2).
    flat_id:          UUID
    full_name:        str
    phone:            Optional[str] = None
    email:            Optional[str] = None
    agreement_start_date: Optional[date] = None
    agreement_end_date:   Optional[date] = None
    monthly_rent:     Optional[Decimal] = None
    security_deposit: Optional[Decimal] = None
    agreement_doc_url: Optional[str] = None
    id_proof_type:    Optional[str] = None
    id_proof_number:  Optional[str] = None
    kyc_verified:     bool = False
    kyc_doc_url:      Optional[str] = None
    police_verification_status: Optional[PoliceVerificationStatus] = PoliceVerificationStatus.PENDING
    police_verification_date:   Optional[date] = None
    emergency_contact_name:  Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    remarks:          Optional[str] = None
    user_id:          Optional[UUID] = None
    # If supplied, TenantService.create() delegates to the existing
    # OccupancyService.tenant_move_in() instead of re-implementing
    # occupancy-transition/agreement-creation logic.
    move_in_date:     Optional[date] = None

    @field_validator("monthly_rent", "security_deposit")
    @classmethod
    def non_negative(cls, v):
        if v is not None and v < 0:
            raise ValueError("must not be negative")
        return v

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v):
        return validate_mobile_number(v)

    @model_validator(mode="after")
    def check_agreement_dates(self):
        start, end = self.agreement_start_date, self.agreement_end_date
        if (start is None) != (end is None):
            raise ValueError("agreement_start_date and agreement_end_date must be supplied together")
        if start is not None and end is not None and end <= start:
            raise ValueError("agreement_end_date must be after agreement_start_date")
        return self


class TenantUpdate(OrmBase):
    # Deliberately excludes: flat_id (immutable, matching Resident — a
    # tenancy "move" is modeled as move-out + a new Tenant row), society_id
    # (doesn't exist on this entity), move_in_date/move_out_date (owned by
    # the Occupancy move-in/move-out endpoints), and
    # agreement_start_date/agreement_end_date/monthly_rent/security_deposit
    # (owned by the renewal endpoint — see AgreementRenewalRequest below —
    # since those fields must stay in sync with the tenant's current ACTIVE
    # AgreementTracker row; a generic PATCH editing them directly would
    # recreate the exact dual-source-of-truth bug this phase just fixed for
    # Flat.occupancy_status).
    full_name:        Optional[str] = None
    phone:            Optional[str] = None
    email:            Optional[str] = None
    agreement_doc_url: Optional[str] = None
    id_proof_type:    Optional[str] = None
    id_proof_number:  Optional[str] = None
    kyc_verified:     Optional[bool] = None
    kyc_doc_url:      Optional[str] = None
    police_verification_status: Optional[PoliceVerificationStatus] = None
    police_verification_date:   Optional[date] = None
    emergency_contact_name:  Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    remarks:          Optional[str] = None
    user_id:          Optional[UUID] = None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v):
        return validate_mobile_number(v)


class TenantOut(TimestampSchema):
    flat_id:          UUID
    user_id:          Optional[UUID]
    full_name:        str
    phone:            Optional[str]
    email:            Optional[str]
    agreement_start_date: Optional[date]
    agreement_end_date:   Optional[date]
    monthly_rent:     Optional[Decimal]
    security_deposit: Optional[Decimal]
    agreement_doc_url: Optional[str]
    id_proof_type:    Optional[str]
    id_proof_number:  Optional[str]
    kyc_verified:     bool
    kyc_doc_url:      Optional[str]
    police_verification_status: Optional[PoliceVerificationStatus]
    police_verification_date:   Optional[date]
    emergency_contact_name:  Optional[str]
    emergency_contact_phone: Optional[str]
    move_in_date:     Optional[date]
    move_out_date:    Optional[date]
    remarks:          Optional[str]
    # Convenience — the id of the tenant's current ACTIVE AgreementTracker
    # row, if any. Populated by TenantService, not stored on Tenant itself.
    active_agreement_id: Optional[UUID] = None


class TenantCreateOut(TenantOut):
    """Response for POST /tenants only — carries non-blocking duplicate
    warnings (mirrors ResidentCreateOut, Phase M1.2 §10)."""
    warnings: List[str] = []


class AgreementRenewalRequest(OrmBase):
    start_date: date
    end_date:   date
    monthly_rent:     Optional[Decimal] = None
    security_deposit: Optional[Decimal] = None
    document_url:     Optional[str] = None

    @model_validator(mode="after")
    def check_dates(self):
        if self.end_date <= self.start_date:
            raise ValueError("end_date must be after start_date")
        return self
