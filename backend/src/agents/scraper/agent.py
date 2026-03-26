"""Scraper Agent — Orchestrates NPPA + pharmacy scrapers."""

import asyncio
import uuid
from datetime import datetime, timezone

from rapidfuzz import fuzz

from src.agents.base import BaseAgent
from src.agents.scraper.apollo import ApolloPharmacyScraper
from src.agents.scraper.netmeds import NetmedsScraper
from src.agents.scraper.nppa import (
    PRIORITY_MEDICINES,
    save_ceiling_prices,
    scrape_nppa_ceiling_prices,
)
from src.agents.scraper.onemg import OneMgScraper
from src.agents.scraper.pharmacy_base import ScrapedPrice
from src.agents.scraper.pharmeasy import PharmEasyScraper
from src.database.models import Medicine, RetailPrice, ScrapeJob
from src.database.session import get_session
from src.security.audit_log import log_audit
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Minimum fuzzy match score to link scraped product → medicine catalog
FUZZY_MATCH_THRESHOLD = 70


def _find_matching_medicine(session, product_name: str, salt: str = "") -> Medicine | None:
    """Find the best matching medicine in catalog using fuzzy matching."""
    # Try exact name match first
    exact = session.query(Medicine).filter(Medicine.name.ilike(f"%{product_name[:50]}%")).first()
    if exact:
        return exact

    # Try salt composition match
    if salt:
        salt_match = (
            session.query(Medicine).filter(Medicine.salt_composition.ilike(f"%{salt}%")).first()
        )
        if salt_match:
            return salt_match

    # Fuzzy match against catalog (sample for performance)
    candidates = session.query(Medicine).limit(5000).all()
    best_score = 0
    best_match = None

    for med in candidates:
        score = fuzz.token_sort_ratio(product_name.lower(), med.name.lower())
        if score > best_score:
            best_score = score
            best_match = med

    if best_score >= FUZZY_MATCH_THRESHOLD:
        return best_match

    return None


def save_retail_prices(prices: list[ScrapedPrice]) -> int:
    """Save scraped retail prices to database, linking to medicine catalog."""
    session = get_session()
    saved = 0

    try:
        for price in prices:
            medicine = _find_matching_medicine(session, price.product_name, price.salt_composition)

            if not medicine:
                # Create new medicine entry for unmatched products
                medicine = Medicine(
                    id=str(uuid.uuid4()),
                    name=price.product_name,
                    salt_composition=price.salt_composition or price.product_name,
                    manufacturer=price.manufacturer,
                    pack_size=price.pack_size,
                )
                session.add(medicine)
                session.flush()

            rp = RetailPrice(
                id=str(uuid.uuid4()),
                medicine_id=medicine.id,
                platform=price.platform,
                product_url=price.product_url,
                product_name=price.product_name,
                listed_price=price.listed_price,
                selling_price=price.selling_price,
                discount_pct=price.discount_pct,
                in_stock=price.in_stock,
                pack_size=price.pack_size,
                price_per_unit=price.price_per_unit,
                scraped_at=datetime.now(timezone.utc),
            )
            session.add(rp)
            saved += 1

        session.commit()
        logger.info(f"Saved {saved} retail prices to database")

    except Exception as e:
        session.rollback()
        logger.error(f"Failed to save retail prices: {e}")
        raise
    finally:
        session.close()

    return saved


class ScraperAgent(BaseAgent):
    """Orchestrates all scrapers: NPPA first, then pharmacies in parallel."""

    def __init__(self):
        super().__init__(name="scraper")
        self.scrapers = {
            "1mg": OneMgScraper(),
            "pharmeasy": PharmEasyScraper(),
            "netmeds": NetmedsScraper(),
            "apollo": ApolloPharmacyScraper(),
        }

    async def execute(
        self,
        medicine_names: list[str] | None = None,
        platforms: list[str] | None = None,
        max_concurrent: int = 3,
    ) -> dict:
        """
        Run full scraping pipeline.

        1. Scrape NPPA ceiling prices
        2. Scrape pharmacy retail prices (parallel with semaphore)
        3. Save all results to database
        """
        if medicine_names is None:
            medicine_names = PRIORITY_MEDICINES[:20]  # Default: top 20 for speed

        if platforms is None:
            platforms = list(self.scrapers.keys())

        results = {
            "nppa": {"searched": 0, "found": 0},
            "pharmacies": {},
            "total_prices": 0,
        }
        session = get_session()

        # Step 1: NPPA ceiling prices
        job_nppa = ScrapeJob(
            id=str(uuid.uuid4()),
            source="nppa",
            status="running",
            started_at=datetime.now(timezone.utc),
        )
        session.add(job_nppa)
        session.commit()

        try:
            nppa_results = await scrape_nppa_ceiling_prices(medicine_names)
            saved_ceiling = save_ceiling_prices(nppa_results)
            results["nppa"] = {
                "searched": len(medicine_names),
                "found": len(nppa_results),
                "saved": saved_ceiling,
            }
            job_nppa.status = "completed"
            job_nppa.medicines_found = len(nppa_results)
            job_nppa.prices_scraped = saved_ceiling
        except Exception as e:
            logger.error(f"NPPA scraping failed: {e}")
            job_nppa.status = "failed"
            job_nppa.error_details = str(e)
            results["nppa"]["error"] = str(e)

        job_nppa.completed_at = datetime.now(timezone.utc)
        session.commit()

        # Step 2: Pharmacy scrapers (parallel with concurrency limit)
        semaphore = asyncio.Semaphore(max_concurrent)

        async def scrape_platform(platform_name: str):
            async with semaphore:
                job = ScrapeJob(
                    id=str(uuid.uuid4()),
                    source=platform_name,
                    status="running",
                    started_at=datetime.now(timezone.utc),
                )
                session.add(job)
                session.commit()

                try:
                    scraper = self.scrapers[platform_name]
                    prices = await scraper.scrape(medicine_names)
                    saved = save_retail_prices(prices)

                    job.status = "completed"
                    job.medicines_found = len(medicine_names)
                    job.prices_scraped = saved
                    results["pharmacies"][platform_name] = {
                        "scraped": len(prices),
                        "saved": saved,
                    }
                    results["total_prices"] += saved

                except Exception as e:
                    logger.error(f"[{platform_name}] Scraping failed: {e}")
                    job.status = "failed"
                    job.errors = 1
                    job.error_details = str(e)
                    results["pharmacies"][platform_name] = {"error": str(e)}

                job.completed_at = datetime.now(timezone.utc)
                session.commit()

        # Run all pharmacy scrapers in parallel
        tasks = [scrape_platform(p) for p in platforms if p in self.scrapers]
        await asyncio.gather(*tasks, return_exceptions=True)

        session.close()

        log_audit(
            agent_name="scraper",
            action="scrape.complete",
            output_data=results,
            metadata={"medicines": len(medicine_names), "platforms": platforms},
        )

        return results
