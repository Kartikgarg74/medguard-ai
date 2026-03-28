#!/usr/bin/env python3
"""
Seed the database with realistic demo data for the hackathon.

50 real DPCO-scheduled medicines with NPPA ceiling prices,
realistic retail prices across 4 platforms, and pre-computed
compliance checks including 15+ known violations.

Usage:
    cd backend
    python -m scripts.seed_demo
"""

import os
import sys
import uuid
import random
from datetime import datetime, timezone

# Ensure backend/src is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("DATABASE_PATH", "data/medguard.db")

from src.database.models import (
    Alert,
    CeilingPrice,
    ComplianceCheck,
    Medicine,
    Report,
    RetailPrice,
    ScrapeJob,
)
from src.database.session import get_session, init_db
from src.security.audit_log import log_audit

# ============================================================
# REAL DPCO-scheduled medicines with actual NPPA ceiling prices
# Source: NPPA notifications + nppaindia.nic.in
# ============================================================

MEDICINES = [
    # (name, salt, formulation, dosage, pack, manufacturer, ceiling_price_per_unit)
    ("Paracetamol 500mg Tablet", "Paracetamol", "Tablet", "500mg", "10 tablets", "Cipla Ltd", 1.82),
    ("Paracetamol 650mg Tablet", "Paracetamol", "Tablet", "650mg", "15 tablets", "GSK", 2.41),
    ("Metformin 500mg Tablet", "Metformin Hydrochloride", "Tablet", "500mg", "10 tablets", "USV Ltd", 1.32),
    ("Metformin 1000mg Tablet", "Metformin Hydrochloride", "Tablet", "1000mg", "10 tablets", "Sun Pharma", 3.67),
    ("Amlodipine 5mg Tablet", "Amlodipine Besylate", "Tablet", "5mg", "10 tablets", "Cipla", 1.98),
    ("Amlodipine 10mg Tablet", "Amlodipine Besylate", "Tablet", "10mg", "10 tablets", "Micro Labs", 3.45),
    ("Atorvastatin 10mg Tablet", "Atorvastatin Calcium", "Tablet", "10mg", "10 tablets", "Ranbaxy", 3.92),
    ("Atorvastatin 20mg Tablet", "Atorvastatin Calcium", "Tablet", "20mg", "10 tablets", "Zydus", 6.50),
    ("Omeprazole 20mg Capsule", "Omeprazole", "Capsule", "20mg", "10 capsules", "Dr. Reddy's", 3.08),
    ("Pantoprazole 40mg Tablet", "Pantoprazole Sodium", "Tablet", "40mg", "10 tablets", "Alkem", 3.56),
    ("Amoxicillin 500mg Capsule", "Amoxicillin Trihydrate", "Capsule", "500mg", "10 capsules", "Cipla", 4.80),
    ("Amoxicillin 250mg Capsule", "Amoxicillin Trihydrate", "Capsule", "250mg", "10 capsules", "Mankind", 2.75),
    ("Ciprofloxacin 500mg Tablet", "Ciprofloxacin Hydrochloride", "Tablet", "500mg", "10 tablets", "Ranbaxy", 2.98),
    ("Azithromycin 500mg Tablet", "Azithromycin Dihydrate", "Tablet", "500mg", "3 tablets", "Alkem", 18.42),
    ("Ibuprofen 400mg Tablet", "Ibuprofen", "Tablet", "400mg", "10 tablets", "Cipla", 1.85),
    ("Diclofenac 50mg Tablet", "Diclofenac Sodium", "Tablet", "50mg", "10 tablets", "Novartis", 1.47),
    ("Cetirizine 10mg Tablet", "Cetirizine Hydrochloride", "Tablet", "10mg", "10 tablets", "Dr. Reddy's", 1.10),
    ("Losartan 50mg Tablet", "Losartan Potassium", "Tablet", "50mg", "10 tablets", "Torrent", 3.36),
    ("Telmisartan 40mg Tablet", "Telmisartan", "Tablet", "40mg", "10 tablets", "Glenmark", 2.98),
    ("Aspirin 75mg Tablet", "Acetylsalicylic Acid", "Tablet", "75mg", "14 tablets", "USV", 0.52),
    ("Clopidogrel 75mg Tablet", "Clopidogrel Bisulphate", "Tablet", "75mg", "10 tablets", "Sun Pharma", 5.10),
    ("Enalapril 5mg Tablet", "Enalapril Maleate", "Tablet", "5mg", "10 tablets", "Cadila", 1.50),
    ("Glimepiride 1mg Tablet", "Glimepiride", "Tablet", "1mg", "10 tablets", "Sanofi", 1.22),
    ("Glimepiride 2mg Tablet", "Glimepiride", "Tablet", "2mg", "10 tablets", "USV", 2.15),
    ("Metoprolol 50mg Tablet", "Metoprolol Succinate", "Tablet", "50mg", "10 tablets", "AstraZeneca", 3.85),
    ("Domperidone 10mg Tablet", "Domperidone", "Tablet", "10mg", "10 tablets", "Cipla", 1.42),
    ("Doxycycline 100mg Capsule", "Doxycycline Hyclate", "Capsule", "100mg", "10 capsules", "Ranbaxy", 3.20),
    ("Levofloxacin 500mg Tablet", "Levofloxacin Hemihydrate", "Tablet", "500mg", "10 tablets", "Cipla", 7.84),
    ("Montelukast 10mg Tablet", "Montelukast Sodium", "Tablet", "10mg", "10 tablets", "Sun Pharma", 5.95),
    ("Ceftriaxone 1g Injection", "Ceftriaxone Sodium", "Injection", "1g", "1 vial", "Alkem", 28.00),
    ("Fluconazole 150mg Capsule", "Fluconazole", "Capsule", "150mg", "1 capsule", "Cipla", 8.95),
    ("Albendazole 400mg Tablet", "Albendazole", "Tablet", "400mg", "1 tablet", "GSK", 3.80),
    ("Dexamethasone 0.5mg Tablet", "Dexamethasone", "Tablet", "0.5mg", "10 tablets", "Zydus", 0.58),
    ("Furosemide 40mg Tablet", "Furosemide", "Tablet", "40mg", "10 tablets", "Sanofi", 0.93),
    ("Prednisolone 5mg Tablet", "Prednisolone", "Tablet", "5mg", "10 tablets", "Wyeth", 0.92),
    ("Salbutamol 2mg Tablet", "Salbutamol Sulphate", "Tablet", "2mg", "10 tablets", "Cipla", 0.87),
    ("Atenolol 50mg Tablet", "Atenolol", "Tablet", "50mg", "14 tablets", "Ipca", 1.20),
    ("Nifedipine 10mg Capsule", "Nifedipine", "Capsule", "10mg", "10 capsules", "Bayer", 1.10),
    ("Phenytoin 100mg Tablet", "Phenytoin Sodium", "Tablet", "100mg", "10 tablets", "Abbott", 1.22),
    ("Isoniazid 300mg Tablet", "Isoniazid", "Tablet", "300mg", "10 tablets", "Macleods", 0.95),
    ("Rifampicin 450mg Capsule", "Rifampicin", "Capsule", "450mg", "10 capsules", "Lupin", 5.28),
    ("Ranitidine 150mg Tablet", "Ranitidine Hydrochloride", "Tablet", "150mg", "10 tablets", "GSK", 1.58),
    ("Acyclovir 200mg Tablet", "Acyclovir", "Tablet", "200mg", "10 tablets", "Cipla", 2.47),
    ("Gabapentin 300mg Capsule", "Gabapentin", "Capsule", "300mg", "10 capsules", "Sun Pharma", 5.80),
    ("Carvedilol 12.5mg Tablet", "Carvedilol", "Tablet", "12.5mg", "10 tablets", "Torrent", 2.75),
    ("Hydroxychloroquine 200mg Tablet", "Hydroxychloroquine Sulphate", "Tablet", "200mg", "10 tablets", "Ipca", 3.55),
    ("Clindamycin 300mg Capsule", "Clindamycin Hydrochloride", "Capsule", "300mg", "10 capsules", "Alkem", 8.30),
    ("Gentamicin 80mg Injection", "Gentamicin Sulphate", "Injection", "80mg/2ml", "1 ampoule", "Cipla", 4.50),
    ("Hydrocortisone 100mg Injection", "Hydrocortisone Sodium Succinate", "Injection", "100mg", "1 vial", "Pfizer", 18.75),
    ("Norfloxacin 400mg Tablet", "Norfloxacin", "Tablet", "400mg", "10 tablets", "Cipla", 2.10),
]

PLATFORMS = ["1mg", "pharmeasy", "netmeds", "apollo"]


def _gen_retail_price(ceiling: float, platform: str, violate: bool = False) -> tuple:
    """Generate a realistic retail price. Returns (mrp, selling_price, discount_pct)."""
    if violate:
        # Overpriced: 20% to 120% above ceiling
        multiplier = random.uniform(1.2, 2.2)
        mrp = round(ceiling * multiplier * 10, 2)  # per pack
    else:
        # Compliant: 70% to 100% of ceiling
        multiplier = random.uniform(0.7, 1.0)
        mrp = round(ceiling * multiplier * 10, 2)

    # Platform-specific discount patterns
    discount_ranges = {
        "1mg": (5, 25),
        "pharmeasy": (8, 30),
        "netmeds": (3, 20),
        "apollo": (0, 10),
    }
    d_min, d_max = discount_ranges.get(platform, (5, 15))
    discount = random.uniform(d_min, d_max)
    selling = round(mrp * (1 - discount / 100), 2)

    return mrp, selling, round(discount, 1)


def seed():
    """Seed the database with demo data."""
    init_db()
    session = get_session()

    print("Seeding demo data...")

    # Determine which medicines will have violations (at least 15)
    violation_indices = random.sample(range(len(MEDICINES)), k=18)

    medicines_created = 0
    ceilings_created = 0
    prices_created = 0
    violations_created = 0
    compliant_created = 0

    # Phase 1: Insert medicines + ceiling prices + retail prices
    retail_data = []  # Collect data for compliance checks in phase 2

    for i, (name, salt, form, dose, pack, mfr, ceil_price) in enumerate(MEDICINES):
        is_violation = i in violation_indices
        med_id = str(uuid.uuid4())

        med = Medicine(
            id=med_id,
            name=name,
            brand_name=name.split(" ")[0],
            salt_composition=salt,
            formulation=form,
            dosage=dose,
            manufacturer=mfr,
            pack_size=pack,
            dpco_scheduled=True,
            nlem_listed=True,
            nlem_category="Essential Medicine",
        )
        session.add(med)
        medicines_created += 1

        # Create ceiling price
        cp = CeilingPrice(
            id=str(uuid.uuid4()),
            medicine_id=med_id,
            ceiling_price=ceil_price,
            price_per_unit=f"per {form.lower()}",
            notification_number=f"SO-{random.randint(1000, 9999)}(E)",
            notification_date="2025-03-28",
            effective_from="2025-04-01",
            source_url="https://nppaimis.nic.in/nppaprice/pharmasahidaamweb.aspx",
        )
        session.add(cp)
        ceilings_created += 1

        # Create retail prices across platforms
        for platform in PLATFORMS:
            # Some medicines may violate on some platforms but not others
            platform_violate = is_violation and random.random() > 0.3
            mrp, selling, discount = _gen_retail_price(ceil_price, platform, platform_violate)

            rp_id = str(uuid.uuid4())
            rp = RetailPrice(
                id=rp_id,
                medicine_id=med_id,
                platform=platform,
                product_url=f"https://www.{platform}.com/drugs/{name.lower().replace(' ', '-')}",
                product_name=f"{name} ({mfr})",
                listed_price=mrp,
                selling_price=selling,
                discount_pct=discount,
                in_stock=random.random() > 0.1,
                pack_size=pack,
                price_per_unit=round(selling / max(1, int("".join(c for c in pack if c.isdigit()) or "1")), 2),
            )
            session.add(rp)
            prices_created += 1

            # Save data for phase 2 compliance checks
            retail_data.append({
                "med_id": med_id, "rp_id": rp_id, "cp_id": cp.id,
                "platform": platform, "ceil_price": ceil_price,
                "selling": selling, "pack": pack, "form": form,
            })

    # Flush phase 1 to DB so FKs are valid
    session.flush()

    # Phase 2: Insert compliance checks
    for rd in retail_data:
        ceil_price = rd["ceil_price"]
        selling = rd["selling"]
        pack = rd["pack"]

        adjusted_ceil = ceil_price * 1.0174028
        pack_units = int("".join(c for c in pack if c.isdigit()) or "1")
        ceil_per_pack = adjusted_ceil * pack_units
        overcharge = max(0, selling - ceil_per_pack)
        overcharge_pct = (overcharge / ceil_per_pack * 100) if ceil_per_pack > 0 else 0

        if overcharge_pct > 2:
            status = "violation"
            if overcharge_pct > 50:
                severity = "critical"
            elif overcharge_pct > 20:
                severity = "high"
            elif overcharge_pct > 5:
                severity = "medium"
            else:
                severity = "low"
            violations_created += 1
            dpco_rule = "Para 4-7, 15, 16 (Scheduled Formulation)"
        else:
            status = "compliant"
            severity = None
            compliant_created += 1
            dpco_rule = "Para 4-7 (Scheduled Formulation)"

        cc = ComplianceCheck(
            id=str(uuid.uuid4()),
            medicine_id=rd["med_id"],
            retail_price_id=rd["rp_id"],
            ceiling_price_id=rd["cp_id"],
            platform=rd["platform"],
            ceiling_price=ceil_price,
            retail_price=selling,
            overcharge_amount=round(overcharge, 2),
            overcharge_pct=round(overcharge_pct, 2),
            status=status,
            severity=severity,
            dpco_rule_applied=dpco_rule,
            confidence_score=1.0,
            checked_by="rule_engine",
            checked_at=datetime.now(timezone.utc),
        )
        session.add(cc)

    # Create a sample report
    report = Report(
        id=str(uuid.uuid4()),
        report_type="daily_summary",
        title=f"MedGuard Demo Report — {datetime.now().strftime('%Y-%m-%d')}",
        generated_by="seed_demo",
        total_medicines_checked=medicines_created * len(PLATFORMS),
        total_violations=violations_created,
        compliance_rate=round(compliant_created / (violations_created + compliant_created) * 100, 1),
        content_html="<h1>Demo Report — Generated by seed script</h1>",
    )
    session.add(report)

    # Create scrape job records
    for src in ["nppa"] + PLATFORMS:
        session.add(ScrapeJob(
            id=str(uuid.uuid4()),
            source=src,
            status="completed",
            medicines_found=50 if src == "nppa" else random.randint(40, 50),
            prices_scraped=50 if src == "nppa" else random.randint(40, 50),
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
        ))

    session.commit()
    session.close()

    # Audit log entry
    log_audit(
        agent_name="seed_demo",
        action="seed.complete",
        metadata={
            "medicines": medicines_created,
            "ceilings": ceilings_created,
            "retail_prices": prices_created,
            "violations": violations_created,
            "compliant": compliant_created,
        },
    )

    print(f"""
Demo data seeded successfully!
  Medicines:        {medicines_created}
  Ceiling prices:   {ceilings_created}
  Retail prices:    {prices_created} ({len(PLATFORMS)} platforms)
  Violations:       {violations_created}
  Compliant:        {compliant_created}
  Compliance rate:  {round(compliant_created / (violations_created + compliant_created) * 100, 1)}%
  Report:           1
  Scrape jobs:      {1 + len(PLATFORMS)}
""")


if __name__ == "__main__":
    seed()
