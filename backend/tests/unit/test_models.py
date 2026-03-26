"""Tests for database models and session management."""

import os
import uuid

import pytest

os.environ["DATABASE_PATH"] = ":memory:"

from src.database.models import (
    Medicine,
    CeilingPrice,
    RetailPrice,
    ComplianceCheck,
    Report,
    Alert,
    ScrapeJob,
)
from src.database.session import get_engine, get_session, init_db, reset_engine


@pytest.fixture(autouse=True)
def fresh_db():
    """Create a fresh in-memory database for each test."""
    reset_engine()
    os.environ["DATABASE_PATH"] = ":memory:"
    init_db()
    yield
    reset_engine()


def test_create_medicine():
    session = get_session()
    med = Medicine(
        id=str(uuid.uuid4()),
        name="Paracetamol 500mg Tablet",
        salt_composition="Paracetamol",
        formulation="Tablet",
        dosage="500mg",
        manufacturer="Cipla Ltd",
        pack_size="10 tablets",
        dpco_scheduled=True,
        nlem_listed=True,
        nlem_category="Analgesic",
    )
    session.add(med)
    session.commit()

    fetched = session.query(Medicine).filter_by(name="Paracetamol 500mg Tablet").first()
    assert fetched is not None
    assert fetched.salt_composition == "Paracetamol"
    assert fetched.dpco_scheduled is True
    session.close()


def test_create_ceiling_price():
    session = get_session()
    med_id = str(uuid.uuid4())
    session.add(Medicine(id=med_id, name="Test Drug", salt_composition="TestSalt"))
    session.commit()

    cp = CeilingPrice(
        id=str(uuid.uuid4()),
        medicine_id=med_id,
        ceiling_price=25.50,
        price_per_unit="per tablet",
        notification_number="SO-1234",
    )
    session.add(cp)
    session.commit()

    fetched = session.query(CeilingPrice).filter_by(medicine_id=med_id).first()
    assert fetched.ceiling_price == 25.50
    session.close()


def test_create_retail_price():
    session = get_session()
    med_id = str(uuid.uuid4())
    session.add(Medicine(id=med_id, name="Test Drug", salt_composition="TestSalt"))
    session.commit()

    rp = RetailPrice(
        id=str(uuid.uuid4()),
        medicine_id=med_id,
        platform="1mg",
        listed_price=45.00,
        selling_price=38.00,
        discount_pct=15.6,
        pack_size="10 tablets",
        price_per_unit=3.80,
    )
    session.add(rp)
    session.commit()

    fetched = session.query(RetailPrice).filter_by(platform="1mg").first()
    assert fetched.selling_price == 38.00
    assert fetched.discount_pct == 15.6
    session.close()


def test_create_compliance_check():
    session = get_session()
    med_id = str(uuid.uuid4())
    session.add(Medicine(id=med_id, name="Test Drug", salt_composition="TestSalt"))
    session.commit()

    cc = ComplianceCheck(
        id=str(uuid.uuid4()),
        medicine_id=med_id,
        platform="pharmeasy",
        ceiling_price=25.00,
        retail_price=40.00,
        overcharge_amount=15.00,
        overcharge_pct=60.0,
        status="violation",
        severity="critical",
        dpco_rule_applied="Para 4-7",
        confidence_score=0.98,
        checked_by="rule_engine",
    )
    session.add(cc)
    session.commit()

    fetched = session.query(ComplianceCheck).filter_by(status="violation").first()
    assert fetched.overcharge_pct == 60.0
    assert fetched.severity == "critical"
    session.close()


def test_create_report():
    session = get_session()
    report = Report(
        id=str(uuid.uuid4()),
        report_type="daily_summary",
        title="Daily Compliance Report - 2026-03-26",
        total_medicines_checked=100,
        total_violations=5,
        compliance_rate=95.0,
    )
    session.add(report)
    session.commit()

    fetched = session.query(Report).first()
    assert fetched.compliance_rate == 95.0
    session.close()


def test_create_scrape_job():
    session = get_session()
    job = ScrapeJob(
        id=str(uuid.uuid4()),
        source="1mg",
        status="completed",
        medicines_found=50,
        prices_scraped=48,
        errors=2,
    )
    session.add(job)
    session.commit()

    fetched = session.query(ScrapeJob).filter_by(source="1mg").first()
    assert fetched.prices_scraped == 48
    session.close()


def test_medicine_relationships():
    session = get_session()
    med_id = str(uuid.uuid4())
    med = Medicine(id=med_id, name="Metformin 500mg", salt_composition="Metformin")
    session.add(med)

    session.add(CeilingPrice(id=str(uuid.uuid4()), medicine_id=med_id, ceiling_price=10.0))
    session.add(
        RetailPrice(
            id=str(uuid.uuid4()),
            medicine_id=med_id,
            platform="1mg",
            listed_price=15.0,
            selling_price=12.0,
        )
    )
    session.commit()

    fetched = session.query(Medicine).filter_by(id=med_id).first()
    assert len(fetched.ceiling_prices) == 1
    assert len(fetched.retail_prices) == 1
    session.close()
