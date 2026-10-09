"""Meetings and minutes, polls, and the society's documents."""
from sqlalchemy import (Boolean, Column, Date, DateTime, ForeignKey, Integer, LargeBinary, String, Text, Time,
                        UniqueConstraint)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import Base, TimestampMixin

MEETING_TYPES = ("agm", "sgm", "committee", "other")
MEETING_STATUSES = ("scheduled", "held", "cancelled")
RESOLUTION_OUTCOMES = ("carried", "rejected", "deferred")
DOCUMENT_CATEGORIES = ("bylaws", "minutes", "audit", "insurance", "agreement", "notice", "other")
DOCUMENT_VISIBILITY = ("everyone", "committee")


class Meeting(Base, TimestampMixin):
    __tablename__ = "meetings"

    society_id = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    meeting_type = Column(String(20), nullable=False, default="committee")
    meeting_date = Column(Date, nullable=False, index=True)
    start_time = Column(Time, nullable=True)
    venue = Column(String(200), nullable=True)
    agenda = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default="scheduled", index=True)
    minutes = Column(Text, nullable=True)
    minutes_published = Column(Boolean, nullable=False, default=False)
    minutes_published_on = Column(Date, nullable=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    attendees = relationship("MeetingAttendee", cascade="all, delete-orphan", order_by="MeetingAttendee.name")
    resolutions = relationship("MeetingResolution", cascade="all, delete-orphan", order_by="MeetingResolution.number")


class MeetingAttendee(Base, TimestampMixin):
    __tablename__ = "meeting_attendees"

    meeting_id = Column(UUID(as_uuid=True), ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    flat_label = Column(String(60), nullable=True)
    designation = Column(String(60), nullable=True)
    present = Column(Boolean, nullable=False, default=True)


class MeetingResolution(Base, TimestampMixin):
    __tablename__ = "meeting_resolutions"

    meeting_id = Column(UUID(as_uuid=True), ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False, index=True)
    number = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    proposed_by = Column(String(120), nullable=True)
    seconded_by = Column(String(120), nullable=True)
    outcome = Column(String(20), nullable=False, default="carried")


class Poll(Base, TimestampMixin):
    __tablename__ = "polls"

    society_id = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    question = Column(String(300), nullable=False)
    description = Column(Text, nullable=True)
    closes_on = Column(Date, nullable=False)
    closed_early = Column(Boolean, nullable=False, default=False)
    results_after = Column(String(10), nullable=False, default="vote")      # vote | close
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    options = relationship("PollOption", cascade="all, delete-orphan", order_by="PollOption.position")


class PollOption(Base, TimestampMixin):
    __tablename__ = "poll_options"

    poll_id = Column(UUID(as_uuid=True), ForeignKey("polls.id", ondelete="CASCADE"), nullable=False, index=True)
    label = Column(String(200), nullable=False)
    position = Column(Integer, nullable=False, default=0)


class PollVote(Base, TimestampMixin):
    """One vote per flat per poll. The vote records the flat and the person who cast it, but the
    screens only ever show totals."""
    __tablename__ = "poll_votes"
    __table_args__ = (UniqueConstraint("poll_id", "flat_id", name="uq_poll_vote_flat"),)

    poll_id = Column(UUID(as_uuid=True), ForeignKey("polls.id", ondelete="CASCADE"), nullable=False, index=True)
    option_id = Column(UUID(as_uuid=True), ForeignKey("poll_options.id", ondelete="CASCADE"), nullable=False)
    flat_id = Column(UUID(as_uuid=True), ForeignKey("flats.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    voted_at = Column(DateTime, nullable=False)


class SocietyDocument(Base, TimestampMixin):
    __tablename__ = "society_documents"

    society_id = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    category = Column(String(20), nullable=False, default="other", index=True)
    description = Column(Text, nullable=True)
    visibility = Column(String(12), nullable=False, default="everyone")
    file_name = Column(String(255), nullable=False)
    mime_type = Column(String(100), nullable=False)
    size_bytes = Column(Integer, nullable=False)
    data = Column(LargeBinary, nullable=False)
    uploaded_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
