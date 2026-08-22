"""SQLAlchemy ORM models for database persistence."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, relationship


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


class Base(DeclarativeBase):
    pass


class PropertyDB(Base):
    __tablename__ = "properties"

    id = Column(String(12), primary_key=True, default=_new_id)
    host_id = Column(String(12), nullable=True)  # Placeholder for host user ID
    title = Column(String(100), nullable=False)
    description = Column(Text, nullable=False)
    location = Column(String(200), nullable=False)  # Replaces 'address'
    images_json = Column(Text, nullable=False, default="[]")  # Replaces single 'image_url'
    property_type = Column(String(50), nullable=False, default="apartment")
    bedrooms = Column(Integer, default=1)
    beds = Column(Integer, default=1)
    bathrooms = Column(Float, default=1.0)
    amenities_json = Column(Text, nullable=False, default="[]")
    
    base_price = Column(Float, nullable=False, default=0.0)
    currency = Column(String(10), default="INR")
    cleaning_fee = Column(Float, default=0.0)
    deposit = Column(Float, default=0.0)
    minimum_stay = Column(Integer, default=1)
    maximum_stay = Column(Integer, default=30)
    
    rating = Column(Float, default=0.0)
    review_count = Column(Integer, default=0)

    # Host's private negotiation rules (must NEVER be sent to frontend)
    negotiation_config_json = Column(Text, nullable=False, default="{}")
    
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    @property
    def images(self) -> list:
        return json.loads(self.images_json) if self.images_json else []

    @images.setter
    def images(self, value: list) -> None:
        self.images_json = json.dumps(value)

    @property
    def amenities(self) -> list:
        return json.loads(self.amenities_json) if self.amenities_json else []

    @amenities.setter
    def amenities(self, value: list) -> None:
        self.amenities_json = json.dumps(value)

    @property
    def negotiation_config(self) -> dict:
        return json.loads(self.negotiation_config_json) if self.negotiation_config_json else {}

    @negotiation_config.setter
    def negotiation_config(self, value: dict) -> None:
        self.negotiation_config_json = json.dumps(value)


class BookingDB(Base):
    __tablename__ = "bookings"

    id = Column(String(12), primary_key=True, default=_new_id)
    property_id = Column(String(12), ForeignKey("properties.id"), nullable=False)
    negotiation_id = Column(String(12), ForeignKey("negotiations.id"), nullable=False, unique=True)
    guest_id = Column(String(12), nullable=True)
    
    status = Column(String(20), default="confirmed")  # confirmed, cancelled
    final_terms_json = Column(Text, nullable=False, default="{}")
    
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    @property
    def final_terms(self) -> dict:
        return json.loads(self.final_terms_json) if self.final_terms_json else {}


class NegotiationDB(Base):
    __tablename__ = "negotiations"

    id = Column(String(12), primary_key=True, default=_new_id)
    property_id = Column(String(12), ForeignKey("properties.id"), nullable=True)
    guest_id = Column(String(12), nullable=True)
    scenario = Column(String(20), nullable=False)
    status = Column(String(30), nullable=False, default="pending")
    config_json = Column(Text, nullable=False, default="{}")
    current_round = Column(Integer, default=0)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    # Relationships
    property_ref = relationship("PropertyDB")
    parties = relationship("PartyDB", back_populates="negotiation", cascade="all, delete-orphan")
    offers = relationship("OfferDB", back_populates="negotiation", cascade="all, delete-orphan", order_by="OfferDB.round_number")
    events = relationship("NegotiationEventDB", back_populates="negotiation", cascade="all, delete-orphan", order_by="NegotiationEventDB.timestamp")
    agreement = relationship("AgreementDB", back_populates="negotiation", uselist=False, cascade="all, delete-orphan")
    cost_records = relationship("CostTrackingDB", back_populates="negotiation", cascade="all, delete-orphan")

    @property
    def config(self) -> dict:
        return json.loads(self.config_json) if self.config_json else {}

    @config.setter
    def config(self, value: dict) -> None:
        self.config_json = json.dumps(value)


class PartyDB(Base):
    __tablename__ = "parties"

    id = Column(String(12), primary_key=True, default=_new_id)
    negotiation_id = Column(String(12), ForeignKey("negotiations.id"), nullable=False)
    role = Column(String(10), nullable=False)  # party_a or party_b
    name = Column(String(100), nullable=False)
    preferences_json = Column(Text, nullable=False, default="{}")

    negotiation = relationship("NegotiationDB", back_populates="parties")

    @property
    def preferences(self) -> dict:
        return json.loads(self.preferences_json) if self.preferences_json else {}

    @preferences.setter
    def preferences(self, value: dict) -> None:
        self.preferences_json = json.dumps(value)


class OfferDB(Base):
    __tablename__ = "offers"

    id = Column(String(12), primary_key=True, default=_new_id)
    negotiation_id = Column(String(12), ForeignKey("negotiations.id"), nullable=False)
    round_number = Column(Integer, nullable=False)
    party_role = Column(String(10), nullable=False)
    terms_json = Column(Text, nullable=False, default="{}")
    reasoning = Column(Text, default="")
    concessions_json = Column(Text, default="[]")
    requested_concessions_json = Column(Text, default="[]")
    validation_result = Column(String(10), default="pending")  # valid, invalid, pending
    validation_details = Column(Text, default="")
    created_at = Column(DateTime, default=_utcnow)

    negotiation = relationship("NegotiationDB", back_populates="offers")

    @property
    def terms(self) -> dict:
        return json.loads(self.terms_json) if self.terms_json else {}

    @property
    def concessions(self) -> list:
        return json.loads(self.concessions_json) if self.concessions_json else []

    @property
    def requested_concessions(self) -> list:
        return json.loads(self.requested_concessions_json) if self.requested_concessions_json else []


class NegotiationEventDB(Base):
    __tablename__ = "negotiation_events"

    id = Column(String(12), primary_key=True, default=_new_id)
    negotiation_id = Column(String(12), ForeignKey("negotiations.id"), nullable=False)
    event_type = Column(String(30), nullable=False)
    round_number = Column(Integer, default=0)
    data_json = Column(Text, default="{}")
    timestamp = Column(DateTime, default=_utcnow)

    negotiation = relationship("NegotiationDB", back_populates="events")

    @property
    def data(self) -> dict:
        return json.loads(self.data_json) if self.data_json else {}


class AgreementDB(Base):
    __tablename__ = "agreements"

    id = Column(String(12), primary_key=True, default=_new_id)
    negotiation_id = Column(String(12), ForeignKey("negotiations.id"), nullable=False, unique=True)
    final_terms_json = Column(Text, nullable=False, default="{}")
    party_a_satisfaction = Column(Float, default=0.0)
    party_b_satisfaction = Column(Float, default=0.0)
    fairness_score = Column(Float, default=0.0)
    constraint_violations = Column(Integer, default=0)
    total_rounds = Column(Integer, default=0)
    party_a_approved = Column(Boolean, default=None, nullable=True)
    party_b_approved = Column(Boolean, default=None, nullable=True)
    rejection_reason = Column(Text, default="")
    created_at = Column(DateTime, default=_utcnow)

    negotiation = relationship("NegotiationDB", back_populates="agreement")

    @property
    def final_terms(self) -> dict:
        return json.loads(self.final_terms_json) if self.final_terms_json else {}


class CostTrackingDB(Base):
    __tablename__ = "cost_tracking"

    id = Column(String(12), primary_key=True, default=_new_id)
    negotiation_id = Column(String(12), ForeignKey("negotiations.id"), nullable=False)
    round_number = Column(Integer, default=0)
    party_role = Column(String(10), default="")
    action = Column(String(30), default="")  # generate_offer, evaluate_offer
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    estimated_cost = Column(Float, default=0.0)
    latency_ms = Column(Float, default=0.0)
    model = Column(String(50), default="")
    created_at = Column(DateTime, default=_utcnow)

    negotiation = relationship("NegotiationDB", back_populates="cost_records")
