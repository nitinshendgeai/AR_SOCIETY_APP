from uuid import UUID
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.dependencies import get_current_user, require_roles
from app.models.user import User
from app.services.society_service import SocietyService
from app.modules.onboarding.schemas.onboarding import (
    SelfRegistrationRequest, SelfRegistrationOut,
    TrialStatusOut, SetupProgressUpdate, AcceptTermsRequest,
)
from app.modules.onboarding.services.onboarding_service import OnboardingService

router = APIRouter(tags=["Onboarding & Trial"])

admin_or_committee = require_roles(
    "Admin", "Committee",
    "Society Admin", "Committee Chairman", "Committee Secretary", "Committee Treasurer",
)


# ── Public self-registration (no auth) ────────────────────────────────────────

@router.post("/public/register", status_code=201)
def self_register_society(
    data: SelfRegistrationRequest,
    db:   Session = Depends(get_db),
):
    """
    Public endpoint — self-service society registration with 30-day free trial.
    No authentication required.
    """
    return OnboardingService(db).self_register(data)


# ── Trial status ──────────────────────────────────────────────────────────────

@router.get("/societies/{society_id}/trial-status")
def get_trial_status(
    society_id:   UUID,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(get_current_user),
):
    """Get current trial/subscription status for a society."""
    society = SocietyService(db).get_or_404(society_id)
    return OnboardingService(db).get_trial_status(society)


# ── Setup wizard progress ─────────────────────────────────────────────────────

@router.patch("/societies/{society_id}/setup-progress")
def update_setup_progress(
    society_id:   UUID,
    data:         SetupProgressUpdate,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(admin_or_committee),
):
    """Update society setup wizard completion percentage."""
    society = SocietyService(db).get_or_404(society_id)
    return OnboardingService(db).update_setup_progress(
        society, data.setup_completion_percentage, data.setup_completed
    )


# ── Accept terms ──────────────────────────────────────────────────────────────

@router.post("/auth/accept-terms")
def accept_terms(
    data:         AcceptTermsRequest,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(get_current_user),
):
    """Mark terms as accepted for the current user."""
    return OnboardingService(db).accept_terms(current_user)
