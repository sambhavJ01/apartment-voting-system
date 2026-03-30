import enum

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime

from backend.database import Base


class UserStatus(str, enum.Enum):
    PENDING_OTP = "pending_otp"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    DISABLED = "disabled"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    apartment_id = Column(
        Integer, ForeignKey("apartments.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    phone_number = Column(String(20), unique=True, nullable=False, index=True)
    # password_hash is NULL until admin approves and generates credentials
    password_hash = Column(String(255), nullable=True)
    status = Column(Enum(UserStatus), default=UserStatus.PENDING_OTP, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    approved_at = Column(DateTime, nullable=True)
    approved_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Relationships
    apartment = relationship("Apartment", back_populates="users")
    votes = relationship("Vote", back_populates="user", lazy="select")
    vote_trackings = relationship("VoteTracking", back_populates="user", lazy="select")
    audit_logs = relationship(
        "AuditLog", back_populates="user", lazy="select",
        foreign_keys="[AuditLog.user_id]",
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} name={self.name!r} phone={self.phone_number}>"
