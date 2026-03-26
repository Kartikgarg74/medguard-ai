"""Immutable SHA-256 chained audit log for compliance auditability."""

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func

from src.database.models import AuditLog
from src.database.session import get_session
from src.utils.logger import get_logger

logger = get_logger(__name__)

GENESIS_HASH = "0" * 64  # Genesis block hash


def _compute_hash(data: str) -> str:
    """Compute SHA-256 hash of a string."""
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _hash_data(data: Any) -> str:
    """Hash any serializable data."""
    if data is None:
        return _compute_hash("null")
    return _compute_hash(json.dumps(data, sort_keys=True, default=str))


def _compute_entry_hash(entry: dict) -> str:
    """Compute the hash of an audit log entry (for chain integrity)."""
    fields = (
        f"{entry['sequence_num']}|{entry['timestamp']}|{entry['agent_name']}|"
        f"{entry['action']}|{entry['input_hash']}|{entry['output_hash']}|"
        f"{entry['prev_hash']}"
    )
    return _compute_hash(fields)


def log_audit(
    agent_name: str,
    action: str,
    resource_type: str | None = None,
    resource_id: str | None = None,
    input_data: Any = None,
    output_data: Any = None,
    metadata: dict | None = None,
    llm_model: str | None = None,
    llm_tokens_used: int | None = None,
    llm_cost_usd: float | None = None,
    duration_ms: int | None = None,
) -> str:
    """
    Write an immutable audit log entry with SHA-256 chain linking.

    Returns the entry ID.
    """
    session = get_session()
    try:
        # Get the previous entry's hash for chain linking
        last_entry = session.query(AuditLog).order_by(AuditLog.sequence_num.desc()).first()
        prev_hash = last_entry.entry_hash if last_entry else GENESIS_HASH
        next_seq = (last_entry.sequence_num + 1) if last_entry else 1

        now = datetime.now(timezone.utc)
        # Use a consistent timestamp string format for hashing
        # (SQLite strips timezone info, so we use a fixed format)
        ts_str = now.strftime("%Y-%m-%d %H:%M:%S")
        entry_id = str(uuid.uuid4())
        input_hash = _hash_data(input_data)
        output_hash = _hash_data(output_data)

        entry_dict = {
            "sequence_num": next_seq,
            "timestamp": ts_str,
            "agent_name": agent_name,
            "action": action,
            "input_hash": input_hash,
            "output_hash": output_hash,
            "prev_hash": prev_hash,
        }
        entry_hash = _compute_entry_hash(entry_dict)

        audit_entry = AuditLog(
            id=entry_id,
            sequence_num=next_seq,
            timestamp=now,
            agent_name=agent_name,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            input_hash=input_hash,
            output_hash=output_hash,
            metadata_json=json.dumps(metadata, default=str) if metadata else None,
            llm_model=llm_model,
            llm_tokens_used=llm_tokens_used,
            llm_cost_usd=llm_cost_usd,
            duration_ms=duration_ms,
            prev_hash=prev_hash,
            entry_hash=entry_hash,
        )

        session.add(audit_entry)
        session.commit()

        logger.debug(f"Audit log #{next_seq}: {agent_name}.{action} -> {entry_hash[:16]}...")
        return entry_id

    except Exception as e:
        session.rollback()
        logger.error(f"Failed to write audit log: {e}")
        raise
    finally:
        session.close()


def verify_chain() -> dict:
    """
    Verify the integrity of the entire audit log chain.

    Returns:
        {
            "valid": bool,
            "total_entries": int,
            "first_broken_at": int | None,  # sequence_num of first break
            "error": str | None,
        }
    """
    session = get_session()
    try:
        entries = session.query(AuditLog).order_by(AuditLog.sequence_num.asc()).all()

        if not entries:
            return {"valid": True, "total_entries": 0, "first_broken_at": None, "error": None}

        # Check genesis entry
        if entries[0].prev_hash != GENESIS_HASH:
            return {
                "valid": False,
                "total_entries": len(entries),
                "first_broken_at": entries[0].sequence_num,
                "error": "Genesis entry has wrong prev_hash",
            }

        for i, entry in enumerate(entries):
            # Recompute entry hash using same format as when written
            ts = entry.timestamp
            if isinstance(ts, datetime):
                ts_str = ts.strftime("%Y-%m-%d %H:%M:%S")
            else:
                ts_str = str(ts)
            entry_dict = {
                "sequence_num": entry.sequence_num,
                "timestamp": ts_str,
                "agent_name": entry.agent_name,
                "action": entry.action,
                "input_hash": entry.input_hash,
                "output_hash": entry.output_hash,
                "prev_hash": entry.prev_hash,
            }
            expected_hash = _compute_entry_hash(entry_dict)

            if entry.entry_hash != expected_hash:
                stored = entry.entry_hash[:16]
                expected = expected_hash[:16]
                return {
                    "valid": False,
                    "total_entries": len(entries),
                    "first_broken_at": entry.sequence_num,
                    "error": (
                        f"Entry #{entry.sequence_num} hash mismatch: "
                        f"stored={stored}... expected={expected}..."
                    ),
                }

            # Check chain link (skip first entry)
            if i > 0:
                prev_seq = entries[i - 1].sequence_num
                if entry.prev_hash != entries[i - 1].entry_hash:
                    return {
                        "valid": False,
                        "total_entries": len(entries),
                        "first_broken_at": entry.sequence_num,
                        "error": (
                            f"Chain broken at #{entry.sequence_num}: "
                            f"prev_hash doesn't match #{prev_seq}"
                        ),
                    }

        return {
            "valid": True,
            "total_entries": len(entries),
            "first_broken_at": None,
            "error": None,
        }

    finally:
        session.close()


def get_audit_stats() -> dict:
    """Get summary statistics of the audit log."""
    session = get_session()
    try:
        total = session.query(func.count(AuditLog.id)).scalar() or 0
        agents = (
            session.query(AuditLog.agent_name, func.count(AuditLog.id))
            .group_by(AuditLog.agent_name)
            .all()
        )
        return {
            "total_entries": total,
            "by_agent": {name: count for name, count in agents},
        }
    finally:
        session.close()
