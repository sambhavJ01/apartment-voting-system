from pydantic import BaseModel, Field
from typing import Optional


class ApartmentCreateRequest(BaseModel):
    apartment_number: str = Field(..., min_length=1, max_length=20)
    max_allowed_voters: int = Field(default=3, ge=1, le=10)


class ApartmentUpdateRequest(BaseModel):
    max_allowed_voters: Optional[int] = Field(None, ge=1, le=10)
    is_active: Optional[bool] = None


class UserApproveRequest(BaseModel):
    user_id: int
    reason: Optional[str] = None  # used for rejection


class UserToggleRequest(BaseModel):
    user_id: int
    active: bool


class AdminUserCreateRequest(BaseModel):
    """Allows bootstrapping an admin account via a secret key."""
    name: str = Field(..., min_length=2, max_length=100)
    apartment_number: str
    phone_number: str
    admin_key: str  # must match settings.ADMIN_REGISTRATION_KEY


class DashboardStats(BaseModel):
    total_eligible_voters: int
    total_pending_approval: int
    active_topics: int
    total_votes_cast: int
    total_apartments: int
    overall_participation_pct: float
