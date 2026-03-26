"""1mg.com medicine price scraper."""

from src.agents.scraper.pharmacy_base import PharmacyScraper, ScrapedPrice
from src.utils.logger import get_logger

logger = get_logger(__name__)


class OneMgScraper(PharmacyScraper):
    PLATFORM_NAME = "1mg"
    BASE_URL = "https://www.1mg.com"

    async def search_medicine(self, page, medicine_name: str) -> list[ScrapedPrice]:
        """Search 1mg and extract product prices."""
        results = []
        search_url = f"{self.BASE_URL}/search/all?name={medicine_name}"

        await page.goto(search_url, wait_until="domcontentloaded", timeout=20000)
        # Wait for product cards to render (JS-heavy)
        await page.wait_for_timeout(3000)

        # Try multiple selectors for product cards
        cards = await page.query_selector_all(
            "div.style__product-card___1gbex, "
            "div[class*='product-card'], "
            "div[class*='ProductCard'], "
            "a[class*='productCard']"
        )

        if not cards:
            # Fallback: try generic product listing patterns
            cards = await page.query_selector_all(
                "div.row > div.col-md-12 > div, div[data-test-id*='product']"
            )

        for card in cards[:10]:  # Limit to top 10 results
            try:
                price_data = await self._extract_card_data(card, page)
                if price_data:
                    results.append(price_data)
            except Exception as e:
                logger.debug(f"[1mg] Failed to parse card: {e}")

        return results

    async def _extract_card_data(self, card, page) -> ScrapedPrice | None:
        """Extract price data from a 1mg product card."""
        # Product name
        name_el = await card.query_selector("[class*='name'], [class*='title'], h2, h3, a[title]")
        name = await name_el.inner_text() if name_el else ""
        if not name:
            title_el = await card.query_selector("a[title]")
            name = await title_el.get_attribute("title") if title_el else ""
        if not name:
            return None

        # Product URL
        link_el = await card.query_selector("a[href]")
        url = ""
        if link_el:
            href = await link_el.get_attribute("href")
            if href:
                url = href if href.startswith("http") else f"{self.BASE_URL}{href}"

        # Price extraction (MRP and selling price)
        price_text = await card.inner_text()
        mrp = 0.0
        selling = 0.0

        # Look for MRP (usually struck-through or labeled)
        mrp_el = await card.query_selector(
            "[class*='strike'], [class*='mrp'], del, s, "
            "span[class*='slash-price'], span[class*='original']"
        )
        if mrp_el:
            mrp = self._parse_price(await mrp_el.inner_text())

        # Look for selling price
        price_el = await card.query_selector(
            "[class*='price']:not([class*='strike']):not(del):not(s), "
            "[class*='best-price'], [class*='selling'], "
            "span[class*='final-price']"
        )
        if price_el:
            selling = self._parse_price(await price_el.inner_text())

        if selling <= 0:
            # Try parsing all price-like patterns from card text
            import re

            prices = re.findall(r"₹\s*(\d+\.?\d*)", price_text)
            if len(prices) >= 2:
                mrp = float(prices[0])
                selling = float(prices[1])
            elif len(prices) == 1:
                selling = float(prices[0])
                mrp = selling

        if selling <= 0:
            return None

        if mrp <= 0:
            mrp = selling

        # Pack size
        pack_el = await card.query_selector("[class*='pack'], [class*='quantity']")
        pack_size = await pack_el.inner_text() if pack_el else ""

        # Discount
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
