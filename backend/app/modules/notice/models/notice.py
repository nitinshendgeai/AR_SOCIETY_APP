"""
Notice & Communication Management Models — ERP communication architecture.

Workflows:
  Notice: DRAFT → PUBLISHED → EXPIRED/ARCHIVED
  Emergency Alert: TRIGGERED → ACKNOWLEDGED/RESOLVED
"""
import enum
from sqlalchemy import Column, String, Text, Boolean, DateTime, Date, Integer, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.db.base import Base, TimestampMixin


# ── Enums ─────────────────────────────────────────────────────────────────────

class NoticeCategory(str, enum.Enum):
    GENERAL         = "general"
    EMERGENCY       = "emergency"
    MAINTENANCE     = "maintenance"
    EVENTS          = "events"
    SECURITY        = "security"
    PARKING         = "parking"
    WATER_SHUTDOWN  = "water_shutdown"
    POWER_SHUTDOWN  = "power_shutdown"
    STAFF_NOTICE    = "staff_notice"
    FINANCE         = "finance"
    AMENITIES       = "amenities"


class NoticePriority(str, enum.Enum):
    LOW    = "low"
    NORMAL = "normal"
    HIGH   = "high"
    URGENT = "urgent"


class NoticeStatus(str, enum.Enum):
    DRAFT     = "draft"
    PUBLISHED = "published"
    EXPIRED   = "expired"
    ARCHIVED  = "archived"


class AudienceType(str, enum.Enum):
    ALL_RESIDENTS   = "all_residents"
    OWNERS_ONLY     = "owners_only"
    TENANTS_ONLY    = "tenants_only"
    SPECIFIC_WINGS  = "specific_wings"
    SPECIFIC_FLATS  = "specific_flats"
    ALL_STAFF       = "all_staff"
    SECURITY_TEAM   = "security_team"
    COMMITTEE       = "committee"
    ALL             = "all"


class AlertType(str, enum.Enum):
    FIRE             = "fire"
    WATER_LEAKAGE    = "water_leakage"
    LIFT_FAILURE     = "lift_failure"
    POWER_FAILURE    = "power_failure"
    SECURITY_THREAT  = "security_threat"
    MEDICAL          = "medical"
    EARTHQUAKE       = "earthquake"
    FLOOD            = "flood"
    GAS_LEAK         = "gas_leak"
    OTHER            = "other"


class AlertStatus(str, enum.Enum):
    ACTIVE   = "active"
    RESOLVED = "resolved"
    CANCELLED= "cancelled"


# ── Notice ────────────────────────────────────────────────────────────────────

class Notice(Base, TimestampMixin):
    __tablename__ = "notices"

    society_id           = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    created_by           = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    title                = Column(String(255), nullable=False)
    content              = Column(Text, nullable=False)
    category             = Column(Enum(NoticeCategory, values_callable=lambda e: [x.value for x in e]), nullable=False, index=True)
    priority             = Column(Enum(NoticePriority, values_callable=lambda e: [x.value for x in e]), default=NoticePriority.NORMAL, nullable=False, index=True)
    status               = Column(Enum(NoticeStatus, values_callable=lambda e: [x.value for x in e]), default=NoticeStatus.DRAFT, nullable=False, index=True)

    publish_date         = Column(DateTime, nullable=True)
    expiry_date          = Column(DateTime, nullable=True)
    acknowledgement_required = Column(Boolean, default=False, nullable=False)
    attachment_url       = Column(String(500), nullable=True)

    # Audience targeting
    audience_type        = Column(Enum(AudienceType, values_callable=lambda e: [x.value for x in e]), default=AudienceType.ALL_RESIDENTS, nullable=False, index=True)
    target_wing_ids      = Column(JSONB, nullable=True)   # list of wing UUIDs if SPECIFIC_WINGS
    target_flat_ids      = Column(JSONB, nullable=True)   # list of flat UUIDs if SPECIFIC_FLATS
    target_user_ids      = Column(JSONB, nullable=True)   # explicit user override

    # Metrics (denormalized for performance)
    total_audience       = Column(Integer, default=0, nullable=False)
    acknowledgement_count= Column(Integer, default=0, nullable=False)

    society         = relationship("Society")
    author          = relationship("User", foreign_keys=[created_by])
    acknowledgements = relationship("NoticeAcknowledgement", back_populates="notice", cascade="all, delete-orphan")
    comm_logs       = relationship("CommunicationLog",       back_populates="notice", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Notice {self.title!r} [{self.status}]>"


# ── NoticeAcknowledgement ─────────────────────────────────────────────────────

class NoticeAcknowledgement(Base, TimestampMixin):
    __tablename__ = "notice_acknowledgements"

    notice_id  = Column(UUID(as_uuid=True), ForeignKey("notices.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id    = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    flat_id    = Column(UUID(as_uuid=True), ForeignKey("flats.id", ondelete="SET NULL"), nullable=True)
    ack_at     = Column(DateTime, nullable=False)
    notes      = Column(Text, nullable=True)

    notice = relationship("Notice", back_populates="acknowledgements")
    user   = relationship("User", foreign_keys=[user_id])
    flat   = relationship("Flat")

    def __repr__(self):
        return f"<Ack notice={self.notice_id} user={self.user_id}>"


# ── Announcement (simpler, no acknowledgement needed) ─────────────────────────

class Announcement(Base, TimestampMixin):
    __tablename__ = "announcements"

    society_id   = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    created_by   = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    title        = Column(String(255), nullable=False)
    content      = Column(Text, nullable=False)
    category     = Column(Enum(NoticeCategory, values_callable=lambda e: [x.value for x in e]), nullable=False, index=True)
    priority     = Column(Enum(NoticePriority, values_callable=lambda e: [x.value for x in e]), default=NoticePriority.NORMAL, nullable=False)
    is_published = Column(Boolean, default=False, nullable=False, index=True)
    publish_date = Column(DateTime, nullable=True)
    expiry_date  = Column(DateTime, nullable=True)
    image_url    = Column(String(500), nullable=True)
    audience_type= Column(Enum(AudienceType, values_callable=lambda e: [x.value for x in e]), default=AudienceType.ALL, nullable=False)

    society = relationship("Society")
    author  = relationship("User", foreign_keys=[created_by])


# ── CommunicationLog (delivery tracking) ─────────────────────────────────────

class CommunicationLog(Base, TimestampMixin):
    __tablename__ = "communication_logs"

    society_id   = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    notice_id    = Column(UUID(as_uuid=True), ForeignKey("notices.id", ondelete="SET NULL"), nullable=True, index=True)
    user_id      = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    channel      = Column(String(30), nullable=False)   # in_app, sms, email, push, whatsapp
    status       = Column(String(30), nullable=False)   # sent, failed, delivered, read
    sent_at      = Column(DateTime, nullable=False)
    error_msg    = Column(Text, nullable=True)

    society = relationship("Society")
    notice  = relationship("Notice", back_populates="comm_logs")
    user    = relationship("User", foreign_keys=[user_id])


# ── EmergencyAlert ────────────────────────────────────────────────────────────

class EmergencyAlert(Base, TimestampMixin):
    __tablename__ = "emergency_alerts"

    society_id   = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    triggered_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    resolved_by  = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    alert_type   = Column(Enum(AlertType, values_callable=lambda e: [x.value for x in e]), nullable=False, index=True)
    status       = Column(Enum(AlertStatus, values_callable=lambda e: [x.value for x in e]), default=AlertStatus.ACTIVE, nullable=False, index=True)
    title        = Column(String(255), nullable=False)
    description  = Column(Text, nullable=True)
    location     = Column(String(255), nullable=True)
    triggered_at = Column(DateTime, nullable=False)
    resolved_at  = Column(DateTime, nullable=True)
    resolution_notes = Column(Text, nullable=True)

    # Channel readiness (future: push, SMS, WhatsApp)
    notify_all_residents = Column(Boolean, default=True, nullable=False)
    notify_security      = Column(Boolean, default=True, nullable=False)
    notify_committee     = Column(Boolean, default=True, nullable=False)
    push_sent            = Column(Boolean, default=False, nullable=False)
    sms_sent             = Column(Boolean, default=False, nullable=False)
    whatsapp_sent        = Column(Boolean, default=False, nullable=False)

    society   = relationship("Society")
    triggerer = relationship("User", foreign_keys=[triggered_by])
    resolver  = relationship("User", foreign_keys=[resolved_by])

    def __repr__(self):
        return f"<EmergencyAlert {self.alert_type} [{self.status}]>"
