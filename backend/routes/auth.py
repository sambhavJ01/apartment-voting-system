"""
Authentication routes — register, OTP verify, login, resend OTP.
"""
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from backend.config import settings
from backend.database import get_db
from backend.schemas.user import (
    LoginRequest,
    MessageResponse,
    OTPVerifyRequest,
    ResendOTPRequest,
    UserRegisterRequest,
)
from backend.services.auth_service import AuthService
from backend.services.otp_provider import get_otp_provider
from backend.services.otp_service import OTPService

router = APIRouter(prefix="/auth", tags=["Authentication"])
limiter = Limiter(key_func=get_remote_address)


def _otp_svc(db: Session) -> OTPService:
    return OTPService(provider=get_otp_provider(settings), db=db)


def _ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


# ─── Registration ─────────────────────────────────────────────────────────────

@router.post("/register", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")   # IP-based: prevents registration spam
async def register(
    body: UserRegisterRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Step 1 — Create account & queue WhatsApp OTP.
    OTP hash is committed to DB synchronously so verification works immediately.
    The actual WhatsApp dispatch runs as a BackgroundTask (non-blocking).
    """
    auth = AuthService(db)
    result = auth.register_user(
        body.name, body.apartment_number, body.phone_number, _ip(request)
    )
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])

    otp_svc = _otp_svc(db)
    created = otp_svc.create_otp(body.phone_number, "registration")
    if not created["success"]:
        raise HTTPException(status_code=429, detail=created["message"])

    # Dispatch via WhatsApp provider in background — no DB access needed
    provider = get_otp_provider(settings)
    background_tasks.add_task(
        provider.send_otp, body.phone_number, created["otp"], "registration"
    )
    return {
        "success": True,
        "message": created["message"],
        "debug_otp": created.get("debug_otp"),
    }


@router.post("/register/verify-otp", response_model=MessageResponse)
async def verify_registration_otp(
    body: OTPVerifyRequest, request: Request, db: Session = Depends(get_db)
):
    """Step 2 — Verify OTP; moves status to 'pending_approval'."""
    otp_result = _otp_svc(db).verify_otp(body.phone_number, body.otp, "registration")
    if not otp_result["success"]:
        raise HTTPException(status_code=400, detail=otp_result["message"])

    confirm = AuthService(db).confirm_registration_otp(body.phone_number, _ip(request))
    if not confirm["success"]:
        raise HTTPException(status_code=400, detail=confirm["message"])

    return {"success": True, "message": confirm["message"]}


@router.post("/resend-otp", response_model=MessageResponse)
@limiter.limit("5/minute")   # stricter: prevents OTP flooding
async def resend_otp(
    body: ResendOTPRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Re-send OTP. Hash stored sync; WhatsApp dispatch backgrounded."""
    otp_svc = _otp_svc(db)
    created = otp_svc.create_otp(body.phone_number, body.purpose)
    if not created["success"]:
        raise HTTPException(status_code=429, detail=created["message"])
    provider = get_otp_provider(settings)
    background_tasks.add_task(
        provider.send_otp, body.phone_number, created["otp"], body.purpose
    )
    return {
        "success": True,
        "message": created["message"],
        "debug_otp": created.get("debug_otp"),
    }


# ─── Login ──────────────────────────────────────────────────────────────

@router.post("/login")
@limiter.limit("20/minute")   # Prevents brute-force password guessing
async def login(body: LoginRequest, request: Request, db: Session = Depends(get_db)):
    """
    Login via phone+password  OR  apartment_number+name+password.
    Returns a JWT bearer token on success.
    """
    result = AuthService(db).login(
        password=body.password,
        phone_number=body.phone_number,
        apartment_number=body.apartment_number,
        name=body.name,
        ip_address=_ip(request),
    )
    if not result["success"]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=result["message"])
    return result
