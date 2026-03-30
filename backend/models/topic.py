import enum

from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, Enum, ForeignKey, Table
from sqlalchemy.orm import relationship
from datetime import datetime

from backend.database import Base


# ─── Association table: topic ↔ election observer ────────────────────────────
# An observer is an approved resident appointed by the admin to view full
# results.  No extra columns are needed so a plain Table is used instead of a
# full ORM model.
topic_observers = Table(
    "topic_observers",
    Base.metadata,
    Column(
        "topic_id",
        Integer,
        ForeignKey("topics.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "user_id",
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class VotingMode(str, enum.Enum):
    ANONYMOUS = "anonymous"
    IDENTIFIED = "identified"


class TopicStatus(str, enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    CLOSED = "closed"
    DISABLED = "disabled"


class Topic(Base):
    __tablename__ = "topics"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    mode = Column(Enum(VotingMode), nullable=False)
    status = Column(Enum(TopicStatus), default=TopicStatus.DRAFT, nullable=False)
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    options = relationship(
        "Option", back_populates="topic",
        cascade="all, delete-orphan",
        order_by="Option.order",
    )
    votes = relationship("Vote", back_populates="topic", lazy="select")
    vote_trackings = relationship("VoteTracking", back_populates="topic", lazy="select")
    # Users appointed by admin as election observers who can see full results
    observers = relationship(
        "User",
        secondary=topic_observers,
        lazy="select",
    )

    def __repr__(self) -> str:
        return f"<Topic id={self.id} title={self.title!r} status={self.status}>"


class Option(Base):
    __tablename__ = "options"

    id = Column(Integer, primary_key=True, index=True)
    topic_id = Column(
        Integer, ForeignKey("topics.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    text = Column(String(500), nullable=False)
    order = Column(Integer, default=0, nullable=False)

    # Relationships
    topic = relationship("Topic", back_populates="options")
    votes = relationship("Vote", back_populates="option", lazy="select")

    def __repr__(self) -> str:
        return f"<Option id={self.id} text={self.text!r}>"
