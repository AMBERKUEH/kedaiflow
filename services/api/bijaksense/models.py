from datetime import datetime
from sqlalchemy import String, Text, JSON, DateTime, Boolean, Float, Numeric, UniqueConstraint, ForeignKeyConstraint
from sqlalchemy.orm import Mapped, mapped_column
from ..models import Base, TenantRecord, now


class MerchantContext(Base):
    __tablename__ = 'flow_merchant_contexts'
    business_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    industry: Mapped[str] = mapped_column(String(80), default='')
    location: Mapped[str] = mapped_column(String(120), default='')
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    products: Mapped[list] = mapped_column(JSON, default=list)
    materials: Mapped[list] = mapped_column(JSON, default=list)
    markets: Mapped[list] = mapped_column(JSON, default=lambda: ['Malaysia'])
    commodities: Mapped[list] = mapped_column(JSON, default=list)
    cost_categories: Mapped[dict] = mapped_column(JSON, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class SignalSource(TenantRecord, Base):
    __tablename__ = 'flow_signal_sources'
    __table_args__ = (UniqueConstraint('business_id', 'id'), UniqueConstraint('business_id', 'url'))
    name: Mapped[str] = mapped_column(String(180))
    url: Mapped[str] = mapped_column(Text)
    provider: Mapped[str] = mapped_column(String(60))
    reliability: Mapped[str] = mapped_column(String(40))
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class MarketSignal(TenantRecord, Base):
    __tablename__ = 'flow_market_signals'
    __table_args__ = (UniqueConstraint('business_id', 'id'), UniqueConstraint('business_id', 'fingerprint'),
        ForeignKeyConstraint(['business_id', 'source_id'], ['flow_signal_sources.business_id', 'flow_signal_sources.id']))
    category: Mapped[str] = mapped_column(String(30), index=True)
    source_id: Mapped[str] = mapped_column(String(64))
    fingerprint: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(500))
    text: Mapped[str] = mapped_column(Text)
    geography: Mapped[list] = mapped_column(JSON, default=list)
    tags: Mapped[list] = mapped_column(JSON, default=list)
    basis: Mapped[str] = mapped_column(String(40))
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    embedding: Mapped[list] = mapped_column(JSON, default=list)
    embedding_model: Mapped[str] = mapped_column(String(180), default='')


class CommodityPriceObservation(TenantRecord, Base):
    __tablename__ = 'flow_commodity_prices'
    __table_args__ = (UniqueConstraint('business_id', 'commodity', 'observed_at', 'currency', 'unit', 'location'),
        ForeignKeyConstraint(['business_id', 'signal_id'], ['flow_market_signals.business_id', 'flow_market_signals.id']))
    signal_id: Mapped[str] = mapped_column(String(64))
    commodity: Mapped[str] = mapped_column(String(60))
    value: Mapped[float] = mapped_column(Numeric(24, 8))
    currency: Mapped[str] = mapped_column(String(3))
    unit: Mapped[str] = mapped_column(String(30))
    original_value: Mapped[str] = mapped_column(String(60))
    original_unit: Mapped[str] = mapped_column(String(40))
    location: Mapped[str] = mapped_column(String(120))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    is_proxy: Mapped[bool] = mapped_column(Boolean, default=True)


class CompetitorProfile(TenantRecord, Base):
    __tablename__ = 'flow_competitors'
    __table_args__ = (UniqueConstraint('business_id', 'id'), UniqueConstraint('business_id', 'url'))
    name: Mapped[str] = mapped_column(String(120))
    url: Mapped[str] = mapped_column(Text)
    source_type: Mapped[str] = mapped_column(String(20), default='website')
    public_access_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_status: Mapped[str] = mapped_column(String(180), default='not_checked')
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CompetitorObservation(TenantRecord, Base):
    __tablename__ = 'flow_competitor_observations'
    __table_args__ = (UniqueConstraint('business_id', 'competitor_id', 'content_hash'),
        ForeignKeyConstraint(['business_id', 'competitor_id'], ['flow_competitors.business_id', 'flow_competitors.id']),
        ForeignKeyConstraint(['business_id', 'signal_id'], ['flow_market_signals.business_id', 'flow_market_signals.id']))
    competitor_id: Mapped[str] = mapped_column(String(64))
    signal_id: Mapped[str] = mapped_column(String(64))
    content_hash: Mapped[str] = mapped_column(String(64))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    kind: Mapped[str] = mapped_column(String(30))
    advertised_prices: Mapped[list] = mapped_column(JSON, default=list)


class MarketInsight(TenantRecord, Base):
    __tablename__ = 'flow_market_insights'
    __table_args__ = (UniqueConstraint('business_id', 'id'), UniqueConstraint('business_id', 'fingerprint'))
    fingerprint: Mapped[str] = mapped_column(String(64))
    category: Mapped[str] = mapped_column(String(30))
    kind: Mapped[str] = mapped_column(String(30))
    title: Mapped[str] = mapped_column(String(500))
    explanation: Mapped[str] = mapped_column(Text)
    uncertainty: Mapped[str] = mapped_column(Text)
    evidence_ids: Mapped[list] = mapped_column(JSON)
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    relevance: Mapped[dict] = mapped_column(JSON, default=dict)
    generator: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(30), default='new')
    feedback: Mapped[str] = mapped_column(Text, default='')
    assessed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class RecommendedAction(TenantRecord, Base):
    __tablename__ = 'flow_recommended_actions'
    __table_args__ = (ForeignKeyConstraint(['business_id', 'insight_id'], ['flow_market_insights.business_id', 'flow_market_insights.id']),)
    insight_id: Mapped[str] = mapped_column(String(64))
    code: Mapped[str] = mapped_column(String(60))
    text: Mapped[str] = mapped_column(Text)


class IngestionJob(TenantRecord, Base):
    __tablename__ = 'flow_ingestion_jobs'
    __table_args__ = (UniqueConstraint('business_id', 'kind', 'bucket'),)
    kind: Mapped[str] = mapped_column(String(20))
    bucket: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(30), default='queued', index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
