"""
Voting routes — browse topics, two-phase vote (OTP initiate → cast).
"""
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from backend.config import settings
from backend.database import get_db
from backend.dependencies import get_current_user
from backend.models.user import User
from backend.schemas.vote import VoteCastRequest, VoteCastResponse, VoteInitiateRequest
from backend.services.otp_provider import get_otp_provider
from backend.services.otp_service import OTPService
from backend.services.voting_service import VotingService

router = APIRouter(prefix="/vote", tags=["Voting"])
limiter = Limiter(key_func=get_remote_address)


def _otp_svc(db: Session) -> OTPService:
    return OTPService(provider=get_otp_provider(settings), db=db)


def _ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


# ─── Browse topics ────────────────────────────────────────────────────────────

@router.get("/topics")
async def active_topics(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List active voting topics available to the current user."""
    svc = VotingService(db)
    topics = svc.get_active_topics()
    return [
        {
            "id": t.id,
            "title": t.title,
            "description": t.description,
            "mode": t.mode.value,
            "end_time": t.end_time.isoformat() if t.end_time else None,
            "has_voted": svc.has_voted(current_user, t.id),
            "is_observer": svc.is_observer(current_user, t.id),
            "options": [{"id": o.id, "text": o.text} for o in t.options],
        }
        for t in topics
    ]


@router.get("/topics/{topic_id}")
async def get_topic(
    topic_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    svc = VotingService(db)
    topic = svc.get_topic(topic_id)
    if not topic:
        raise HTTPException(404, "Topic not found.")
    return {
        "id": topic.id,
        "title": topic.title,
        "description": topic.description,
        "mode": topic.mode.value,
        "status": topic.status.value,
        "start_time": topic.start_time.isoformat() if topic.start_time else None,
        "end_time": topic.end_time.isoformat() if topic.end_time else None,
        "has_voted": svc.has_voted(current_user, topic_id),
        "is_observer": svc.is_observer(current_user, topic_id),
        "options": [
            {"id": o.id, "text": o.text, "order": o.order}
            for o in topic.options
        ],
    }


# ─── Two-phase voting ─────────────────────────────────────────────────────────

@router.post("/initiate", status_code=status.HTTP_200_OK)
@limiter.limit("15/minute")   # Per IP: prevents vote-initiate spam
async def initiate_vote(
    body: VoteInitiateRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Phase 1: Validate intent, then queue WhatsApp OTP in background.
    OTP hash is committed to DB synchronously; provider dispatch is non-blocking.
    """
    svc = VotingService(db)

    # Pre-validate before creating OTP to avoid wasted provider calls
    topic = svc.get_topic(body.topic_id)
    if not topic:
        raise HTTPException(404, "Topic not found.")
    if svc.has_voted(current_user, body.topic_id):
        raise HTTPException(409, "You have already voted on this topic.")

    otp_svc = _otp_svc(db)
    created = otp_svc.create_otp(current_user.phone_number, "vote_confirmation")
    if not created["success"]:
        raise HTTPException(429, created["message"])

    # Send OTP via WhatsApp provider in background (no DB access)
    provider = get_otp_provider(settings)
    background_tasks.add_task(
        provider.send_otp, current_user.phone_number, created["otp"], "vote_confirmation"
    )

    return {
        "success": True,
        "message": created["message"],
        "debug_otp": created.get("debug_otp"),
    }


@router.post("/cast", response_model=VoteCastResponse)
@limiter.limit("10/minute")   # Prevents OTP-guess brute-force during vote confirm
async def cast_vote(
    body: VoteCastRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Phase 2: Verify OTP then atomically record vote.
    """
    # Verify OTP first
    otp_result = _otp_svc(db).verify_otp(
        current_user.phone_number, body.otp, "vote_confirmation"
    )
    if not otp_result["success"]:
        raise HTTPException(400, otp_result["message"])

    # Cast vote
    result = VotingService(db).cast_vote(
        user=current_user,
        topic_id=body.topic_id,
        option_id=body.option_id,
        ip_address=_ip(request),
    )
    if not result["success"]:
        raise HTTPException(400, result["message"])

    return result


# ─── Results (observers + admin only) ────────────────────────────────────────

@router.get("/topics/{topic_id}/results")
async def get_results(
    topic_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Aggregated results — visible only to the admin and appointed observers.
    Regular voters receive 403; they can call /topics/{id}/my-vote instead.
    """
    svc = VotingService(db)
    if not current_user.is_admin and not svc.is_observer(current_user, topic_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Results are restricted to appointed election observers.",
        )

    result = svc.get_results(topic_id)
    if not result["success"]:
        raise HTTPException(404, result["message"])
    return result


# ─── My vote (every voter can retrieve their own choice) ─────────────────────

@router.get("/topics/{topic_id}/my-vote")
async def get_my_vote(
    topic_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returns the option the currently authenticated voter chose.
    Works in both identified and anonymous modes — the voter is always
    allowed to know their own selection.
    """
    result = VotingService(db).get_my_vote(current_user, topic_id)
    if not result["success"]:
        raise HTTPException(404, result["message"])
    return result
