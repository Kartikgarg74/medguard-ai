"""API routes for medicine search and price comparison."""

from fastapi import APIRouter, HTTPException, Query

from src.database.models import CeilingPrice, Medicine, RetailPrice
from src.database.session import get_session

router = APIRouter(prefix="/api/medicines", tags=["medicines"])


@router.get("")
async def list_medicines(
    search: str = Query("", description="Search by name or salt"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    dpco_only: bool = Query(False, description="Only DPCO-scheduled drugs"),
):
    """Search and list medicines."""
    session = get_session()
    try:
        query = session.query(Medicine)
        if search:
            query = query.filter(
                Medicine.name.ilike(f"%{search}%")
                | Medicine.salt_composition.ilike(f"%{search}%")
                | Medicine.brand_name.ilike(f"%{search}%")
            )
        if dpco_only:
            query = query.filter(Medicine.dpco_scheduled == True)  # noqa: E712

        total = query.count()
        medicines = query.offset((page - 1) * limit).limit(limit).all()

        return {
            "total": total,
            "page": page,
            "limit": limit,
            "results": [
                {
                    "id": m.id,
                    "name": m.name,
                    "brand_name": m.brand_name,
                    "salt_composition": m.salt_composition,
                    "formulation": m.formulation,
                    "dosage": m.dosage,
                    "manufacturer": m.manufacturer,
                    "pack_size": m.pack_size,
                    "dpco_scheduled": m.dpco_scheduled,
                    "nlem_listed": m.nlem_listed,
                }
                for m in medicines
            ],
        }
    finally:
        session.close()


@router.get("/{medicine_id}")
async def get_medicine(medicine_id: str):
    """Get medicine detail with latest prices across platforms."""
    session = get_session()
    try:
        med = session.query(Medicine).filter_by(id=medicine_id).first()
        if not med:
            raise HTTPException(status_code=404, detail="Medicine not found")

        # Latest ceiling price
        ceiling = (
            session.query(CeilingPrice)
            .filter_by(medicine_id=medicine_id)
            .order_by(CeilingPrice.scraped_at.desc())
            .first()
        )

        # Latest retail prices per platform
        platforms = ["1mg", "pharmeasy", "netmeds", "apollo"]
        price_comparison = {}
        for platform in platforms:
            rp = (
                session.query(RetailPrice)
                .filter_by(medicine_id=medicine_id, platform=platform)
                .order_by(RetailPrice.scraped_at.desc())
                .first()
            )
            if rp:
                price_comparison[platform] = {
                    "listed_price": rp.listed_price,
                    "selling_price": rp.selling_price,
                    "discount_pct": rp.discount_pct,
                    "pack_size": rp.pack_size,
                    "price_per_unit": rp.price_per_unit,
                    "product_url": rp.product_url,
                    "scraped_at": rp.scraped_at.isoformat() if rp.scraped_at else None,
                }

        return {
            "id": med.id,
            "name": med.name,
            "salt_composition": med.salt_composition,
            "formulation": med.formulation,
            "dosage": med.dosage,
            "manufacturer": med.manufacturer,
            "pack_size": med.pack_size,
            "dpco_scheduled": med.dpco_scheduled,
            "nlem_listed": med.nlem_listed,
            "ceiling_price": {
                "price": ceiling.ceiling_price,
                "notification": ceiling.notification_number,
                "effective_from": ceiling.effective_from,
            }
            if ceiling
            else None,
            "price_comparison": price_comparison,
        }
    finally:
        session.close()
