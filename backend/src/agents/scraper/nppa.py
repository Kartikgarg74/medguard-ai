"""NPPA ceiling price scraper — fetches from Pharma Sahi Daam web tool."""

import re
import uuid
from datetime import datetime, timezone

import httpx
from bs4 import BeautifulSoup

from src.database.models import CeilingPrice, Medicine
from src.database.session import get_session
from src.security.audit_log import log_audit
from src.utils.logger import get_logger

logger = get_logger(__name__)

PHARMA_SAHI_DAAM_URL = "https://nppaimis.nic.in/nppaprice/pharmasahidaamweb.aspx"

# Common DPCO-scheduled medicines to seed ceiling price lookups
PRIORITY_MEDICINES = [
    "Paracetamol",
    "Metformin",
    "Amlodipine",
    "Atorvastatin",
    "Omeprazole",
    "Amoxicillin",
    "Ciprofloxacin",
    "Ibuprofen",
    "Diclofenac",
    "Ranitidine",
    "Aspirin",
    "Cetirizine",
    "Azithromycin",
    "Losartan",
    "Pantoprazole",
    "Clopidogrel",
    "Enalapril",
    "Glimepiride",
    "Metoprolol",
    "Domperidone",
    "Doxycycline",
    "Levofloxacin",
    "Montelukast",
    "Telmisartan",
    "Ceftriaxone",
    "Fluconazole",
    "Gabapentin",
    "Hydroxychloroquine",
    "Albendazole",
    "Acyclovir",
    "Atenolol",
    "Carvedilol",
    "Chloroquine",
    "Clindamycin",
    "Dexamethasone",
    "Diazepam",
    "Furosemide",
    "Gentamicin",
    "Hydrocortisone",
    "Insulin",
    "Isoniazid",
    "Lithium",
    "Mebendazole",
    "Morphine",
    "Nifedipine",
    "Norfloxacin",
    "Phenytoin",
    "Prednisolone",
    "Rifampicin",
    "Salbutamol",
]


async def _fetch_page(client: httpx.AsyncClient) -> tuple[str, dict]:
    """Fetch the Pharma Sahi Daam page and extract ASP.NET form fields."""
    response = await client.get(PHARMA_SAHI_DAAM_URL, timeout=30)
    response.raise_for_status()
    html = response.text
    soup = BeautifulSoup(html, "html.parser")

    # Extract ASP.NET hidden fields needed for POST
    form_data = {}
    for field_name in ["__VIEWSTATE", "__VIEWSTATEGENERATOR", "__EVENTVALIDATION"]:
        tag = soup.find("input", {"id": field_name})
        if tag:
            form_data[field_name] = tag.get("value", "")

    return html, form_data


async def _search_medicine(
    client: httpx.AsyncClient,
    medicine_name: str,
    form_data: dict,
) -> list[dict]:
    """Search for a medicine on Pharma Sahi Daam and parse results."""
    post_data = {
        **form_data,
        "ctl00$ContentPlaceHolder1$txtMedicineName": medicine_name,
        "ctl00$ContentPlaceHolder1$btnSearch": "Search",
    }

    try:
        response = await client.post(
            PHARMA_SAHI_DAAM_URL,
            data=post_data,
            timeout=30,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": PHARMA_SAHI_DAAM_URL,
            },
        )
        response.raise_for_status()
    except httpx.HTTPError as e:
        logger.warning(f"NPPA search failed for '{medicine_name}': {e}")
        return []

    return _parse_results(response.text, medicine_name)


def _parse_results(html: str, search_term: str) -> list[dict]:
    """Parse the Pharma Sahi Daam results table."""
    soup = BeautifulSoup(html, "html.parser")
    results = []

    # Find the results grid/table
    table = soup.find("table", {"id": re.compile(r"GridView|grdMedicine|ContentPlaceHolder")})
    if not table:
        # Try finding any table with price-like data
        tables = soup.find_all("table")
        for t in tables:
            if t.find("td", string=re.compile(r"\d+\.\d{2}")):
                table = t
                break

    if not table:
        logger.debug(f"No results table found for '{search_term}'")
        return results

    rows = table.find_all("tr")[1:]  # Skip header row
    for row in rows:
        cols = row.find_all("td")
        if len(cols) < 3:
            continue

        col_texts = [col.get_text(strip=True) for col in cols]

        # Try to extract: medicine name, dosage/formulation, ceiling price
        record = _extract_price_from_row(col_texts, search_term)
        if record:
            results.append(record)

    logger.info(f"NPPA: Found {len(results)} ceiling prices for '{search_term}'")
    return results


def _extract_price_from_row(cols: list[str], search_term: str) -> dict | None:
    """Extract structured data from a table row."""
    # Find the column that looks like a price (digits with decimal)
    price = None
    name = None
    formulation = None

    for i, col in enumerate(cols):
        # Price detection
        price_match = re.search(r"(\d+\.?\d*)", col)
        if price_match and not name:
            # First numeric-looking column after name
            continue

        if not name and len(col) > 3 and not col.replace(".", "").isdigit():
            name = col

    # Second pass: find price
    for col in cols:
        cleaned = col.strip().replace(",", "")
        try:
            val = float(cleaned)
            if 0.01 <= val <= 50000:  # Reasonable price range
                price = val
                break
        except ValueError:
            continue

    # Formulation detection
    for col in cols:
        col_lower = col.lower()
        if any(f in col_lower for f in ["tablet", "capsule", "syrup", "injection", "cream"]):
            formulation = col.strip()
            break

    if price and price > 0:
        return {
            "name": name or search_term,
            "formulation": formulation or "",
            "ceiling_price": price,
            "source": "nppa_pharma_sahi_daam",
        }
    return None


async def scrape_nppa_ceiling_prices(
    medicine_names: list[str] | None = None,
) -> list[dict]:
    """
    Scrape ceiling prices from NPPA Pharma Sahi Daam.

    Args:
        medicine_names: List of medicine names to search. Defaults to PRIORITY_MEDICINES.

    Returns:
        List of {name, formulation, ceiling_price, source} dicts.
    """
    if medicine_names is None:
        medicine_names = PRIORITY_MEDICINES

    all_results = []
    async with httpx.AsyncClient(follow_redirects=True) as client:
        # Step 1: Get the page and extract form fields
        try:
            _, form_data = await _fetch_page(client)
        except httpx.HTTPError as e:
            logger.error(f"Failed to fetch NPPA page: {e}")
            # Fallback: return empty (will use cached/seed data)
            return all_results

        # Step 2: Search each medicine
        for i, name in enumerate(medicine_names):
            results = await _search_medicine(client, name, form_data)
            all_results.extend(results)

            # Rate limiting: be respectful to government servers
            if i < len(medicine_names) - 1:
                import asyncio

                await asyncio.sleep(1.5)

    logger.info(f"NPPA scraping complete: {len(all_results)} ceiling prices found")

    log_audit(
        agent_name="scraper",
        action="scrape.nppa",
        metadata={
            "medicines_searched": len(medicine_names),
            "results_found": len(all_results),
        },
    )

    return all_results


def save_ceiling_prices(results: list[dict]) -> int:
    """Save scraped ceiling prices to database, linking to medicine catalog."""
    session = get_session()
    saved = 0

    try:
        for result in results:
            # Try to find matching medicine in catalog
            medicine = (
                session.query(Medicine).filter(Medicine.name.ilike(f"%{result['name']}%")).first()
            )

            if not medicine:
                # Create new medicine entry
                medicine = Medicine(
                    id=str(uuid.uuid4()),
                    name=result["name"],
                    salt_composition=result["name"],  # Use name as fallback
                    formulation=result.get("formulation", ""),
                    dpco_scheduled=True,
                )
                session.add(medicine)
                session.flush()

            # Mark as DPCO scheduled
            medicine.dpco_scheduled = True

            # Add ceiling price
            cp = CeilingPrice(
                id=str(uuid.uuid4()),
                medicine_id=medicine.id,
                ceiling_price=result["ceiling_price"],
                price_per_unit=result.get("formulation", ""),
                source_url=PHARMA_SAHI_DAAM_URL,
                scraped_at=datetime.now(timezone.utc),
            )
            session.add(cp)
            saved += 1

        session.commit()
        logger.info(f"Saved {saved} ceiling prices to database")

    except Exception as e:
        session.rollback()
        logger.error(f"Failed to save ceiling prices: {e}")
        raise
    finally:
        session.close()

    return saved
