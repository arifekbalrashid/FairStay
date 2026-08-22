"""Auto-seed the database with sample FairStay properties on first deploy."""

from __future__ import annotations

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database_models import PropertyDB
from app.models.schemas import NegotiationScenario
from app.negotiation.engine import get_scenario

logger = structlog.get_logger()

SEED_IMAGES = [
    "https://images.unsplash.com/photo-1502672260266-1c1ef2d93688?auto=format&fit=crop&q=80&w=800",
    "https://images.unsplash.com/photo-1522708323590-d24dbb6b0267?auto=format&fit=crop&q=80&w=800",
    "https://images.unsplash.com/photo-1560448204-e02f11c3d0e2?auto=format&fit=crop&q=80&w=800",
]


async def seed_properties(session: AsyncSession) -> None:
    """Insert default properties if the table is empty."""
    meta = get_scenario(NegotiationScenario.RENTAL)
    base_host_config = meta.default_party_b.model_dump()

    props = [
        PropertyDB(
            title="Modern Studio in Downtown",
            description="Beautiful open-plan studio with floor-to-ceiling windows and exposed brick. Perfect for solo travelers or couples.",
            location="Delhi, India",
            images=[SEED_IMAGES[0]],
            property_type="studio",
            bedrooms=1, beds=1, bathrooms=1.0,
            amenities=["WiFi", "AC", "Kitchen", "Parking", "Late checkout"],
            base_price=4500, cleaning_fee=500, deposit=15000, minimum_stay=5,
            rating=4.8, review_count=124,
        ),
        PropertyDB(
            title="Cozy 1BR Near University",
            description="Perfect for students or young professionals. Walking distance to campus.",
            location="Bangalore, India",
            images=[SEED_IMAGES[1]],
            property_type="apartment",
            bedrooms=1, beds=1, bathrooms=1.0,
            amenities=["WiFi", "AC", "Washing machine"],
            base_price=3000, cleaning_fee=300, deposit=10000, minimum_stay=2,
            rating=4.5, review_count=89,
        ),
        PropertyDB(
            title="Modern Skyline Apartment",
            description="High-rise apartment with stunning city views, pool, and gym access.",
            location="Mumbai, India",
            images=[SEED_IMAGES[2]],
            property_type="apartment",
            bedrooms=2, beds=2, bathrooms=2.0,
            amenities=["WiFi", "AC", "Kitchen", "Pool", "Gym", "Parking"],
            base_price=8500, cleaning_fee=1200, deposit=30000, minimum_stay=3,
            rating=4.9, review_count=210,
        ),
    ]

    for p in props:
        cfg = base_host_config.copy()
        cfg["ideal_values"] = cfg["ideal_values"].copy()
        cfg["ideal_values"]["nightly_price"] = p.base_price
        cfg["ideal_values"]["total_price"] = p.base_price * p.minimum_stay
        cfg["ideal_values"]["deposit"] = p.deposit
        cfg["ideal_values"]["cleaning_fee"] = p.cleaning_fee

        cfg["acceptable_values"] = cfg["acceptable_values"].copy()
        cfg["acceptable_values"]["nightly_price"] = p.base_price * 0.8

        cfg["hard_constraints"] = cfg["hard_constraints"].copy()
        cfg["hard_constraints"]["min_nightly_price"] = p.base_price * 0.8
        cfg["hard_constraints"]["min_stay_nights"] = p.minimum_stay

        p.negotiation_config = cfg
        session.add(p)

    await session.commit()
    logger.info("seed_properties_complete", count=len(props))
