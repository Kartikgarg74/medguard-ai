"""1mg.com medicine price scraper."""

import re

from src.agents.scraper.pharmacy_base import PharmacyScraper, ScrapedPrice
from src.utils.logger import get_logger

logger = get_logger(__name__)


class OneMgScraper(PharmacyScraper):
    PLATFORM_NAME = "1mg"
    BASE_URL = "https://www.1mg.com"

    async def search_medicine(self, page, medicine_name: str) -> list[ScrapedPrice]:
        results = []
        search_url = f"{self.BASE_URL}/search/all?name={medicine_name}"

        await page.goto(search_url, wait_until="domcontentloaded", timeout=20000)
        await page.wait_for_timeout(4000)

        # 1mg uses cardContainer class for product cards
        cards = await page.query_selector_all(
            'div[class*="cardContainer"], '
            'div[class*="product-card"], '
            'div[class*="style__product-card"]'
        )

        if not cards:
            # Broader fallback
            cards = await page.query_selector_all('div[class*="card"]')
            # Filter to only cards that contain price text
            filtered = []
            for card in cards:
                text = await card.inner_text()
                if "₹" in text:
                    filtered.append(card)
            cards = filtered

        for card in cards[:10]:
            try:
                price_data = await self._extract_card_data(card)
                if price_data:
                    results.append(price_data)
            except Exception as e:
                logger.debug(f"[1mg] Card parse error: {e}")

        return results

    async def _extract_card_data(self, card) -> ScrapedPrice | None:
        text = await card.inner_text()
        if not text or "₹" not in text:
            return None

        lines = [l.strip() for l in text.split("\n") if l.strip()]

        # Extract product name (usually first non-badge line)
        name = ""
        for line in lines:
            if line and line not in ("Bestseller", "Recommended", "Add to cart"):
                if not line.startswith("₹") and not line.endswith("off"):
                    name = line
                    break
        if not name:
            return None

        # Extract pack size (e.g., "strip of 15 tablets")
        pack_size = ""
        for line in lines:
            if any(w in line.lower() for w in ["strip", "tablet", "capsule", "bottle", "ml", "vial"]):
                if not line.startswith("₹"):
                    pack_size = line
                    break

        # Extract prices
        prices = re.findall(r"₹\s*(\d+\.?\d*)", text)
        if not prices:
            return None

        if len(prices) >= 2:
            selling = float(prices[0])
            mrp = float(prices[1])
        else:
            selling = float(prices[0])
            mrp = selling

        if selling > mrp and mrp > 0:
            mrp, selling = selling, mrp
        if selling <= 0:
            return None
        if mrp <= 0:
            mrp = selling

        # Extract URL
        link_el = await card.query_selector("a[href]")
        url = ""
        if link_el:
            href = await link_el.get_attribute("href")
            if href:
                url = href if href.startswith("http") else f"{self.BASE_URL}{href}"

        discount = round(((mrp - selling) / mrp * 100), 1) if mrp > selling else 0.0

        return ScrapedPrice(
            product_name=name.strip(),
            platform=self.PLATFORM_NAME,
            listed_price=mrp,
            selling_price=selling,
            discount_pct=discount,
            pack_size=pack_size.strip(),
            product_url=url,
            price_per_unit=self._calculate_per_unit(selling, pack_size),
        )
