"""
Authentication service — registration, OTP confirmation, login, token management.
"""
import logging
import secrets
import string
from datetime import datetime, timedelta
from typing import Optional

import bcrypt as _bcrypt_lib
from jose import jwt, JWTError
from sqlalchemy import and_
from sqlalchemy.orm import Session

from backend.config import settings
from backend.models.apartment import Apartment
from backend.models.user import User, UserStatus
from backend.services.audit_service import AuditService

logger = logging.getLogger(__name__)


def hash_password(password: str) -> str:
    return _bcrypt_lib.hashpw(password.encode(), _bcrypt_lib.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _bcrypt_lib.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


def generate_password(length: int = 12) -> str:
    """Generate a secure random password for newly approved accounts."""
    alphabet = string.ascii_letters + string.digits + "!@#$%"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def create_access_token(user: User) -> str:
    payload = {
        "sub": str(user.id),
        "is_admin": user.is_admin,
        "phone": user.phone_number,
        "exp": datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


class AuthService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self._audit = AuditService(db)

    # ── Apartment helpers ────────────────────────────────────────────────────

    def _get_or_create_apartment(self, apartment_number: str) -> Apartment:
        apt = (
            self.db.query(Apartment)
            .filter(Apartment.apartment_number == apartment_number)
            .first()
        )
        if not apt:
            apt = Apartment(apartment_number=apartment_number)
            self.db.add(apt)
            self.db.flush()
        return apt

    # ── Registration ─────────────────────────────────────────────────────────

    def register_user(
        self,
        name: str,
        apartment_number: str,
        phone_number: str,
        ip_address: Optional[str] = None,
    ) -> dict:
        # Block re-registration if already past OTP stage
        existing = (
            self.db.query(User).filter(User.phone_number == phone_number).first()
        )
        if existing:
            if existing.status == UserStatus.PENDING_OTP:
                # Safe to restart — delete the incomplete record
                self.db.delete(existing)
                self.db.flush()
            else:
                return {
                    "success": False,
                    "message": "This phone number is already registered.",
                }

        apt = self._get_or_create_apartment(apartment_number)

        if not apt.is_active:
            return {"success": False, "message": f"Apartment {apartment_number} is not active."}

        # Enforce voter limit per apartment (approved + pending-approval only)
        current_count = (
            self.db.query(User)
            .filter(
                and_(
                    User.apartment_id == apt.id,
                    User.status.in_([UserStatus.PENDING_APPROVAL, UserStatus.APPROVED]),
                    User.is_active.is_(True),
                )
            )
            .count()
        )
        if current_count >= apt.max_allowed_voters:
            return {
                "success": False,
                "message": (
                    f"Apartment {apartment_number} already has the maximum "
                    f"{apt.max_allowed_voters} registered voter(s)."
                ),
            }

        user = User(
            name=name,
            apartment_id=apt.id,
            phone_number=phone_number,
            status=UserStatus.PENDING_OTP,
        )
        self.db.add(user)
        self.db.commit()

        self._audit.log(
            action="REGISTRATION_INITIATED",
            user_id=user.id,
            apartment_id=apt.id,
            log_data={"name": name, "apartment_number": apartment_number},
            ip_address=ip_address,
        )
        return {
            "success": True,
            "message": "Registration initiated. Please verify via WhatsApp OTP.",
            "phone_number": phone_number,
        }

    def confirm_registration_otp(
        self,
        phone_number: str,
        ip_address: Optional[str] = None,
    ) -> dict:
        """Called after OTP is verified — moves user to PENDING_APPROVAL."""
        user = self.db.query(User).filter(User.phone_number == phone_number).first()
        if not user:
            return {"success": False, "message": "User not found."}
        if user.status != UserStatus.PENDING_OTP:
            return {"success": False, "message": "Registration already progressed past OTP stage."}

        user.status = UserStatus.PENDING_APPROVAL
        self.db.commit()

        self._audit.log(
            action="REGISTRATION_OTP_VERIFIED",
            user_id=user.id,
            apartment_id=user.apartment_id,
            ip_address=ip_address,
        )
        return {
            "success": True,
            "message": (
                "Phone number verified. "
                "Your account is now pending admin approval."
            ),
        }

    # ── Login ────────────────────────────────────────────────────────────────

    def login(
        self,
        password: str,
        phone_number: Optional[str] = None,
        apartment_number: Optional[str] = None,
        name: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> dict:
        user: Optional[User] = None

        if phone_number:
            user = self.db.query(User).filter(User.phone_number == phone_number).first()
        elif apartment_number and name:
            apt = (
                self.db.query(Apartment)
                .filter(Apartment.apartment_number == apartment_number)
                .first()
            )
            if apt:
                user = (
                    self.db.query(User)
                    .filter(
                        and_(User.apartment_id == apt.id, User.name == name)
                    )
                    .first()
                )

        if not user:
            self._audit.log(
                action="LOGIN_FAILED",
                log_data={"reason": "user_not_found"},
                ip_address=ip_address,
            )
            return {"success": False, "message": "Invalid credentials."}

        if not user.is_active:
            return {"success": False, "message": "Account is disabled. Contact admin."}

        _pending_msgs = {
            UserStatus.PENDING_OTP: "Please complete OTP verification first.",
            UserStatus.PENDING_APPROVAL: "Your account is pending admin approval.",
            UserStatus.REJECTED: "Your registration was rejected. Contact admin.",
            UserStatus.DISABLED: "Your account has been disabled.",
        }
        if user.status != UserStatus.APPROVED:
            return {
                "success": False,
                "message": _pending_msgs.get(user.status, "Account is not active."),
            }

        if not user.password_hash or not verify_password(password, user.password_hash):
            self._audit.log(
                action="LOGIN_FAILED",
                user_id=user.id,
                log_data={"reason": "wrong_password"},
                ip_address=ip_address,
            )
            return {"success": False, "message": "Invalid credentials."}

        token = create_access_token(user)

        self._audit.log(
            action="LOGIN_SUCCESS",
            user_id=user.id,
            apartment_id=user.apartment_id,
            ip_address=ip_address,
        )
        return {
            "success": True,
            "access_token": token,
            "token_type": "bearer",
            "user": {
                "id": user.id,
                "name": user.name,
                "apartment_number": user.apartment.apartment_number,
                "phone_number": user.phone_number,
                "status": user.status.value,
                "is_active": user.is_active,
                "is_admin": user.is_admin,
                "created_at": user.created_at.isoformat(),
            },
        }

    # ── Token verification ────────────────────────────────────────────────────

    def verify_token(self, token: str) -> Optional[User]:
        try:
            payload = jwt.decode(
                token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
            )
            user_id = int(payload["sub"])
        except (JWTError, KeyError, ValueError, TypeError):
            return None

        user = self.db.query(User).filter(User.id == user_id).first()
        if user and user.is_active and user.status == UserStatus.APPROVED:
            return user
        return None
