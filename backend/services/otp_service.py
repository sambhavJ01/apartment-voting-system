"""
OTP Service — generation, storage (hashed), delivery and verification.

Security notes:
- Raw OTP is NEVER stored; only HMAC-SHA256(otp + phone_number, SECRET_SALT).
- Timing-safe comparison via hmac.compare_digest().
- Max retry limit prevents brute-force.
- Rate-limit prevents OTP flooding.
"""
import hashlib
import hmac
import logging
import secrets
from datetime import datetime, timedelta

from sqlalchemy.orm import Session
from sqlalchemy import and_

from backend.config import settings
from backend.models.otp import OTPLog
from backend.services.otp_provider import OTPProvider

logger = logging.getLogger(__name__)

VALID_PURPOSES = {"registration", "login", "vote_confirmation"}


class OTPService:
    def __init__(self, provider: OTPProvider, db: Session) -> None:
        self.provider = provider
        self.db = db

    # ── Private helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _generate_otp() -> str:
        """Cryptographically secure 6-digit OTP."""
        return f"{secrets.randbelow(900_000) + 100_000:06d}"

    @staticmethod
    def _hash_otp(otp: str, phone_number: str) -> str:
        """
        HMAC-SHA256(key=OTP_SECRET_SALT, msg=otp:phone_number).
        Returns lowercase hex digest (64 chars).
        """
        key = settings.OTP_SECRET_SALT.encode()
        msg = f"{otp}:{phone_number}".encode()
        return hmac.new(key, msg, hashlib.sha256).hexdigest()

    def _check_rate_limit(self, phone_number: str, purpose: str) -> bool:
        """Return True (allowed) if the last OTP was created > OTP_RATE_LIMIT_SECONDS ago."""
        cutoff = datetime.utcnow() - timedelta(seconds=settings.OTP_RATE_LIMIT_SECONDS)
        recent = (
            self.db.query(OTPLog)
            .filter(
                and_(
                    OTPLog.phone_number == phone_number,
                    OTPLog.purpose == purpose,
                    OTPLog.created_at > cutoff,
                )
            )
            .first()
        )
        return recent is None

    def _invalidate_existing(self, phone_number: str, purpose: str) -> None:
        """Invalidate any currently active OTPs for this phone+purpose pair."""
        (
            self.db.query(OTPLog)
            .filter(
                and_(
                    OTPLog.phone_number == phone_number,
                    OTPLog.purpose == purpose,
                    OTPLog.is_active.is_(True),
                )
            )
            .update({"is_active": False}, synchronize_session=False)
        )

    # ── Public API ───────────────────────────────────────────────────────────

    def create_otp(self, phone_number: str, purpose: str) -> dict:
        """
        Phase 1 of two-phase OTP flow:
          - Rate-limit check
          - Generate + hash OTP
          - Persist hash to DB  ← committed before this method returns
          - Return raw OTP to caller (never stored; used only for dispatching)

        The DB commit happens here so the OTP record exists even when the
        WhatsApp dispatch is deferred to a background task.

        Returns: {success, otp (raw), message, debug_otp?}
        """
        if purpose not in VALID_PURPOSES:
            return {"success": False, "message": f"Invalid OTP purpose: {purpose}"}

        if not self._check_rate_limit(phone_number, purpose):
            return {
                "success": False,
                "message": (
                    f"Please wait {settings.OTP_RATE_LIMIT_SECONDS} seconds "
                    "before requesting another OTP."
                ),
            }

        self._invalidate_existing(phone_number, purpose)

        otp = self._generate_otp()
        otp_hash = self._hash_otp(otp, phone_number)
        expiry = datetime.utcnow() + timedelta(minutes=settings.OTP_EXPIRY_MINUTES)

        log = OTPLog(
            phone_number=phone_number,
            otp_hash=otp_hash,
            purpose=purpose,
            expiry_time=expiry,
            attempts=0,
            verified=False,
            is_active=True,
        )
        self.db.add(log)
        self.db.commit()

        result: dict = {
            "success": True,
            "otp": otp,   # raw OTP — must be passed directly to dispatch_to_provider
            "message": (
                f"OTP is being sent to WhatsApp {phone_number}. "
                f"Valid for {settings.OTP_EXPIRY_MINUTES} minutes."
            ),
        }
        # Surface raw OTP in dev console mode so UI can show it immediately
        if settings.OTP_PROVIDER.lower() == "console":
            result["debug_otp"] = otp
        return result

    def dispatch_to_provider(self, phone_number: str, otp: str, purpose: str) -> bool:
        """
        Phase 2 of two-phase OTP flow:
          - Calls the WhatsApp provider to deliver the OTP.
          - SAFE to call from a FastAPI BackgroundTask because it touches no
            DB session (the session from the request is already closed by then).

        Returns True on success, False on failure.
        """
        return self.provider.send_otp(phone_number, otp, purpose)

    def send_otp(self, phone_number: str, purpose: str) -> dict:
        """
        Convenience method: create_otp + dispatch_to_provider in one call.
        Used by routes that don't need async dispatch (e.g. resend-otp).
        """
        created = self.create_otp(phone_number, purpose)
        if not created["success"]:
            return created

        sent = self.dispatch_to_provider(phone_number, created["otp"], purpose)
        if not sent:
            # Invalidate so the user can retry immediately without rate-limit wait
            self._invalidate_existing(phone_number, purpose)
            self.db.commit()
            return {"success": False, "message": "Failed to deliver OTP. Please try again."}

        return {
            "success": True,
            "message": created["message"],
            "debug_otp": created.get("debug_otp"),
        }

    def verify_otp(self, phone_number: str, otp: str, purpose: str) -> dict:
        """
        Verify a submitted OTP.

        Returns dict with success (bool) and message (str).
        On success the OTPLog entry is marked verified+inactive (single-use).
        """
        expected_hash = self._hash_otp(otp, phone_number)

        log = (
            self.db.query(OTPLog)
            .filter(
                and_(
                    OTPLog.phone_number == phone_number,
                    OTPLog.purpose == purpose,
                    OTPLog.is_active.is_(True),
                    OTPLog.verified.is_(False),
                    OTPLog.expiry_time > datetime.utcnow(),
                )
            )
            .order_by(OTPLog.created_at.desc())
            .first()
        )

        if not log:
            return {
                "success": False,
                "message": "OTP not found or expired. Please request a new one.",
            }

        if log.attempts >= settings.OTP_MAX_RETRIES:
            log.is_active = False
            self.db.commit()
            return {
                "success": False,
                "message": "Maximum attempts exceeded. Please request a new OTP.",
            }

        # Increment attempts BEFORE comparison to prevent timing leaks
        log.attempts += 1
        self.db.commit()

        if not hmac.compare_digest(log.otp_hash, expected_hash):
            remaining = settings.OTP_MAX_RETRIES - log.attempts
            return {
                "success": False,
                "message": f"Invalid OTP. {max(remaining, 0)} attempt(s) remaining.",
            }

        # Mark as single-use
        log.verified = True
        log.is_active = False
        self.db.commit()

        return {"success": True, "message": "OTP verified successfully."}
