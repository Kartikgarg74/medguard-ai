"""Apollo Pharmacy medicine price scraper."""

from src.agents.scraper.pharmacy_base import PharmacyScraper, ScrapedPrice
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ApolloPharmacyScraper(PharmacyScraper):
    PLATFORM_NAME = "apollo"
    BASE_URL = "https://www.apollopharmacy.in"

    async def _create_browser_context(self, playwright):
        """Override with extra stealth for Apollo's anti-bot measures."""
        browser = await playwright.chromium.launch(
            headless=self.headless,
            args=[
                "--disable-blink-features=AutomationControlled",
            ],
        )
        context = await browser.new_context(
            user_agent=self._random_user_agent(),
            viewport={"width": 1440, "height": 900},
            locale="en-IN",
            timezone_id="Asia/Kolkata",
            geolocation={"latitude": 28.6139, "longitude": 77.2090},  # Delhi
            permissions=["geolocation"],
        )
        # Remove webdriver flag
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => false });
        """)
        # Block heavy resources
        await context.route(
            "**/*.{png,jpg,jpeg,gif,svg,ico,woff,woff2,ttf,mp4,webm}",
            lambda route: route.abort(),
        )
        return browser, context

    async def search_medicine(self, page, medicine_name: str) -> list[ScrapedPrice]:
        results = []
        safe_name = self._safe_medicine_name(medicine_name)
        search_url = f"{self.BASE_URL}/search-medicines/{safe_name}"

        try:
            await page.goto(search_url, wait_until="domcontentloaded", timeout=25000)
            await page.wait_for_timeout(4000)  # Apollo is slower to render
        except Exception as e:
            logger.warning(f"[apollo] Page load failed for '{medicine_name}': {e}")
            return results

        cards = await page.query_selector_all(
            "div[class*='ProductCard'], div[class*='product-card'], div[class*='MedicineCard']"
        )

        if not cards:
            cards = await page.query_selector_all("div[class*='product'], a[class*='product']")

        for card in cards[:10]:
            try:
                price_data = await self._extract_card_data(card)
                if price_data:
                    results.append(price_data)
            except Exception as e:
                logger.debug(f"[apollo] Card parse error: {e}")

        return results

    async def _extract_card_data(self, card) -> ScrapedPrice | None:
        import re

        name_el = await card.query_selector(
            "[class*='name'], [class*='title'], h2, h3, p[class*='Name']"
        )
        name = ""
        if name_el:
            name = await name_el.inner_text()
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
