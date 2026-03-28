"""Tests for scraper components — HTML parsing, fuzzy matching, price extraction."""

import os
import uuid

import pytest

os.environ["DATABASE_PATH"] = ":memory:"

from src.agents.scraper.nppa import _extract_price_from_row, _parse_results
from src.agents.scraper.pharmacy_base import PharmacyScraper, ScrapedPrice
from src.agents.scraper.agent import _find_matching_medicine, save_retail_prices
from src.database.models import Medicine
from src.database.session import get_session, init_db, reset_engine


@pytest.fixture(autouse=True)
def fresh_db():
    reset_engine()
    os.environ["DATABASE_PATH"] = ":memory:"
    init_db()
    yield
    reset_engine()


# --- NPPA Parser Tests ---


def test_extract_price_from_row_basic():
    # Parser picks first valid float in reasonable price range
    cols = ["Paracetamol 500mg Tablet", "Tablet", "25.50"]
    result = _extract_price_from_row(cols, "Paracetamol")
    assert result is not None
    assert result["ceiling_price"] == 25.50


def test_extract_price_from_row_with_pack_and_price():
    cols = ["Paracetamol 500mg Tablet", "Tablet", "10", "25.50"]
    result = _extract_price_from_row(cols, "Paracetamol")
    assert result is not None
    # Parser finds first valid float — may be pack_size(10) or price(25.50)
    assert result["ceiling_price"] > 0


def test_extract_price_from_row_no_price():
    cols = ["Paracetamol", "Tablet", "N/A", "Not Available"]
    result = _extract_price_from_row(cols, "Paracetamol")
    assert result is None


def test_extract_price_from_row_with_comma():
    cols = ["Insulin Injection", "Injection", "1250.00"]
    result = _extract_price_from_row(cols, "Insulin")
    assert result is not None
    assert result["ceiling_price"] == 1250.00


def test_parse_results_no_table():
    html = "<html><body><p>No results found</p></body></html>"
    results = _parse_results(html, "NonExistent")
    assert results == []


def test_parse_results_with_table():
    html = """
    <html><body>
    <table id="GridView1">
        <tr><th>Medicine</th><th>Form</th><th>Price</th></tr>
        <tr><td>Paracetamol 500mg</td><td>Tablet</td><td>25.50</td></tr>
        <tr><td>Paracetamol 650mg</td><td>Tablet</td><td>32.00</td></tr>
    </table>
    </body></html>
    """
    results = _parse_results(html, "Paracetamol")
    assert len(results) >= 1
    assert any(r["ceiling_price"] == 25.50 for r in results)


# --- Price Parsing Tests ---


class DummyScraper(PharmacyScraper):
    PLATFORM_NAME = "test"
    BASE_URL = "https://test.com"

    async def search_medicine(self, page, name):
        return []


def test_parse_price_basic():
    s = DummyScraper()
    assert s._parse_price("₹45.50") == 45.50
    assert s._parse_price("MRP ₹ 120.00") == 120.00
    assert s._parse_price("₹1,250.00") == 1250.00
    assert s._parse_price("") == 0.0
    assert s._parse_price("N/A") == 0.0


def test_calculate_per_unit():
    s = DummyScraper()
    assert s._calculate_per_unit(100.0, "10 tablets") == 10.0
    assert s._calculate_per_unit(50.0, "5 ml bottle") == 10.0
    assert s._calculate_per_unit(30.0, "1 strip") == 30.0
    assert s._calculate_per_unit(100.0, "") == 100.0


# --- Fuzzy Matching Tests ---


def test_find_matching_medicine_exact():
    session = get_session()
    med = Medicine(
        id=str(uuid.uuid4()),
        name="Paracetamol 500mg Tablet",
        salt_composition="Paracetamol",
    )
    session.add(med)
    session.commit()

    found = _find_matching_medicine(session, "Paracetamol 500mg Tablet")
    assert found is not None
    assert found.name == "Paracetamol 500mg Tablet"
    session.close()


def test_find_matching_medicine_partial():
    session = get_session()
    med = Medicine(
        id=str(uuid.uuid4()),
        name="Metformin 500mg Tablet",
        salt_composition="Metformin Hydrochloride",
    )
    session.add(med)
    session.commit()

    found = _find_matching_medicine(session, "Metformin 500mg")
    assert found is not None
    session.close()


def test_find_matching_medicine_by_salt():
    session = get_session()
    med = Medicine(
        id=str(uuid.uuid4()),
        name="Glucophage 500mg",
        salt_composition="Metformin",
    )
    session.add(med)
    session.commit()

    found = _find_matching_medicine(session, "SomeOtherBrand", salt="Metformin")
    assert found is not None
    assert found.salt_composition == "Metformin"
    session.close()


def test_find_matching_medicine_no_match():
    session = get_session()
    session.add(
        Medicine(
            id=str(uuid.uuid4()),
            name="Paracetamol 500mg",
            salt_composition="Paracetamol",
        )
    )
    session.commit()

    found = _find_matching_medicine(session, "XYZNONEXISTENT12345DRUG")
    # Gibberish name should not fuzzy-match "Paracetamol 500mg" at 70% threshold
    assert found is None
    session.close()


# --- Save Retail Prices Tests ---


def test_save_retail_prices():
    session = get_session()
    med = Medicine(
        id=str(uuid.uuid4()),
        name="Paracetamol 500mg Tablet",
        salt_composition="Paracetamol",
    )
    session.add(med)
    session.commit()
    session.close()

    prices = [
        ScrapedPrice(
            product_name="Paracetamol 500mg Tablet",
            platform="1mg",
            listed_price=45.00,
            selling_price=38.00,
            discount_pct=15.6,
            pack_size="10 tablets",
            price_per_unit=3.80,
        ),
        ScrapedPrice(
            product_name="Paracetamol 500mg Tablet",
            platform="pharmeasy",
            listed_price=42.00,
            selling_price=35.00,
            discount_pct=16.7,
            pack_size="10 tablets",
            price_per_unit=3.50,
        ),
    ]

    saved = save_retail_prices(prices)
    assert saved == 2

    # Verify in DB
    from src.database.models import RetailPrice

    session = get_session()
    rps = session.query(RetailPrice).all()
    assert len(rps) == 2
    platforms = {rp.platform for rp in rps}
    assert "1mg" in platforms
    assert "pharmeasy" in platforms
    session.close()


def test_save_retail_prices_creates_unmatched_medicine():
    """If a scraped product doesn't match any medicine, it should create a new one."""
    prices = [
        ScrapedPrice(
            product_name="BrandNewDrug 100mg XYZ",
            platform="netmeds",
            listed_price=150.00,
            selling_price=130.00,
        ),
    ]

    saved = save_retail_prices(prices)
    assert saved == 1

    session = get_session()
    med = session.query(Medicine).filter(Medicine.name == "BrandNewDrug 100mg XYZ").first()
    assert med is not None
    session.close()
