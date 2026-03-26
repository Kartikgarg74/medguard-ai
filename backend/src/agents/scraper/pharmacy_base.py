"""Abstract base class for pharmacy website scrapers using Playwright."""

import asyncio
import os
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from src.utils.logger import get_logger

logger = get_logger(__name__)

USER_AGENTS = [
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15"
    ),
    (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
]


@dataclass
class ScrapedPrice:
    """A single scraped price record from an online pharmacy."""

    product_name: str
    platform: str
    listed_price: float  # MRP
    selling_price: float  # After discount
    discount_pct: float = 0.0
    pack_size: str = ""
    product_url: str = ""
    manufacturer: str = ""
    salt_composition: str = ""
    in_stock: bool = True
    price_per_unit: float = 0.0
    extra: dict = field(default_factory=dict)


class PharmacyScraper(ABC):
    """Abstract base for Playwright-based pharmacy scrapers."""

    PLATFORM_NAME: str = ""
    BASE_URL: str = ""
    MAX_RETRIES: int = 3

    def __init__(self):
        self.delay_min = float(os.getenv("SCRAPER_DELAY_MIN", "1.5"))
        self.delay_max = float(os.getenv("SCRAPER_DELAY_MAX", "4.0"))
        self.headless = os.getenv("SCRAPER_HEADLESS", "true").lower() == "true"
        self.logger = get_logger(f"scraper.{self.PLATFORM_NAME}")

    async def _random_delay(self):
        """Random delay between requests to avoid detection."""
        delay = random.uniform(self.delay_min, self.delay_max)
        await asyncio.sleep(delay)

    def _random_user_agent(self) -> str:
        return random.choice(USER_AGENTS)

    async def _create_browser_context(self, playwright):
        """Create a stealth browser context."""
        browser = await playwright.chromium.launch(
            headless=self.headless,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = await browser.new_context(
            user_agent=self._random_user_agent(),
            viewport={"width": 1366, "height": 768},
            locale="en-IN",
            timezone_id="Asia/Kolkata",
        )
        # Block unnecessary resources for speed
        await context.route(
            "**/*.{png,jpg,jpeg,gif,svg,ico,woff,woff2,ttf}",
            lambda route: route.abort(),
        )
        return browser, context

    @abstractmethod
    async def search_medicine(self, page, medicine_name: str) -> list[ScrapedPrice]:
        """Search for a medicine and extract price data. Subclasses must implement."""
        ...

    async def scrape(self, medicine_names: list[str]) -> list[ScrapedPrice]:
        """Scrape prices for a list of medicines."""
        all_results = []
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            self.logger.error("Playwright not installed. Run: playwright install chromium")
            return all_results

        async with async_playwright() as pw:
            browser, context = await self._create_browser_context(pw)
            page = await context.new_page()

            for i, name in enumerate(medicine_names):
                for attempt in range(self.MAX_RETRIES):
                    try:
                        results = await self.search_medicine(page, name)
                        all_results.extend(results)
                        self.logger.info(
                            f"[{self.PLATFORM_NAME}] '{name}': {len(results)} prices found"
                        )
                        break
                    except Exception as e:
                        self.logger.warning(
                            f"[{self.PLATFORM_NAME}] '{name}' attempt {attempt + 1} failed: {e}"
                        )
                        if attempt == self.MAX_RETRIES - 1:
                            self.logger.error(
                                f"[{self.PLATFORM_NAME}] '{name}' all retries exhausted"
                            )

                # Rate limiting between searches
                if i < len(medicine_names) - 1:
                    await self._random_delay()

            await browser.close()

        self.logger.info(
            f"[{self.PLATFORM_NAME}] Scraping complete: "
            f"{len(all_results)} prices from {len(medicine_names)} searches"
        )
        return all_results

    def _parse_price(self, text: str) -> float:
        """Parse a price string like '₹45.50' or 'MRP ₹ 120.00' into a float."""
        if not text:
            return 0.0
        import re

        cleaned = re.sub(r"[₹,\s]", "", text)
        match = re.search(r"(\d+\.?\d*)", cleaned)
        return float(match.group(1)) if match else 0.0

    def _calculate_per_unit(self, price: float, pack_size: str) -> float:
        """Calculate price per unit from pack size string."""
        import re

        match = re.search(r"(\d+)", pack_size)
        if match:
            units = int(match.group(1))
            if units > 0:
                return round(price / units, 2)
        return price
