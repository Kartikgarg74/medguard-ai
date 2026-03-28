"""API routes for compliance reports."""

from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse

from src.database.models import Report
from src.database.session import get_session

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("")
async def list_reports(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=50),
):
    """List generated reports."""
    session = get_session()
    try:
        total = session.query(Report).count()
        reports = (
            session.query(Report)
            .order_by(Report.generated_at.desc())
            .offset((page - 1) * limit)
            .limit(limit)
            .all()
        )

        return {
            "total": total,
            "page": page,
            "results": [
                {
                    "id": r.id,
                    "type": r.report_type,
                    "title": r.title,
                    "total_checked": r.total_medicines_checked,
                    "total_violations": r.total_violations,
                    "compliance_rate": r.compliance_rate,
                    "generated_at": r.generated_at.isoformat() if r.generated_at else None,
                    "file_path": r.file_path,
                }
                for r in reports
            ],
        }
    finally:
        session.close()


@router.get("/{report_id}")
async def get_report(report_id: str):
    """Get report metadata."""
    session = get_session()
    try:
        report = session.query(Report).filter_by(id=report_id).first()
        if not report:
            return {"error": "Report not found"}

        return {
            "id": report.id,
            "type": report.report_type,
            "title": report.title,
            "total_checked": report.total_medicines_checked,
            "total_violations": report.total_violations,
            "compliance_rate": report.compliance_rate,
            "generated_at": report.generated_at.isoformat() if report.generated_at else None,
            "file_path": report.file_path,
        }
    finally:
        session.close()


@router.get("/{report_id}/view")
async def view_report_html(report_id: str):
    """View the HTML report directly in browser."""
    session = get_session()
    try:
        report = session.query(Report).filter_by(id=report_id).first()
        if not report or not report.content_html:
            return HTMLResponse("<h1>Report not found</h1>", status_code=404)

        return HTMLResponse(report.content_html)
    finally:
        session.close()
