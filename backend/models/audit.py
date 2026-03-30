from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON, Index
from sqlalchemy.orm import relationship
from datetime import datetime

from backend.database import Base


class AuditLog(Base):
    """
    Immutable audit trail. Rows are only inserted — never updated or deleted.
    The `log_data` column stores arbitrary JSON metadata (action-specific fields).
    Note: `metadata` is a reserved attribute on DeclarativeBase in SQLAlchemy 2.x,
    so we use `log_data` as the Python name while storing as "metadata" in the DB.
    """
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    apartment_id = Column(Integer, ForeignKey("apartments.id"), nullable=True, index=True)
    action = Column(String(100), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    log_data = Column("metadata", JSON, nullable=True)
    ip_address = Column(String(45), nullable=True)

    # Relationships
    user = relationship("User", back_populates="audit_logs", foreign_keys=[user_id])
    apartment = relationship("Apartment", back_populates="audit_logs", foreign_keys=[apartment_id])

    __table_args__ = (
        Index("ix_audit_action_ts", "action", "timestamp"),
    )

    def __repr__(self) -> str:
        return f"<AuditLog action={self.action!r} ts={self.timestamp}>"
