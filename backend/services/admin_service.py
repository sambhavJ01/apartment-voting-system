"""
Admin service — user approval, apartment management, topic lifecycle.
"""
import logging
from datetime import datetime
from typing import List, Optional

from sqlalchemy import and_
from sqlalchemy.orm import Session

from backend.models.apartment import Apartment
from backend.models.topic import Topic, Option, TopicStatus, VotingMode
from backend.models.user import User, UserStatus
from backend.models.vote import Vote, VoteTracking
from backend.services.audit_service import AuditService
from backend.services.auth_service import generate_password, hash_password

logger = logging.getLogger(__name__)


class AdminService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self._audit = AuditService(db)

    # ── User management ──────────────────────────────────────────────────────

    def get_pending_users(self) -> List[User]:
        return (
            self.db.query(User)
            .filter(User.status == UserStatus.PENDING_APPROVAL)
            .order_by(User.created_at)
            .all()
        )

    def get_all_users(self, status: Optional[str] = None) -> List[User]:
        q = self.db.query(User).filter(User.is_admin.is_(False))
        if status:
            q = q.filter(User.status == UserStatus(status))
        return q.order_by(User.created_at.desc()).all()

    def approve_user(
        self,
        user_id: int,
        admin_id: int,
        ip_address: Optional[str] = None,
    ) -> dict:
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            return {"success": False, "message": "User not found."}
        if user.status != UserStatus.PENDING_APPROVAL:
            return {
                "success": False,
                "message": f"User status is '{user.status}' — expected 'pending_approval'.",
            }

        password = generate_password()
        user.status = UserStatus.APPROVED
        user.password_hash = hash_password(password)
        user.approved_at = datetime.utcnow()
        user.approved_by_id = admin_id
        self.db.commit()

        self._audit.log(
            action="USER_APPROVED",
            user_id=admin_id,
            apartment_id=user.apartment_id,
            log_data={"approved_user_id": user_id, "name": user.name},
            ip_address=ip_address,
        )
        return {
            "success": True,
            "message": f"User '{user.name}' approved.",
            # Admin must transmit this password to the user via a secure channel
            "generated_password": password,
            "user_id": user_id,
        }

    def reject_user(
        self,
        user_id: int,
        admin_id: int,
        reason: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> dict:
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            return {"success": False, "message": "User not found."}

        user.status = UserStatus.REJECTED
        self.db.commit()

        self._audit.log(
            action="USER_REJECTED",
            user_id=admin_id,
            apartment_id=user.apartment_id,
            log_data={"rejected_user_id": user_id, "reason": reason},
            ip_address=ip_address,
        )
        return {"success": True, "message": f"User '{user.name}' rejected."}

    def toggle_user(
        self,
        user_id: int,
        admin_id: int,
        active: bool,
        ip_address: Optional[str] = None,
    ) -> dict:
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            return {"success": False, "message": "User not found."}

        user.is_active = active
        if not active:
            user.status = UserStatus.DISABLED
        elif user.status == UserStatus.DISABLED:
            user.status = UserStatus.APPROVED
        self.db.commit()

        action = "USER_ENABLED" if active else "USER_DISABLED"
        self._audit.log(
            action=action,
            user_id=admin_id,
            log_data={"target_user_id": user_id},
            ip_address=ip_address,
        )
        label = "enabled" if active else "disabled"
        return {"success": True, "message": f"User '{user.name}' {label}."}

    # ── Apartment management ─────────────────────────────────────────────────

    def create_apartment(
        self,
        apartment_number: str,
        max_allowed_voters: int = 3,
        admin_id: Optional[int] = None,
    ) -> dict:
        if self.db.query(Apartment).filter(
            Apartment.apartment_number == apartment_number
        ).first():
            return {
                "success": False,
                "message": f"Apartment '{apartment_number}' already exists.",
            }

        apt = Apartment(
            apartment_number=apartment_number,
            max_allowed_voters=max_allowed_voters,
        )
        self.db.add(apt)
        self.db.commit()

        self._audit.log(
            action="APARTMENT_CREATED",
            user_id=admin_id,
            apartment_id=apt.id,
            log_data={
                "apartment_number": apartment_number,
                "max_voters": max_allowed_voters,
            },
        )
        return {
            "success": True,
            "message": f"Apartment '{apartment_number}' created.",
            "apartment_id": apt.id,
        }

    def list_apartments(self) -> List[Apartment]:
        return (
            self.db.query(Apartment)
            .order_by(Apartment.apartment_number)
            .all()
        )

    def update_apartment(
        self,
        apartment_id: int,
        max_allowed_voters: Optional[int] = None,
        is_active: Optional[bool] = None,
    ) -> dict:
        apt = self.db.query(Apartment).filter(Apartment.id == apartment_id).first()
        if not apt:
            return {"success": False, "message": "Apartment not found."}

        if max_allowed_voters is not None:
            apt.max_allowed_voters = max_allowed_voters
        if is_active is not None:
            apt.is_active = is_active
        self.db.commit()
        return {"success": True, "message": "Apartment updated."}

    # ── Topic management ─────────────────────────────────────────────────────

    def create_topic(
        self,
        title: str,
        description: Optional[str],
        mode: str,
        option_texts: List[str],
        observer_ids: Optional[List[int]] = None,
        start_time=None,
        end_time=None,
        admin_id: Optional[int] = None,
    ) -> dict:
        if len(option_texts) < 2:
            return {"success": False, "message": "At least 2 options required."}

        topic = Topic(
            title=title,
            description=description,
            mode=VotingMode(mode),
            status=TopicStatus.DRAFT,
            start_time=start_time,
            end_time=end_time,
            created_by_id=admin_id,
        )
        self.db.add(topic)
        self.db.flush()

        for i, text in enumerate(option_texts):
            self.db.add(Option(topic_id=topic.id, text=text, order=i))

        # Assign election observers (must be approved, non-admin residents)
        if observer_ids:
            observers = (
                self.db.query(User)
                .filter(
                    User.id.in_(observer_ids),
                    User.is_admin.is_(False),
                    User.status == UserStatus.APPROVED,
                )
                .all()
            )
            topic.observers = observers

        self.db.commit()

        self._audit.log(
            action="TOPIC_CREATED",
            user_id=admin_id,
            log_data={"topic_id": topic.id, "title": title, "mode": mode,
                      "observer_ids": [o.id for o in topic.observers]},
        )
        return {
            "success": True,
            "message": f"Topic '{title}' created.",
            "topic_id": topic.id,
        }

    def update_topic_status(
        self,
        topic_id: int,
        status: str,
        admin_id: Optional[int] = None,
    ) -> dict:
        topic = self.db.query(Topic).filter(Topic.id == topic_id).first()
        if not topic:
            return {"success": False, "message": "Topic not found."}

        topic.status = TopicStatus(status)
        self.db.commit()

        self._audit.log(
            action="TOPIC_STATUS_CHANGED",
            user_id=admin_id,
            log_data={"topic_id": topic_id, "new_status": status},
        )
        return {"success": True, "message": f"Topic status updated to '{status}'."}

    def set_topic_observers(
        self,
        topic_id: int,
        observer_ids: List[int],
        admin_id: Optional[int] = None,
    ) -> dict:
        """Replace the full list of election observers for a topic."""
        topic = self.db.query(Topic).filter(Topic.id == topic_id).first()
        if not topic:
            return {"success": False, "message": "Topic not found."}

        observers = (
            self.db.query(User)
            .filter(
                User.id.in_(observer_ids),
                User.is_admin.is_(False),
                User.status == UserStatus.APPROVED,
            )
            .all()
        ) if observer_ids else []
        topic.observers = observers
        self.db.commit()

        ids = [o.id for o in observers]
        self._audit.log(
            action="TOPIC_OBSERVERS_UPDATED",
            user_id=admin_id,
            log_data={"topic_id": topic_id, "observer_ids": ids},
        )
        return {
            "success": True,
            "message": (
                f"{len(ids)} observer(s) set for '{topic.title}'." if ids
                else f"All observers removed from '{topic.title}'."
            ),
            "observer_ids": ids,
        }

    def list_topics(self) -> List[Topic]:
        return (
            self.db.query(Topic)
            .order_by(Topic.created_at.desc())
            .all()
        )

    # ── Dashboard ────────────────────────────────────────────────────────────

    def get_dashboard_stats(self) -> dict:
        eligible = (
            self.db.query(User)
            .filter(
                User.status == UserStatus.APPROVED,
                User.is_active.is_(True),
                User.is_admin.is_(False),
            )
            .count()
        )
        pending = (
            self.db.query(User)
            .filter(User.status == UserStatus.PENDING_APPROVAL)
            .count()
        )
        active_topics = (
            self.db.query(Topic)
            .filter(Topic.status == TopicStatus.ACTIVE)
            .count()
        )
        total_votes = self.db.query(VoteTracking).count()
        total_apartments = (
            self.db.query(Apartment).filter(Apartment.is_active.is_(True)).count()
        )
        participation = (total_votes / eligible * 100) if eligible else 0.0

        return {
            "total_eligible_voters": eligible,
            "total_pending_approval": pending,
            "active_topics": active_topics,
            "total_votes_cast": total_votes,
            "total_apartments": total_apartments,
            "overall_participation_pct": round(participation, 1),
        }
