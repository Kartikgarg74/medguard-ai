"""API routes for dashboard data — KPIs, charts, trends."""

from fastapi import APIRouter, HTTPException
from sqlalchemy import case, func

from src.database.models import ComplianceCheck, Medicine, RetailPrice, ScrapeJob
from src.database.session import get_session

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/stats")
async def dashboard_stats():
    """KPI cards data for the dashboard."""
    session = get_session()
    try:
        medicines_count = session.query(func.count(Medicine.id)).scalar() or 0
        dpco_count = (
            session.query(func.count(Medicine.id))
            .filter(Medicine.dpco_scheduled == True)  # noqa: E712
            .scalar()
            or 0
        )
        total_checks = session.query(func.count(ComplianceCheck.id)).scalar() or 0
        violations = (
            session.query(func.count(ComplianceCheck.id))
            .filter(ComplianceCheck.status == "violation")
            .scalar()
            or 0
        )
        platforms_active = (
            session.query(func.count(func.distinct(RetailPrice.platform))).scalar() or 0
        )
        rate = (
            round(((total_checks - violations) / total_checks * 100), 1)
            if total_checks > 0
            else 100.0
        )

        return {
            "medicines_in_catalog": medicines_count,
            "dpco_scheduled": dpco_count,
            "total_checks": total_checks,
            "violations": violations,
            "compliance_rate": rate,
            "platforms_monitored": platforms_active,
        }
    except Exception:
        session.rollback()
        raise HTTPException(status_code=500, detail='Database query failed')
    finally:
        session.close()


@router.get("/violations-by-platform")
async def violations_by_platform():
    """Chart data: violations count per platform."""
    session = get_session()
    try:
        data = (
            session.query(
                ComplianceCheck.platform,
                func.count(ComplianceCheck.id).label("total"),
                func.sum(case((ComplianceCheck.status == "violation", 1), else_=0)).label(
                    "violations"
                ),
            )
            .group_by(ComplianceCheck.platform)
            .all()
        )

        return {
            "labels": [row[0] for row in data],
            "total": [row[1] for row in data],
            "violations": [row[2] or 0 for row in data],
        }
    except Exception:
        session.rollback()
        raise HTTPException(status_code=500, detail='Database query failed')
    finally:
        session.close()


@router.get("/top-violators")
async def top_violators():
    """Top 10 medicines with highest overcharge percentage."""
    session = get_session()
    try:
        results = (
            session.query(ComplianceCheck, Medicine.name)
            .join(Medicine, ComplianceCheck.medicine_id == Medicine.id)
            .filter(ComplianceCheck.status == "violation")
            .order_by(ComplianceCheck.overcharge_pct.desc())
            .limit(10)
            .all()
        )

        return [
            {
                "medicine_name": name,
                "platform": cc.platform,
                "overcharge_pct": cc.overcharge_pct,
                "overcharge_amount": cc.overcharge_amount,
                "severity": cc.severity,
            }
            for cc, name in results
        ]
    except Exception:
        session.rollback()
        raise HTTPException(status_code=500, detail='Database query failed')
    finally:
        session.close()


@router.get("/scrape-jobs")
async def recent_scrape_jobs():
    """Recent scrape job history."""
    session = get_session()
    try:
        jobs = session.query(ScrapeJob).order_by(ScrapeJob.created_at.desc()).limit(20).all()

        return [
            {
                "id": j.id,
                "source": j.source,
                "status": j.status,
                "medicines_found": j.medicines_found,
                "prices_scraped": j.prices_scraped,
                "errors": j.errors,
                "started_at": j.started_at.isoformat() if j.started_at else None,
                "completed_at": j.completed_at.isoformat() if j.completed_at else None,
            }
            for j in jobs
        ]
    except Exception:
        session.rollback()
        raise HTTPException(status_code=500, detail='Database query failed')
    finally:
        session.close()
