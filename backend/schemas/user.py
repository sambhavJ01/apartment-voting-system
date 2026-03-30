from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime

from backend.models.user import UserStatus


# ─── Registration ──────────────────────────────────────────────────────────────

class UserRegisterRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    apartment_number: str = Field(..., min_length=1, max_length=20)
    phone_number: str = Field(..., min_length=10, max_length=20)

    @field_validator("phone_number")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        # Strip spaces/dashes; require E.164-ish format
        cleaned = v.replace(" ", "").replace("-", "")
        if not cleaned.lstrip("+").isdigit():
            raise ValueError("Phone number must contain only digits (and optional leading +)")
        if len(cleaned.lstrip("+")) < 9:
            raise ValueError("Phone number too short")
        return cleaned


class OTPVerifyRequest(BaseModel):
    phone_number: str
    otp: str = Field(..., min_length=6, max_length=6, pattern=r"^\d{6}$")
    purpose: str = "registration"  # registration | login | vote_confirmation


class ResendOTPRequest(BaseModel):
    phone_number: str
    purpose: str = "registration"


# ─── Login ─────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    password: str = Field(..., min_length=1)
    phone_number: Optional[str] = None
    apartment_number: Optional[str] = None
    name: Optional[str] = None


# ─── Responses ─────────────────────────────────────────────────────────────────

class UserPublic(BaseModel):
    id: int
    name: str
    apartment_number: str
    phone_number: str
    status: UserStatus
    is_active: bool
    is_admin: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserPublic


class MessageResponse(BaseModel):
    success: bool
    message: str
    debug_otp: Optional[str] = None  # populated only in "console" OTP mode
