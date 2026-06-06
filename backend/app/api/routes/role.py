from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List, Optional

from app.db.session import get_db
from app.models.role import Role
from app.core.dependencies import get_current_user
from pydantic import BaseModel


class RoleListItem(BaseModel):
    id:          str
    name:        str
    description: Optional[str] = None

    model_config = {"from_attributes": True}


router = APIRouter(prefix="/roles", tags=["Roles"])


@router.get("/", response_model=List[RoleListItem],
            dependencies=[Depends(get_current_user)])
def list_roles(db: Session = Depends(get_db)):
    roles = db.query(Role).order_by(Role.name).all()
    return [RoleListItem(id=str(r.id), name=r.name, description=r.description)
            for r in roles]
