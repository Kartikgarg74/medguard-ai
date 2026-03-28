"""PharmEasy medicine price scraper."""

import re

from src.agents.scraper.pharmacy_base import PharmacyScraper, ScrapedPrice
from src.utils.logger import get_logger

logger = get_logger(__name__)


class PharmEasyScraper(PharmacyScraper):
    PLATFORM_NAME = "pharmeasy"
    BASE_URL = "https://pharmeasy.in"

    async def search_medicine(self, page, medicine_name: str) -> list[ScrapedPrice]:
        results = []
        search_url = f"{self.BASE_URL}/search/all?name={medicine_name}"

        await page.goto(search_url, wait_until="domcontentloaded", timeout=20000)
        await page.wait_for_timeout(4000)

        # PharmEasy uses ProductCard_medicineUnitContainer
        cards = await page.query_selector_all(
            'div[class*="ProductCard_medicineUnitContainer"], '
            'div[class*="ProductCard_container"]'
        )

        if not cards:
            # Fallback: links to product pages with price text
            all_cards = await page.query_selector_all('div[class*="card"]')
            cards = []
            for c in all_cards:
                text = await c.inner_text()
                if "₹" in text and len(text) > 20:
                    cards.append(c)

        for card in cards[:10]:
            try:
                price_data = await self._extract_card_data(card)
                if price_data:
                    results.append(price_data)
            except Exception as e:
                logger.debug(f"[pharmeasy] Card parse error: {e}")

        return results

    async def _extract_card_data(self, card) -> ScrapedPrice | None:
        text = await card.inner_text()
        if not text or "₹" not in text:
            return None

        lines = [l.strip() for l in text.split("\n") if l.strip()]
        if len(lines) < 3:
            return None

        # PharmEasy format:
        # Line 0: Product name (e.g., "Dolo 650mg Strip Of 15 Tablets")
        # Line 1: "By MANUFACTURER"
        # Line 2: Pack size (e.g., "15 Tablet(s) in Strip")
        # Then prices: ₹selling, ₹mrp, XX% OFF
        name = lines[0] if lines else ""
        if not name or name.startswith("₹"):
            return None

        manufacturer = ""
        pack_size = ""
        for line in lines[1:4]:
            if line.startswith("By "):
                manufacturer = line[3:]
            elif any(w in line.lower() for w in ["tablet", "capsule", "strip", "bottle", "ml"]):
                pack_size = line

        # Extract prices
        prices = re.findall(r"₹(\d+\.?\d*)", text)
        if not prices:
            return None

        selling = float(prices[0])
        mrp = float(prices[1]) if len(prices) >= 2 else selling

        if selling > mrp and mrp > 0:
            mrp, selling = selling, mrp
        if selling <= 0:
            return None
        if mrp <= 0:
            mrp = selling

        # URL
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
            manufacturer=manufacturer.strip(),
            price_per_unit=self._calculate_per_unit(selling, pack_size),
        )
