from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_any_member
from app.db.session import get_db
from app.models.user import User
from app.modules.assistant import service
from app.modules.assistant.schemas import (
    AskRequest, AskResponse, DiagnosticsRequest, DiagnosticsResponse, StatusResponse,
)

# Authentication, the suspended-society and no-society gates run inside get_current_user for every call here. The
# assistant is a core feature (it has no entry in the optional services catalogue); what it may check about a society
# is gated per topic in the service. Nothing in these handlers writes: see service.py and diagnostics.py.
router = APIRouter(prefix="/assistant", tags=["Help Assistant"], dependencies=[Depends(require_any_member)])


def _headers(response: Response, request_id: str) -> None:
    response.headers["X-Request-ID"] = request_id
    response.headers["Cache-Control"] = "no-store"


@router.get("/status", response_model=StatusResponse)
def assistant_status(response: Response, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rid = service.new_request_id()
    _headers(response, rid)
    return service.status(db, user, rid)


@router.post("/ask", response_model=AskResponse)
def ask(data: AskRequest, response: Response, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rid = service.new_request_id()
    _headers(response, rid)
    return service.ask(db, user, data, rid)


@router.post("/diagnostics", response_model=DiagnosticsResponse)
def diagnostics(data: DiagnosticsRequest, response: Response, db: Session = Depends(get_db),
                user: User = Depends(get_current_user)):
    """Read-only configuration checks (counts and yes/no findings). A POST only because it takes a body; it changes
    nothing."""
    rid = service.new_request_id()
    _headers(response, rid)
    return service.diagnose(db, user, data, rid)
