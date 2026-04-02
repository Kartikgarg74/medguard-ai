"""API routes for compliance violations."""

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func

from src.database.models import ComplianceCheck, Medicine
from src.database.session import get_session

router = APIRouter(prefix="/api/violations", tags=["violations"])

_VALID_SEVERITIES = {"critical", "high", "medium", "low", ""}
_VALID_PLATFORMS = {"1mg", "pharmeasy", "netmeds", "apollo", ""}


@router.get("")
async def list_violations(
    severity: str = Query(
        "", max_length=20, description="Filter: critical/high/medium/low"
    ),
    platform: str = Query(
        "", max_length=50, description="Filter by platform"
    ),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    """List compliance violations with filters."""
    # Validate enum-like inputs
    if severity and severity.lower() not in _VALID_SEVERITIES:
        raise HTTPException(
            status_code=400,
            detail="Invalid severity. Use: critical, high, medium, low",
        )
    if platform and platform.lower() not in _VALID_PLATFORMS:
        raise HTTPException(
            status_code=400,
            detail="Invalid platform. Use: 1mg, pharmeasy, netmeds, apollo",
        )

    session = get_session()
    try:
        query = (
            session.query(ComplianceCheck, Medicine.name)
            .join(Medicine, ComplianceCheck.medicine_id == Medicine.id)
            .filter(ComplianceCheck.status.in_(["violation", "warning"]))
        )

        if severity:
            query = query.filter(ComplianceCheck.severity == severity)
        if platform:
            query = query.filter(ComplianceCheck.platform == platform)

        total = query.count()
        results = (
            query.order_by(ComplianceCheck.overcharge_pct.desc())
            .offset((page - 1) * limit)
            .limit(limit)
            .all()
        )

        return {
            "total": total,
            "page": page,
            "limit": limit,
            "results": [
                {
                    "id": cc.id,
                    "medicine_name": name,
                    "platform": cc.platform,
                    "ceiling_price": cc.ceiling_price,
                    "retail_price": cc.retail_price,
                    "overcharge_amount": cc.overcharge_amount,
                    "overcharge_pct": cc.overcharge_pct,
                    "status": cc.status,
                    "severity": cc.severity,
                    "dpco_rule": cc.dpco_rule_applied,
                    "reasoning": cc.llm_reasoning,
                    "confidence": cc.confidence_score,
                    "checked_by": cc.checked_by,
                    "checked_at": cc.checked_at.isoformat() if cc.checked_at else None,
                }
                for cc, name in results
            ],
        }
    except Exception:
        session.rollback()
        raise HTTPException(status_code=500, detail="Database query failed")
    finally:
        session.close()


@router.get("/stats")
async def violation_stats():
    """Aggregated violation statistics."""
    session = get_session()
    try:
        total = session.query(func.count(ComplianceCheck.id)).scalar() or 0
        violations = (
            session.query(func.count(ComplianceCheck.id))
            .filter(ComplianceCheck.status == "violation")
            .scalar()
            or 0
        )
        total_overcharge = (
            session.query(func.sum(ComplianceCheck.overcharge_amount))
            .filter(ComplianceCheck.status == "violation")
            .scalar()
            or 0
        )

        # By severity
        by_severity = dict(
            session.query(ComplianceCheck.severity, func.count(ComplianceCheck.id))
            .filter(ComplianceCheck.status == "violation")
            .group_by(ComplianceCheck.severity)
            .all()
        )

        # By platform
        by_platform = dict(
            session.query(ComplianceCheck.platform, func.count(ComplianceCheck.id))
            .filter(ComplianceCheck.status == "violation")
            .group_by(ComplianceCheck.platform)
            .all()
        )

        rate = round(((total - violations) / total * 100), 1) if total > 0 else 100.0

        return {
            "total_checked": total,
            "total_violations": violations,
            "compliance_rate": rate,
            "total_overcharge": round(total_overcharge, 2),
            "by_severity": by_severity,
            "by_platform": by_platform,
        }
    except Exception:
        session.rollback()
        raise HTTPException(status_code=500, detail="Database query failed")
    finally:
        session.close()
