"""
Voting service — vote casting (two-phase: initiate → cast with OTP) and results.

Privacy design:
  - Identified mode: user_id stored in vote_tracking and votes tables.
  - Anonymous mode:  hashed_user_id = HMAC-SHA256(user_id:topic_id, ANON_VOTE_SALT)
    → deterministic so double-voting is caught, but not reversible.
"""
import hashlib
import hmac
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import and_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.config import settings
from backend.models.topic import Topic, Option, TopicStatus, VotingMode
from backend.models.user import User, UserStatus
from backend.models.vote import Vote, VoteTracking
from backend.services.audit_service import AuditService

logger = logging.getLogger(__name__)


class VotingService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self._audit = AuditService(db)

    # ── Private helpers ──────────────────────────────────────────────────────

    def _anon_hash(self, user_id: int, topic_id: int) -> str:
        """Non-reversible, deterministic identity hash for anonymous voting."""
        key = settings.ANON_VOTE_SALT.encode()
        msg = f"{user_id}:{topic_id}".encode()
        return hmac.new(key, msg, hashlib.sha256).hexdigest()

    def _is_within_window(self, topic: Topic) -> tuple[bool, str]:
        now = datetime.utcnow()
        if topic.start_time and topic.start_time > now:
            return False, "Voting has not started yet."
        if topic.end_time and topic.end_time < now:
            return False, "Voting period has ended."
        return True, ""

    # ── Read ─────────────────────────────────────────────────────────────────

    def get_active_topics(self) -> list:
        now = datetime.utcnow()
        topics = (
            self.db.query(Topic)
            .filter(Topic.status == TopicStatus.ACTIVE)
            .order_by(Topic.created_at.desc())
            .all()
        )
        return [
            t for t in topics
            if (not t.start_time or t.start_time <= now)
            and (not t.end_time or t.end_time >= now)
        ]

    def get_topic(self, topic_id: int) -> Optional[Topic]:
        return self.db.query(Topic).filter(Topic.id == topic_id).first()

    def has_voted(self, user: User, topic_id: int) -> bool:
        topic = self.get_topic(topic_id)
        if not topic:
            return False

        if topic.mode == VotingMode.ANONYMOUS:
            h = self._anon_hash(user.id, topic_id)
            return (
                self.db.query(VoteTracking)
                .filter(
                    and_(
                        VoteTracking.topic_id == topic_id,
                        VoteTracking.hashed_user_id == h,
                    )
                )
                .first()
                is not None
            )
        else:
            return (
                self.db.query(VoteTracking)
                .filter(
                    and_(
                        VoteTracking.topic_id == topic_id,
                        VoteTracking.user_id == user.id,
                    )
                )
                .first()
                is not None
            )

    # ── Write ─────────────────────────────────────────────────────────────────

    def cast_vote(
        self,
        user: User,
        topic_id: int,
        option_id: int,
        ip_address: Optional[str] = None,
    ) -> dict:
        """
        Atomically record vote + tracking entry.
        Called ONLY after OTP is verified.
        """
        if user.status != UserStatus.APPROVED or not user.is_active:
            return {"success": False, "message": "Account not authorised to vote."}

        topic = self.get_topic(topic_id)
        if not topic:
            return {"success": False, "message": "Voting topic not found."}

        if topic.status != TopicStatus.ACTIVE:
            return {"success": False, "message": "This voting topic is not currently active."}

        ok, msg = self._is_within_window(topic)
        if not ok:
            return {"success": False, "message": msg}

        # Validate option belongs to this topic
        option = (
            self.db.query(Option)
            .filter(and_(Option.id == option_id, Option.topic_id == topic_id))
            .first()
        )
        if not option:
            return {"success": False, "message": "Invalid option for this topic."}

        if self.has_voted(user, topic_id):
            return {"success": False, "message": "You have already voted on this topic."}

        # Determine identity fields by mode
        if topic.mode == VotingMode.IDENTIFIED:
            vote_user_id = user.id
            vote_hash = None
            track_user_id = user.id
            track_hash = None
        else:  # ANONYMOUS
            vote_user_id = None
            vote_hash = self._anon_hash(user.id, topic_id)
            track_user_id = None
            track_hash = vote_hash

        try:
            voted_at = datetime.utcnow()
            self.db.add(
                Vote(
                    topic_id=topic_id,
                    option_id=option_id,
                    user_id=vote_user_id,
                    hashed_user_id=vote_hash,
                    timestamp=voted_at,
                )
            )
            self.db.add(
                VoteTracking(
                    topic_id=topic_id,
                    user_id=track_user_id,
                    hashed_user_id=track_hash,
                    voted_at=voted_at,
                )
            )
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            return {
                "success": False,
                "message": "Duplicate vote detected. You have already voted.",
            }

        self._audit.log(
            action="VOTE_CAST",
            user_id=user.id,
            apartment_id=user.apartment_id,
            log_data={
                "topic_id": topic_id,
                "option_id": option_id,
                "mode": topic.mode.value,
            },
            ip_address=ip_address,
        )

        return {
            "success": True,
            "message": f"Your vote for '{topic.title}' has been recorded.",
            "topic_id": topic_id,
            "voted_at": voted_at.isoformat(),
        }

    # ── Results ──────────────────────────────────────────────────────────────

    def is_observer(self, user: "User", topic_id: int) -> bool:
        """Return True if the user is an appointed election observer for this topic."""
        topic = self.get_topic(topic_id)
        if not topic:
            return False
        return any(o.id == user.id for o in topic.observers)

    def get_my_vote(self, user: "User", topic_id: int) -> dict:
        """
        Return the option the current user chose for a topic.
        Works for both identified and anonymous voting modes — the voter is
        allowed to know their own choice even in anonymous mode.
        """
        topic = self.get_topic(topic_id)
        if not topic:
            return {"success": False, "message": "Topic not found."}

        if not self.has_voted(user, topic_id):
            return {"success": False, "message": "You have not voted on this topic yet."}

        if topic.mode == VotingMode.IDENTIFIED:
            vote = (
                self.db.query(Vote)
                .filter(
                    and_(Vote.topic_id == topic_id, Vote.user_id == user.id)
                )
                .first()
            )
        else:  # ANONYMOUS — use deterministic hash to locate the vote row
            h = self._anon_hash(user.id, topic_id)
            vote = (
                self.db.query(Vote)
                .filter(
                    and_(Vote.topic_id == topic_id, Vote.hashed_user_id == h)
                )
                .first()
            )

        if not vote:
            return {"success": False, "message": "Vote record not found."}

        option = (
            self.db.query(Option).filter(Option.id == vote.option_id).first()
        )
        return {
            "success": True,
            "topic_id": topic_id,
            "topic_title": topic.title,
            "mode": topic.mode.value,
            "option_id": vote.option_id,
            "option_text": option.text if option else "Unknown",
            "voted_at": vote.timestamp.isoformat(),
        }

    def get_results(self, topic_id: int) -> dict:
        topic = self.get_topic(topic_id)
        if not topic:
            return {"success": False, "message": "Topic not found."}

        eligible = (
            self.db.query(User)
            .filter(
                User.status == UserStatus.APPROVED,
                User.is_active.is_(True),
                User.is_admin.is_(False),
            )
            .count()
        )

        results = []
        total_votes = 0
        for opt in sorted(topic.options, key=lambda o: o.order):
            count = (
                self.db.query(Vote)
                .filter(
                    and_(Vote.topic_id == topic_id, Vote.option_id == opt.id)
                )
                .count()
            )
            total_votes += count
            results.append({"option_id": opt.id, "option_text": opt.text, "count": count})

        for r in results:
            r["percentage"] = round((r["count"] / total_votes * 100) if total_votes else 0, 1)

        participation = round((total_votes / eligible * 100) if eligible else 0, 1)

        return {
            "success": True,
            "topic_id": topic_id,
            "topic_title": topic.title,
            "mode": topic.mode.value,
            "status": topic.status.value,
            "total_votes": total_votes,
            "total_eligible": eligible,
            "participation_pct": participation,
            "results": [
                {
                    "option_id": r["option_id"],
                    "option_text": r["option_text"],
                    "vote_count": r["count"],
                    "percentage": r["percentage"],
                }
                for r in results
            ],
        }
