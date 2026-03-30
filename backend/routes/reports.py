"""
Report routes — topic summaries, per-topic detail, CSV/Excel export, audit logs.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.dependencies import get_current_admin, get_current_user
from backend.models.user import User
from backend.services.report_service import ReportService

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get("/topics")
async def all_topics_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Summary table for all topics (accessible to any approved voter)."""
    return ReportService(db).get_all_topics_summary()


@router.get("/topics/{topic_id}")
async def topic_report(
    topic_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = ReportService(db).get_topic_report(topic_id)
    if not result.get("success"):
        raise HTTPException(404, result.get("message", "Not found."))
    return result


@router.get("/topics/{topic_id}/export/csv")
async def export_csv(
    topic_id: int,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    data = ReportService(db).export_csv(topic_id)
    if not data:
        raise HTTPException(404, "Topic not found or export failed.")
    return Response(
        content=data,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=topic_{topic_id}_results.csv"},
    )


@router.get("/topics/{topic_id}/export/excel")
async def export_excel(
    topic_id: int,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    data = ReportService(db).export_excel(topic_id)
    if not data:
        raise HTTPException(404, "Topic not found or export failed (openpyxl may not be installed).")
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=topic_{topic_id}_results.xlsx"},
    )


@router.get("/audit-logs")
async def audit_logs(
    limit: int = Query(default=100, le=500),
    action_filter: str = Query(default=None),
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    return ReportService(db).get_audit_logs(limit=limit, action_filter=action_filter)
