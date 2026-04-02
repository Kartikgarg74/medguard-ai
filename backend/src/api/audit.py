"""API routes for audit log access and chain verification."""

from fastapi import APIRouter, HTTPException, Query

from src.database.models import AuditLog
from src.database.session import get_session
from src.security.audit_log import get_audit_stats, verify_chain

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("/log")
async def get_audit_log(
    agent: str = Query("", description="Filter by agent name"),
    action: str = Query("", description="Filter by action"),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
):
    """Query the audit log."""
    session = get_session()
    try:
        query = session.query(AuditLog)
        if agent:
            query = query.filter(AuditLog.agent_name == agent)
        if action:
            query = query.filter(AuditLog.action.ilike(f"%{action}%"))

        total = query.count()
        entries = (
            query.order_by(AuditLog.sequence_num.desc())
            .offset((page - 1) * limit)
            .limit(limit)
            .all()
        )

        return {
            "total": total,
            "page": page,
            "results": [
                {
                    "id": e.id,
                    "sequence": e.sequence_num,
                    "timestamp": e.timestamp.isoformat() if e.timestamp else None,
                    "agent": e.agent_name,
                    "action": e.action,
                    "resource_type": e.resource_type,
                    "resource_id": e.resource_id,
                    "llm_model": e.llm_model,
                    "llm_tokens": e.llm_tokens_used,
                    "duration_ms": e.duration_ms,
                    "entry_hash": e.entry_hash[:16] + "..." if e.entry_hash else None,
                }
                for e in entries
            ],
        }
    except Exception:
        session.rollback()
        raise HTTPException(status_code=500, detail='Database query failed')
    finally:
        session.close()


@router.get("/verify")
async def verify_audit_chain():
    """Verify the integrity of the audit log chain."""
    return verify_chain()


@router.get("/stats")
async def audit_stats():
    """Get audit log summary statistics."""
    return get_audit_stats()
