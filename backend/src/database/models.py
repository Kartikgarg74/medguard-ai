"""SQLAlchemy ORM models for MedGuard AI."""

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class Medicine(Base):
    """Core medicine catalog — populated from NPPA + scraped data."""

    __tablename__ = "medicines"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False, index=True)
    brand_name = Column(String, index=True)
    salt_composition = Column(String, nullable=False)
    formulation = Column(String)  # Tablet, Capsule, Syrup, Injection, etc.
    dosage = Column(String)  # e.g., "500mg", "10ml"
    manufacturer = Column(String)
    pack_size = Column(String)  # e.g., "10 tablets", "100ml bottle"
    dpco_scheduled = Column(Boolean, default=False)
    nlem_listed = Column(Boolean, default=False)
    nlem_category = Column(String)  # Analgesic, Anti-diabetic, etc.
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    ceiling_prices = relationship("CeilingPrice", back_populates="medicine")
    retail_prices = relationship("RetailPrice", back_populates="medicine")
    compliance_checks = relationship("ComplianceCheck", back_populates="medicine")


class CeilingPrice(Base):
    """NPPA ceiling prices — scraped from nppaindia.nic.in / Pharma Sahi Daam."""

    __tablename__ = "ceiling_prices"

    id = Column(String, primary_key=True)
    medicine_id = Column(String, ForeignKey("medicines.id"), nullable=False, index=True)
    ceiling_price = Column(Float, nullable=False)
    price_per_unit = Column(String)  # "per tablet", "per 5ml"
    notification_number = Column(String)
    notification_date = Column(String)
    effective_from = Column(String)
    source_url = Column(String)
    scraped_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    medicine = relationship("Medicine", back_populates="ceiling_prices")


class RetailPrice(Base):
    """Retail prices from online pharmacies — scraped from 1mg, PharmEasy, etc."""

    __tablename__ = "retail_prices"

    id = Column(String, primary_key=True)
    medicine_id = Column(String, ForeignKey("medicines.id"), nullable=False, index=True)
    platform = Column(String, nullable=False, index=True)  # '1mg', 'pharmeasy', 'netmeds', 'apollo'
    product_url = Column(String)
    product_name = Column(String)  # Exact name as listed on platform
    listed_price = Column(Float, nullable=False)  # MRP on platform
    selling_price = Column(Float, nullable=False)  # Actual selling price after discount
    discount_pct = Column(Float, default=0)
    in_stock = Column(Boolean, default=True)
    seller_name = Column(String)
    pack_size = Column(String)
    price_per_unit = Column(Float)  # selling_price / units_in_pack
    scraped_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    medicine = relationship("Medicine", back_populates="retail_prices")

    __table_args__ = (Index("idx_retail_platform_scraped", "platform", "scraped_at"),)


class ComplianceCheck(Base):
    """Compliance check results — output of the Compliance Checker Agent."""

    __tablename__ = "compliance_checks"

    id = Column(String, primary_key=True)
    medicine_id = Column(String, ForeignKey("medicines.id"), nullable=False, index=True)
    retail_price_id = Column(String, ForeignKey("retail_prices.id"))
    ceiling_price_id = Column(String, ForeignKey("ceiling_prices.id"))
    platform = Column(String, nullable=False)
    ceiling_price = Column(Float)
    retail_price = Column(Float)
    overcharge_amount = Column(Float)  # retail - ceiling (positive = violation)
    overcharge_pct = Column(Float)  # ((retail - ceiling) / ceiling) * 100
    status = Column(String, nullable=False, index=True)  # compliant/violation/warning/review_needed
    severity = Column(String, index=True)  # critical/high/medium/low
    dpco_rule_applied = Column(String)  # Which DPCO paragraph triggered
    llm_reasoning = Column(Text)
    confidence_score = Column(Float)
    checked_by = Column(String)  # "rule_engine", "llm_8b", "llm_70b"
    audit_hash = Column(String)  # SHA-256 of input+output for tamper detection
    checked_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    medicine = relationship("Medicine", back_populates="compliance_checks")


class Report(Base):
    """Generated compliance reports."""

    __tablename__ = "reports"

    id = Column(String, primary_key=True)
    report_type = Column(String, nullable=False)  # daily_summary, violation_detail, platform_audit
    title = Column(String, nullable=False)
    generated_by = Column(String, default="reporter_agent")
    content_html = Column(Text)
    content_json = Column(Text)  # Structured data as JSON string
    file_path = Column(String)
    total_medicines_checked = Column(Integer, default=0)
    total_violations = Column(Integer, default=0)
    compliance_rate = Column(Float)  # 0-100 percentage
    generated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Alert(Base):
    """Alert dispatch history."""

    __tablename__ = "alerts"

    id = Column(String, primary_key=True)
    compliance_check_id = Column(String, ForeignKey("compliance_checks.id"))
    channel = Column(String, nullable=False)  # telegram, email, webhook
    severity = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    status = Column(String, default="sent")  # sent, acknowledged, escalated, resolved
    acknowledged_by = Column(String)
    acknowledged_at = Column(DateTime)
    sent_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class AuditLog(Base):
    """Immutable audit log with SHA-256 chain integrity."""

    __tablename__ = "audit_log"

    id = Column(String, primary_key=True)
    sequence_num = Column(Integer, nullable=False, unique=True, index=True)
    timestamp = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    agent_name = Column(String, nullable=False, index=True)
    action = Column(String, nullable=False, index=True)
    resource_type = Column(String)  # medicine, price, violation, report
    resource_id = Column(String)
    input_hash = Column(String)  # SHA-256 of input data
    output_hash = Column(String)  # SHA-256 of output data
    metadata_json = Column(Text)  # JSON blob for extra context
    llm_model = Column(String)
    llm_tokens_used = Column(Integer)
    llm_cost_usd = Column(Float)
    duration_ms = Column(Integer)
    prev_hash = Column(String, nullable=False)  # SHA-256 of previous entry (chain)
    entry_hash = Column(String, nullable=False)  # SHA-256 of this entry

    __table_args__ = (Index("idx_audit_timestamp", "timestamp"),)


class ScrapeJob(Base):
    """Scraper job tracking."""

    __tablename__ = "scrape_jobs"

    id = Column(String, primary_key=True)
    source = Column(String, nullable=False)  # nppa, 1mg, pharmeasy, netmeds, apollo
    status = Column(String, nullable=False, default="pending")  # pending/running/completed/failed
    medicines_found = Column(Integer, default=0)
    prices_scraped = Column(Integer, default=0)
    errors = Column(Integer, default=0)
    error_details = Column(Text)  # JSON array
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
