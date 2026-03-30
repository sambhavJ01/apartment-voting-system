from sqlalchemy import Column, Integer, String, Boolean, DateTime, Index
from datetime import datetime

from backend.database import Base


class OTPLog(Base):
    """
    Stores hashed OTPs.  The raw OTP is NEVER persisted — only its HMAC-SHA256.
    """
    __tablename__ = "otp_logs"

    id = Column(Integer, primary_key=True, index=True)
    phone_number = Column(String(20), nullable=False, index=True)
    otp_hash = Column(String(64), nullable=False)           # HMAC-SHA256 hex digest
    purpose = Column(String(50), nullable=False)            # registration | login | vote_confirmation
    expiry_time = Column(DateTime, nullable=False)
    attempts = Column(Integer, default=0, nullable=False)   # failed verification attempts
    verified = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)  # invalidated after use / new OTP
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_otp_active_lookup", "phone_number", "purpose", "is_active"),
    )

    def __repr__(self) -> str:
        return f"<OTPLog phone={self.phone_number} purpose={self.purpose} verified={self.verified}>"
