"""Netmeds medicine price scraper."""

from src.agents.scraper.pharmacy_base import PharmacyScraper, ScrapedPrice
from src.utils.logger import get_logger

logger = get_logger(__name__)


class NetmedsScraper(PharmacyScraper):
    PLATFORM_NAME = "netmeds"
    BASE_URL = "https://www.netmeds.com"

    async def search_medicine(self, page, medicine_name: str) -> list[ScrapedPrice]:
        results = []
        safe_name = self._safe_medicine_name(medicine_name)
        search_url = f"{self.BASE_URL}/catalogsearch/result/{safe_name}/all"

        await page.goto(search_url, wait_until="domcontentloaded", timeout=20000)
        await page.wait_for_timeout(3000)

        cards = await page.query_selector_all(
            "div.product-list div.ais-InfiniteHits-item, "
            "div[class*='product-card'], "
            "li[class*='product-item']"
        )

        if not cards:
            cards = await page.query_selector_all("div.cat-item, div[class*='product']")

        for card in cards[:10]:
            try:
                price_data = await self._extract_card_data(card)
                if price_data:
                    results.append(price_data)
            except Exception as e:
                logger.debug(f"[netmeds] Card parse error: {e}")

        return results

    async def _extract_card_data(self, card) -> ScrapedPrice | None:
        import re

        name_el = await card.query_selector("[class*='name'], [class*='title'], h3, h2, a[title]")
        name = ""
        if name_el:
            name = await name_el.inner_text()
            if not name:
                name = (await name_el.get_attribute("title")) or ""
        if not name:
            return None

        link_el = await card.query_selector("a[href]")
        url = ""
        if link_el:
            href = await link_el.get_attribute("href")
            if href:
                url = href if href.startswith("http") else f"{self.BASE_URL}{href}"

        card_text = await card.inner_text()
        prices = re.findall(r"₹\s*(\d+\.?\d*)", card_text)

        mrp = float(prices[0]) if len(prices) >= 1 else 0.0
        selling = float(prices[1]) if len(prices) >= 2 else mrp

        if selling > mrp and mrp > 0:
            mrp, selling = selling, mrp
        if selling <= 0:
            return None
        if mrp <= 0:
            mrp = selling

        pack_el = await card.query_selector("[class*='pack'], [class*='quantity']")
        pack_size = (await pack_el.inner_text()) if pack_el else ""

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
