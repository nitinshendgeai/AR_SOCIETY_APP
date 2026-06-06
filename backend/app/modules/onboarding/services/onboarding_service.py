"""
OnboardingService — self-service society registration with trial creation.

Extends the existing SocietySetupService to support:
- Public self-registration (no admin required)
- Trial account creation
- Extended default roles (13 roles)
- Extended default users (admin, chairman, secretary, treasurer)
"""
import re
from datetime import date, timedelta
from typing import Tuple
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models.society import Society, AccountStatus
from app.models.role import Role
from app.models.user import User, UserRole, UserStatus
from app.models.audit_log import AuditAction
from app.core.security import hash_password
from app.services.audit_service import AuditService
from app.modules.onboarding.schemas.onboarding import SelfRegistrationRequest

TRIAL_DAYS = 30

# Fixed password used for ALL system-generated onboarding accounts.
# Users are forced to change this on first login (must_change_password=True).
STANDARD_ONBOARDING_PASSWORD = "Admin@1234"

# 14 default roles for self-registered societies
EXTENDED_DEFAULT_ROLES = [
    ("Platform Admin",          "AR Society internal cross-society management"),
    ("Society Admin",           "Full society-level administration"),
    ("Committee Chairman",      "Head of resident welfare committee"),
    ("Committee Secretary",     "Society secretary and record keeper"),
    ("Committee Treasurer",     "Society treasurer and finance"),
    ("Committee Member",        "General committee member"),
    ("Security Supervisor",     "Supervises security staff and gate operations"),
    ("Housekeeping Supervisor", "Supervises housekeeping and cleaning staff"),
    ("Technical Supervisor",    "Supervises maintenance and technical staff"),
    ("Security Staff",          "Gate security and patrol operations"),
    ("Housekeeping Staff",      "Cleaning and housekeeping operations"),
    ("Technical Staff",         "Electrical, plumbing, and maintenance work"),
    ("Resident",                "Flat owner or permanent occupant"),
    ("Tenant",                  "Rented flat occupant"),
]

# RBAC group mapping for require_roles() dependency
ROLE_RBAC_GROUP = {
    "Society Admin":           "Admin",
    "Committee Chairman":      "Committee",
    "Committee Secretary":     "Committee",
    "Committee Treasurer":     "Committee",
    "Committee Member":        "Committee",
    "Security Supervisor":     "Security",
    "Security Staff":          "Security",
    "Housekeeping Supervisor": "Staff",
    "Housekeeping Staff":      "Staff",
    "Technical Supervisor":    "Staff",
    "Technical Staff":         "Staff",
    "Resident":                "Resident",
    "Tenant":                  "Resident",
}

# 9 default users created for every new society.
# Email pattern: {prefix}@{society_code_lowercase}.com
# All share STANDARD_ONBOARDING_PASSWORD and must_change_password=True.
DEFAULT_USER_CONFIGS = [
    {"prefix": "admin",        "name_suffix": "Admin",                 "role": "Society Admin"},
    {"prefix": "chairman",     "name_suffix": "Chairman",              "role": "Committee Chairman"},
    {"prefix": "secretary",    "name_suffix": "Secretary",             "role": "Committee Secretary"},
    {"prefix": "treasurer",    "name_suffix": "Treasurer",             "role": "Committee Treasurer"},
    {"prefix": "committee",    "name_suffix": "Committee Member",      "role": "Committee Member"},
    {"prefix": "security",     "name_suffix": "Security Supervisor",   "role": "Security Supervisor"},
    {"prefix": "housekeeping", "name_suffix": "Housekeeping Supervisor","role": "Housekeeping Supervisor"},
    {"prefix": "technical",    "name_suffix": "Technical Supervisor",  "role": "Technical Supervisor"},
    {"prefix": "resident",     "name_suffix": "Resident",              "role": "Resident"},
]


class OnboardingService:

    def __init__(self, db: Session):
        self.db = db

    # ── Public self-registration ───────────────────────────────────────────────

    def self_register(self, data: SelfRegistrationRequest) -> dict:
        """
        Full self-service registration in one transaction.
        Returns society + credentials.
        """
        self._validate_uniqueness(data)

        society = self._create_society(data)
        roles   = self._create_extended_roles()
        users, creds = self._create_default_users(society, roles)

        # Commit society, roles, and users FIRST so they are persisted regardless
        # of whether the audit log write succeeds.  AuditService.log() internally
        # calls db.commit() and, on failure, db.rollback() — if the audit were
        # called while these objects were still unflushed, a rollback would wipe
        # the society and users while the route still returned credentials (→ 401).
        self.db.commit()

        days_remaining = (society.trial_end_date - date.today()).days

        AuditService.log(
            db=self.db, action=AuditAction.CREATE,
            module="onboarding", entity_id=str(society.id),
            entity_type="Society", user=None,
            new_values={
                "event":         "society_self_registered",
                "society":       society.name,
                "society_code":  society.society_code,
                "contact_email": data.contact_email,
                "trial_end":     str(society.trial_end_date),
                "roles_created": len(roles),
                "users_created": len(users),
            },
        )

        return {
            "society_id":     str(society.id),
            "society_name":   society.name,
            "society_code":   society.society_code,
            "trial_end_date": str(society.trial_end_date),
            "trial_days":     days_remaining,
            "credentials":    creds,
            "message":        "Society registered successfully. Your 30-day free trial starts now.",
        }

    # ── Trial status ──────────────────────────────────────────────────────────

    def get_trial_status(self, society: Society) -> dict:
        today = date.today()

        # Lazy expiry: update status if trial has ended
        if (society.account_status == AccountStatus.TRIAL
                and society.trial_end_date
                and today > society.trial_end_date):
            society.account_status = AccountStatus.EXPIRED
            self.db.commit()

        days_remaining = 0
        trial_expired  = False
        if society.trial_end_date:
            remaining = (society.trial_end_date - today).days
            days_remaining = max(0, remaining)
            trial_expired  = remaining < 0

        return {
            "account_status":              society.account_status.value,
            "is_trial":                    society.is_trial,
            "trial_start_date":            str(society.trial_start_date) if society.trial_start_date else None,
            "trial_end_date":              str(society.trial_end_date) if society.trial_end_date else None,
            "trial_days_remaining":        days_remaining,
            "trial_expired":               trial_expired,
            "expiry_warning":              0 < days_remaining <= 7,
            "expiry_critical":             0 < days_remaining <= 3,
            "subscription_plan":           society.subscription_plan,
            "subscription_status":         society.subscription_status,
            "setup_completed":             society.setup_completed,
            "setup_completion_percentage": society.setup_completion_percentage,
        }

    # ── Setup wizard progress ─────────────────────────────────────────────────

    def update_setup_progress(self, society: Society, pct: int, completed: bool) -> dict:
        society.setup_completion_percentage = pct
        if completed:
            society.setup_completed = True
            society.setup_completion_percentage = 100
        self.db.commit()
        return {"setup_completed": society.setup_completed,
                "setup_completion_percentage": society.setup_completion_percentage}

    # ── Accept terms ──────────────────────────────────────────────────────────

    def accept_terms(self, user: User) -> dict:
        user.terms_accepted = True
        self.db.commit()
        return {"terms_accepted": True, "message": "Terms accepted successfully"}

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _validate_uniqueness(self, data: SelfRegistrationRequest):
        errors = []
        if self.db.query(Society).filter(Society.name == data.society_name).first():
            errors.append("Society name is already registered")
        if self.db.query(Society).filter(Society.society_code == data.society_code).first():
            errors.append("Society code is already taken")
        if (self.db.query(User).filter(User.email == data.contact_email).first()
                or self.db.query(Society).filter(Society.contact_email == data.contact_email).first()):
            errors.append("Email address is already registered")
        if (self.db.query(User).filter(User.phone == data.contact_mobile).first()
                or self.db.query(Society).filter(Society.contact_phone == data.contact_mobile).first()):
            errors.append("Mobile number is already registered")
        if errors:
            raise HTTPException(status_code=409, detail="; ".join(errors))

    def _create_society(self, data: SelfRegistrationRequest) -> Society:
        today = date.today()
        society = Society(
            name                = data.society_name,
            society_code        = data.society_code,
            city                = data.city,
            state               = data.state,
            country             = data.country,
            contact_email       = data.contact_email,
            contact_phone       = data.contact_mobile,
            contact_person_name = data.contact_person_name,
            total_wings         = data.total_wings,
            total_flats         = data.total_flats,
            account_status      = AccountStatus.TRIAL,
            is_trial            = True,
            trial_start_date    = today,
            trial_end_date      = today + timedelta(days=TRIAL_DAYS),
            allowed_users       = 50,
            allowed_flats       = max(data.total_flats, 100),
            allowed_storage_mb  = 1024,
            setup_completed     = False,
            setup_completion_percentage = 0,
        )
        self.db.add(society)
        self.db.flush()
        return society

    def _create_extended_roles(self) -> list:
        created = []
        for name, description in EXTENDED_DEFAULT_ROLES:
            r = self.db.query(Role).filter(Role.name == name).first()
            if not r:
                r = Role(name=name, description=description)
                self.db.add(r)
                self.db.flush()
            created.append(r)
        return created

    def _create_default_users(self, society: Society,
                               roles: list) -> Tuple[list, list]:
        code     = society.society_code.lower()
        role_map = {r.name: r for r in roles}
        pwd_hash = hash_password(STANDARD_ONBOARDING_PASSWORD)

        created_users, credentials = [], []

        for cfg in DEFAULT_USER_CONFIGS:
            email     = f"{cfg['prefix']}@{code}.com"
            full_name = f"{society.name} {cfg['name_suffix']}"

            if self.db.query(User).filter(User.email == email).first():
                continue  # idempotent: skip if already exists

            user = User(
                society_id           = society.id,
                email                = email,
                full_name            = full_name,
                hashed_password      = pwd_hash,
                status               = UserStatus.ACTIVE,
                must_change_password = True,
                terms_accepted       = False,
                setup_completed      = False,
            )
            self.db.add(user)
            self.db.flush()

            role = role_map.get(cfg["role"])
            if role:
                self.db.add(UserRole(user_id=user.id, role_id=role.id))

            created_users.append(user)
            credentials.append({
                "role":     cfg["role"],
                "email":    email,
                "password": STANDARD_ONBOARDING_PASSWORD,
            })

        return created_users, credentials
