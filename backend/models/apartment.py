from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime

from backend.database import Base


class Apartment(Base):
    __tablename__ = "apartments"

    id = Column(Integer, primary_key=True, index=True)
    apartment_number = Column(String(20), unique=True, nullable=False, index=True)
    max_allowed_voters = Column(Integer, default=3, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    users = relationship("User", back_populates="apartment", lazy="select")
    audit_logs = relationship(
        "AuditLog", back_populates="apartment", lazy="select",
        foreign_keys="[AuditLog.apartment_id]",
    )

    def __repr__(self) -> str:
        return f"<Apartment {self.apartment_number}>"
