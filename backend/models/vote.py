from sqlalchemy import (
    Column, Integer, String, DateTime, ForeignKey,
    UniqueConstraint, Index,
)
from sqlalchemy.orm import relationship
from datetime import datetime

from backend.database import Base


class Vote(Base):
    """
    Stores the actual vote.

    Identified mode  → user_id is set,        hashed_user_id is NULL
    Anonymous mode   → hashed_user_id is set,  user_id is NULL

    The hashed_user_id is an HMAC of (user_id, topic_id) so it cannot
    be reversed to reveal identity, but it is deterministic enough to
    prevent double-voting via VoteTracking.
    """
    __tablename__ = "votes"

    id = Column(Integer, primary_key=True, index=True)
    topic_id = Column(
        Integer, ForeignKey("topics.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    option_id = Column(
        Integer, ForeignKey("options.id", ondelete="RESTRICT"),
        nullable=False,
    )
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    hashed_user_id = Column(String(64), nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    topic = relationship("Topic", back_populates="votes")
    option = relationship("Option", back_populates="votes")
    user = relationship("User", back_populates="votes")

    def __repr__(self) -> str:
        return f"<Vote topic={self.topic_id} option={self.option_id}>"


class VoteTracking(Base):
    """
    Tracks who has voted per topic — WITHOUT storing identity in anonymous mode.
    The two UNIQUE constraints prevent double-voting for both voting modes.
    """
    __tablename__ = "vote_tracking"

    id = Column(Integer, primary_key=True, index=True)
    topic_id = Column(
        Integer, ForeignKey("topics.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    hashed_user_id = Column(String(64), nullable=True)
    voted_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    topic = relationship("Topic", back_populates="vote_trackings")
    user = relationship("User", back_populates="vote_trackings")

    __table_args__ = (
        # Identified mode: one vote per user per topic
        UniqueConstraint("topic_id", "user_id", name="uq_tracking_identified"),
        # Anonymous mode: one vote per hashed identity per topic
        UniqueConstraint("topic_id", "hashed_user_id", name="uq_tracking_anonymous"),
        Index("ix_tracking_topic_user", "topic_id", "user_id"),
        Index("ix_tracking_topic_hashed", "topic_id", "hashed_user_id"),
    )

    def __repr__(self) -> str:
        return f"<VoteTracking topic={self.topic_id}>"
