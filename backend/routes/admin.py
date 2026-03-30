"""
Admin routes — user approval, apartment management, topic lifecycle, dashboard.
All endpoints require an authenticated admin user.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from backend.config import settings
from backend.database import get_db
from backend.dependencies import get_current_admin
from backend.models.user import User
from backend.schemas.admin import (
    AdminUserCreateRequest,
    ApartmentCreateRequest,
    ApartmentUpdateRequest,
    DashboardStats,
    UserApproveRequest,
    UserToggleRequest,
)
from backend.schemas.topic import TopicCreateRequest, TopicObserverUpdate, TopicStatusUpdate
from backend.services.admin_service import AdminService
from backend.services.auth_service import AuthService, generate_password, hash_password

router = APIRouter(prefix="/admin", tags=["Admin"])


def _ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


# ─── Bootstrap admin ─────────────────────────────────────────────────────────

@router.post("/bootstrap", status_code=status.HTTP_201_CREATED)
async def create_admin_user(body: AdminUserCreateRequest, db: Session = Depends(get_db)):
    """
    One-time endpoint to create the first admin.
    Requires matching ADMIN_REGISTRATION_KEY from .env.
    """
    if body.admin_key != settings.ADMIN_REGISTRATION_KEY:
        raise HTTPException(status_code=403, detail="Invalid admin registration key.")

    auth = AuthService(db)
    apt = auth._get_or_create_apartment(body.apartment_number)

    from backend.models.user import User, UserStatus
    existing = db.query(User).filter(User.phone_number == body.phone_number).first()
    if existing:
        raise HTTPException(400, "Phone number already registered.")

    password = generate_password()
    admin = User(
        name=body.name,
        apartment_id=apt.id,
        phone_number=body.phone_number,
        password_hash=hash_password(password),
        status=UserStatus.APPROVED,
        is_active=True,
        is_admin=True,
    )
    db.add(admin)
    db.commit()
    return {
        "success": True,
        "message": f"Admin '{body.name}' created. Save the generated password.",
        "generated_password": password,
    }


# ─── Dashboard ────────────────────────────────────────────────────────────────

@router.get("/dashboard", response_model=DashboardStats)
async def dashboard(
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    return AdminService(db).get_dashboard_stats()


# ─── User management ──────────────────────────────────────────────────────────

@router.get("/users/pending")
async def list_pending_users(
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    users = AdminService(db).get_pending_users()
    return [
        {
            "id": u.id,
            "name": u.name,
            "phone_number": u.phone_number,
            "apartment_number": u.apartment.apartment_number,
            "status": u.status.value,
            "created_at": u.created_at.isoformat(),
        }
        for u in users
    ]


@router.get("/users")
async def list_all_users(
    status_filter: Optional[str] = None,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    users = AdminService(db).get_all_users(status_filter)
    return [
        {
            "id": u.id,
            "name": u.name,
            "phone_number": u.phone_number,
            "apartment_number": u.apartment.apartment_number,
            "status": u.status.value,
            "is_active": u.is_active,
            "created_at": u.created_at.isoformat(),
            "approved_at": u.approved_at.isoformat() if u.approved_at else None,
        }
        for u in users
    ]


@router.post("/users/approve")
async def approve_user(
    body: UserApproveRequest,
    request: Request,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    result = AdminService(db).approve_user(body.user_id, admin.id, _ip(request))
    if not result["success"]:
        raise HTTPException(400, result["message"])
    return result


@router.post("/users/reject")
async def reject_user(
    body: UserApproveRequest,
    request: Request,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    result = AdminService(db).reject_user(body.user_id, admin.id, body.reason, _ip(request))
    if not result["success"]:
        raise HTTPException(400, result["message"])
    return result


@router.post("/users/toggle")
async def toggle_user(
    body: UserToggleRequest,
    request: Request,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    result = AdminService(db).toggle_user(body.user_id, admin.id, body.active, _ip(request))
    if not result["success"]:
        raise HTTPException(400, result["message"])
    return result


# ─── Apartment management ─────────────────────────────────────────────────────

@router.post("/apartments", status_code=status.HTTP_201_CREATED)
async def create_apartment(
    body: ApartmentCreateRequest,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    result = AdminService(db).create_apartment(
        body.apartment_number, body.max_allowed_voters, admin.id
    )
    if not result["success"]:
        raise HTTPException(400, result["message"])
    return result


@router.get("/apartments")
async def list_apartments(
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    apts = AdminService(db).list_apartments()
    return [
        {
            "id": a.id,
            "apartment_number": a.apartment_number,
            "max_allowed_voters": a.max_allowed_voters,
            "is_active": a.is_active,
            "registered_voters": sum(
                1 for u in a.users
                if u.status.value in ("approved", "pending_approval") and u.is_active
            ),
        }
        for a in apts
    ]


@router.put("/apartments/{apartment_id}")
async def update_apartment(
    apartment_id: int,
    body: ApartmentUpdateRequest,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    result = AdminService(db).update_apartment(
        apartment_id, body.max_allowed_voters, body.is_active
    )
    if not result["success"]:
        raise HTTPException(400, result["message"])
    return result


# ─── Topic management ─────────────────────────────────────────────────────────

@router.post("/topics", status_code=status.HTTP_201_CREATED)
async def create_topic(
    body: TopicCreateRequest,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    result = AdminService(db).create_topic(
        title=body.title,
        description=body.description,
        mode=body.mode.value,
        option_texts=[o.text for o in body.options],
        observer_ids=body.observer_ids,
        start_time=body.start_time,
        end_time=body.end_time,
        admin_id=admin.id,
    )
    if not result["success"]:
        raise HTTPException(400, result["message"])
    return result


@router.get("/topics")
async def list_topics(
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    topics = AdminService(db).list_topics()
    return [
        {
            "id": t.id,
            "title": t.title,
            "mode": t.mode.value,
            "status": t.status.value,
            "start_time": t.start_time.isoformat() if t.start_time else None,
            "end_time": t.end_time.isoformat() if t.end_time else None,
            "options_count": len(t.options),
            "created_at": t.created_at.isoformat(),
            "observers": [
                {"id": o.id, "name": o.name, "apartment_number": o.apartment.apartment_number}
                for o in t.observers
            ],
        }
        for t in topics
    ]


@router.put("/topics/{topic_id}/observers")
async def set_topic_observers(
    topic_id: int,
    body: TopicObserverUpdate,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Replace the full observer list for a topic (pass empty list to clear)."""
    result = AdminService(db).set_topic_observers(topic_id, body.observer_ids, admin.id)
    if not result["success"]:
        raise HTTPException(400, result["message"])
    return result


@router.put("/topics/{topic_id}/status")
async def update_topic_status(
    topic_id: int,
    body: TopicStatusUpdate,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    result = AdminService(db).update_topic_status(topic_id, body.status.value, admin.id)
    if not result["success"]:
        raise HTTPException(400, result["message"])
    return result
