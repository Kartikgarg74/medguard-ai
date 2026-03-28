"""Integration tests for all API endpoints."""

import os
import uuid

import pytest
from sqlalchemy import text

os.environ["DATABASE_PATH"] = ":memory:"

from src.database.models import ComplianceCheck, Medicine, Report
from src.database.session import get_session, init_db

# Build a test app without lifespan (avoids DB re-init conflicts)
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.audit import router as audit_router
from src.api.dashboard import router as dashboard_router
from src.api.medicines import router as medicines_router
from src.api.reports import router as reports_router
from src.api.scraper_api import router as scraper_router
from src.api.violations import router as violations_router

_app = FastAPI()
_app.include_router(medicines_router)
_app.include_router(violations_router)
_app.include_router(dashboard_router)
_app.include_router(reports_router)
_app.include_router(scraper_router)
_app.include_router(audit_router)


@_app.get("/health")
async def health():
    return {"status": "healthy", "service": "medguard-ai", "version": "0.1.0"}


client = TestClient(_app)

TABLES = [
    "alerts",
    "compliance_checks",
    "retail_prices",
    "ceiling_prices",
    "reports",
    "scrape_jobs",
    "audit_log",
    "medicines",
]


@pytest.fixture(autouse=True)
def clean_tables():
    """Ensure tables exist and clear data between tests."""
    # Re-init DB each test to handle engine resets from other test modules
    init_db()
    session = get_session()
    for table in TABLES:
        try:
            session.execute(text(f"DELETE FROM {table}"))
        except Exception:
            pass
    session.commit()
    session.close()
    yield


def _seed_test_data():
    """Seed minimal test data for API tests."""
    session = get_session()
    med_id = str(uuid.uuid4())
    session.add(
        Medicine(
            id=med_id,
            name="Paracetamol 500mg Tablet",
            salt_composition="Paracetamol",
            formulation="Tablet",
            dosage="500mg",
            manufacturer="Cipla",
            dpco_scheduled=True,
        )
    )

    for severity in ["critical", "high", "medium"]:
        session.add(
            ComplianceCheck(
                id=str(uuid.uuid4()),
                medicine_id=med_id,
                platform="1mg",
                ceiling_price=25.0,
                retail_price=50.0,
                overcharge_amount=25.0,
                overcharge_pct=100.0,
                status="violation",
                severity=severity,
                dpco_rule_applied="Para 4-7",
                confidence_score=1.0,
                checked_by="rule_engine",
            )
        )

    session.add(
        ComplianceCheck(
            id=str(uuid.uuid4()),
            medicine_id=med_id,
            platform="pharmeasy",
            ceiling_price=25.0,
            retail_price=20.0,
            overcharge_amount=0,
            overcharge_pct=0,
            status="compliant",
            confidence_score=1.0,
            checked_by="rule_engine",
        )
    )

    session.add(
        Report(
            id=str(uuid.uuid4()),
            report_type="daily_summary",
            title="Test Report",
            total_medicines_checked=10,
            total_violations=3,
            compliance_rate=70.0,
            content_html="<h1>Test</h1>",
        )
    )

    session.commit()
    session.close()
    return med_id


# --- Health ---


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "healthy"


# --- Medicines ---


def test_list_medicines_empty():
    r = client.get("/api/medicines")
    assert r.status_code == 200
    assert r.json()["total"] == 0


def test_list_medicines_with_data():
    _seed_test_data()
    r = client.get("/api/medicines")
    assert r.status_code == 200
    assert r.json()["total"] >= 1


def test_search_medicines():
    _seed_test_data()
    r = client.get("/api/medicines?search=Paracetamol")
    data = r.json()
    assert data["total"] >= 1
    assert "Paracetamol" in data["results"][0]["name"]


def test_get_medicine_detail():
    med_id = _seed_test_data()
    r = client.get(f"/api/medicines/{med_id}")
    assert r.status_code == 200
    data = r.json()
    assert data["name"] == "Paracetamol 500mg Tablet"
    assert data["dpco_scheduled"] is True


def test_dpco_only_filter():
    _seed_test_data()
    r = client.get("/api/medicines?dpco_only=true")
    assert r.json()["total"] >= 1


# --- Violations ---


def test_list_violations():
    _seed_test_data()
    r = client.get("/api/violations")
    assert r.status_code == 200
    assert r.json()["total"] == 3


def test_filter_violations_by_severity():
    _seed_test_data()
    r = client.get("/api/violations?severity=critical")
    data = r.json()
    assert data["total"] == 1
    assert data["results"][0]["severity"] == "critical"


def test_violation_stats():
    _seed_test_data()
    r = client.get("/api/violations/stats")
    data = r.json()
    assert data["total_checked"] == 4
    assert data["total_violations"] == 3
    assert data["compliance_rate"] == 25.0


# --- Dashboard ---


def test_dashboard_stats():
    _seed_test_data()
    r = client.get("/api/dashboard/stats")
    data = r.json()
    assert data["medicines_in_catalog"] >= 1
    assert data["violations"] >= 1


def test_violations_by_platform():
    _seed_test_data()
    r = client.get("/api/dashboard/violations-by-platform")
    data = r.json()
    assert "labels" in data
    assert "violations" in data


def test_top_violators():
    _seed_test_data()
    r = client.get("/api/dashboard/top-violators")
    assert isinstance(r.json(), list)
    assert len(r.json()) >= 1


# --- Reports ---


def test_list_reports():
    _seed_test_data()
    r = client.get("/api/reports")
    assert r.status_code == 200
    assert r.json()["total"] >= 1


def test_view_report_html():
    _seed_test_data()
    session = get_session()
    report = session.query(Report).first()
    report_id = report.id
    session.close()

    r = client.get(f"/api/reports/{report_id}/view")
    assert r.status_code == 200
    assert "<h1>Test</h1>" in r.text


# --- Scraper ---


def test_scraper_status():
    r = client.get("/api/scraper/status")
    assert r.status_code == 200
    assert "status" in r.json()


# --- Audit ---


def test_audit_verify():
    r = client.get("/api/audit/verify")
    assert r.status_code == 200
    assert "valid" in r.json()


def test_audit_stats():
    r = client.get("/api/audit/stats")
    assert r.status_code == 200
    assert "total_entries" in r.json()


def test_audit_log_list():
    r = client.get("/api/audit/log")
    assert r.status_code == 200
    assert "results" in r.json()
