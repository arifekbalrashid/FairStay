#!/usr/bin/env python3
"""Seed the database with fictional FairStay properties."""

import asyncio
import json
import sys
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import select

sys.path.insert(0, ".")

from app.config import get_settings
from app.models.database_models import Base, PropertyDB
from app.models.schemas import NegotiationScenario
from app.negotiation.engine import get_scenario

async def seed():
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=True)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Recreate tables (drop and create)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    print("Tables recreated.")

    async with async_session() as session:
        # Load default host config
        meta = get_scenario(NegotiationScenario.RENTAL)
        base_host_config = meta.default_party_b.model_dump()
        
        props = [
            PropertyDB(
                title="Modern Studio in Downtown",
                description="Beautiful open-plan studio with floor-to-ceiling windows and exposed brick. Perfect for solo travelers or couples.",
                location="Delhi, India",
                images=["/loft.jpg"],
                property_type="studio",
                bedrooms=1,
                beds=1,
                bathrooms=1.0,
                amenities=["WiFi", "AC", "Kitchen", "Parking", "Late checkout"],
                base_price=4500,
                cleaning_fee=500,
                deposit=15000,
                minimum_stay=5,
                rating=4.8,
                review_count=124,
            ),
            PropertyDB(
                title="Cozy 1BR Near University",
                description="Perfect for students or young professionals. Walking distance to campus.",
                location="Bangalore, India",
                images=["/cozy.jpg"],
                property_type="apartment",
                bedrooms=1,
                beds=1,
                bathrooms=1.0,
                amenities=["WiFi", "AC", "Washing machine"],
                base_price=3000,
                cleaning_fee=300,
                deposit=10000,
                minimum_stay=2,
                rating=4.5,
                review_count=89,
            ),
            PropertyDB(
                title="Modern Skyline Apartment",
                description="High-rise apartment with stunning city views, pool, and gym access.",
                location="Mumbai, India",
                images=["/skyline.jpg"],
                property_type="apartment",
                bedrooms=2,
                beds=2,
                bathrooms=2.0,
                amenities=["WiFi", "AC", "Kitchen", "Pool", "Gym", "Parking"],
                base_price=8500,
                cleaning_fee=1200,
                deposit=30000,
                minimum_stay=3,
                rating=4.9,
                review_count=210,
            ),
        ]
        
        # Override the configs
        for i, p in enumerate(props):
            cfg = base_host_config.copy()
            
            # Setup ideal
            cfg["ideal_values"] = cfg["ideal_values"].copy()
            cfg["ideal_values"]["nightly_price"] = p.base_price
            cfg["ideal_values"]["total_price"] = p.base_price * p.minimum_stay
            cfg["ideal_values"]["deposit"] = p.deposit
            cfg["ideal_values"]["cleaning_fee"] = p.cleaning_fee
            
            # Setup acceptable
            cfg["acceptable_values"] = cfg["acceptable_values"].copy()
            cfg["acceptable_values"]["nightly_price"] = p.base_price * 0.8
            
            # Setup hard constraints
            cfg["hard_constraints"] = cfg["hard_constraints"].copy()
            cfg["hard_constraints"]["min_nightly_price"] = p.base_price * 0.8
            cfg["hard_constraints"]["min_stay_nights"] = p.minimum_stay
            
            p.negotiation_config = cfg
            
            session.add(p)
            
        await session.commit()
        print(f"Seeded {len(props)} properties.")

if __name__ == "__main__":
    asyncio.run(seed())
