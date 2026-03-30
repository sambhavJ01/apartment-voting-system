"""
Centralised audit logging.  Every significant action in the system
is logged here — registration, OTP events, logins, votes, admin actions.
"""
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from backend.models.audit import AuditLog

logger = logging.getLogger(__name__)


class AuditService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def log(
        self,
        action: str,
        user_id: Optional[int] = None,
        apartment_id: Optional[int] = None,
        log_data: Optional[dict] = None,
        ip_address: Optional[str] = None,
    ) -> None:
        entry = AuditLog(
            user_id=user_id,
            apartment_id=apartment_id,
            action=action,
            timestamp=datetime.utcnow(),
            log_data=log_data,
            ip_address=ip_address,
        )
        self.db.add(entry)
        try:
            self.db.commit()
        except Exception as exc:
            self.db.rollback()
            logger.error("Audit log write failed for action=%r: %s", action, exc)
