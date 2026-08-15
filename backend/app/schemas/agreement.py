from typing import Optional
from uuid import UUID
from datetime import date
from decimal import Decimal
from app.schemas.common import TimestampSchema
from app.models.agreement_tracker import AgreementStatus


class AgreementOut(TimestampSchema):
    society_id:       UUID
    flat_id:          UUID
    tenant_id:        UUID
    start_date:       date
    end_date:         date
    status:           AgreementStatus
    monthly_rent:     Optional[Decimal]
    security_deposit: Optional[Decimal]
    document_url:     Optional[str]
    renewal_of_id:    Optional[UUID]
    termination_reason: Optional[str]
    alert_sent_30:    bool
    alert_sent_7:     bool
