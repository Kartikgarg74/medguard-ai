"""Seed the medicine catalog from the GitHub Indian Medicine Dataset.

Source: https://github.com/junioralive/Indian-Medicine-Dataset
253,973 records with: name, price, manufacturer, type, pack_size, composition
"""

import csv
import io
import uuid
from pathlib import Path

import httpx

from src.database.models import Medicine
from src.database.session import get_session
from src.security.audit_log import log_audit
from src.utils.logger import get_logger

logger = get_logger(__name__)

DATASET_URL = (
    "https://raw.githubusercontent.com/junioralive/Indian-Medicine-Dataset/main/dataset.csv"
)
LOCAL_SEED_PATH = Path("data/seed/medicines.csv")


def _parse_composition(composition1: str, composition2: str) -> str:
    """Combine salt compositions into a single string."""
    parts = []
    if composition1 and composition1.strip():
        parts.append(composition1.strip())
    if composition2 and composition2.strip():
        parts.append(composition2.strip())
    return " + ".join(parts) if parts else "Unknown"


def _parse_formulation(name: str, pack_size: str) -> str:
    """Infer formulation from medicine name and pack size."""
    name_lower = (name or "").lower()
    pack_lower = (pack_size or "").lower()
    combined = name_lower + " " + pack_lower

    if any(w in combined for w in ["tablet", "tab "]):
        return "Tablet"
    elif any(w in combined for w in ["capsule", "cap "]):
        return "Capsule"
    elif any(w in combined for w in ["syrup", "suspension", "liquid", "oral solution"]):
        return "Syrup"
    elif any(w in combined for w in ["injection", "inj ", "vial"]):
        return "Injection"
    elif any(w in combined for w in ["cream", "ointment", "gel", "lotion"]):
        return "Topical"
    elif any(w in combined for w in ["drop", "eye ", "ear "]):
        return "Drops"
    elif any(w in combined for w in ["inhaler", "respule"]):
        return "Inhaler"
    elif any(w in combined for w in ["powder", "sachet", "granule"]):
        return "Powder"
    return "Other"


def _parse_dosage(name: str) -> str:
    """Extract dosage from medicine name (e.g., '500mg', '10ml')."""
    import re

    match = re.search(r"(\d+\.?\d*\s*(?:mg|mcg|g|ml|iu|meq|%|unit))", name, re.IGNORECASE)
    return match.group(1).strip() if match else ""


def download_dataset() -> str:
    """Download the CSV dataset. Returns CSV content as string."""
    # Check local cache first
    if LOCAL_SEED_PATH.exists():
        logger.info(f"Using cached seed data from {LOCAL_SEED_PATH}")
        return LOCAL_SEED_PATH.read_text(encoding="utf-8")

    logger.info(f"Downloading medicine dataset from {DATASET_URL}...")
    response = httpx.get(DATASET_URL, timeout=120, follow_redirects=True)
    response.raise_for_status()

    # Cache locally
    LOCAL_SEED_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOCAL_SEED_PATH.write_text(response.text, encoding="utf-8")
    logger.info(f"Dataset cached at {LOCAL_SEED_PATH}")

    return response.text


def seed_medicines(limit: int | None = None) -> int:
    """
    Seed the medicines table from the GitHub dataset.

    Args:
        limit: Max records to import (None = all 253K). Use limit=1000 for dev/testing.

    Returns:
        Number of medicines imported.
    """
    csv_content = download_dataset()
    reader = csv.DictReader(io.StringIO(csv_content))

    session = get_session()
    count = 0
    batch = []
    batch_size = 500

    try:
        for row in reader:
            if limit and count >= limit:
                break

            name = (row.get("name") or "").strip()
            if not name:
                continue

            medicine = Medicine(
                id=str(uuid.uuid4()),
                name=name,
                brand_name=name.split(" ")[0] if name else None,
                salt_composition=_parse_composition(
                    row.get("short_composition1", ""),
                    row.get("short_composition2", ""),
                ),
                formulation=_parse_formulation(name, row.get("pack_size_label", "")),
                dosage=_parse_dosage(name),
                manufacturer=(row.get("manufacturer_name") or "").strip(),
                pack_size=(row.get("pack_size_label") or "").strip(),
                dpco_scheduled=False,  # Will be updated when NPPA data is scraped
                nlem_listed=False,
            )
            batch.append(medicine)
            count += 1

            if len(batch) >= batch_size:
                session.bulk_save_objects(batch)
                session.commit()
                batch = []

        # Flush remaining batch
        if batch:
            session.bulk_save_objects(batch)
            session.commit()

        logger.info(f"Seeded {count} medicines into catalog")

        log_audit(
            agent_name="seed_loader",
            action="seed.medicines",
            resource_type="medicine",
            metadata={"count": count, "source": "github-indian-medicine-dataset"},
        )

        return count

    except Exception as e:
        session.rollback()
        logger.error(f"Seed failed: {e}")
        raise
    finally:
        session.close()
