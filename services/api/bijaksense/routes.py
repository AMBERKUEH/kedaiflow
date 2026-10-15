from datetime import datetime
from decimal import Decimal
from typing import Literal
from fastapi import APIRouter, Request, Query, Response
from sqlalchemy import select, inspect, func
from ..models import Business, Deal, now
from ..security import resolve_actor, current_actor, require, scoped, fail, aware
from .models import *
from .schemas import ContextInput, CompetitorInput, FeedbackInput
from .config import CATEGORIES, COMMODITIES
from .connectors import public_url, Unavailable
from .engine import price_series
from .jobs import enqueue
from .retrieval import relevance


def serial(row):
    result = {}
    for col in inspect(type(row)).columns:
        if col.key == 'embedding':
            continue
        value = getattr(row, col.key)
        result[col.key] = aware(value).isoformat() if isinstance(value, datetime) else str(value) if isinstance(value, Decimal) else value
    return result


def signal_view(db, signal):
    source = db.scalar(select(SignalSource).where(SignalSource.business_id == signal.business_id, SignalSource.id == signal.source_id))
    return {**serial(signal), 'source': serial(source), 'freshness': 'fresh' if aware(signal.expires_at) > now() else 'stale', 'age_hours': round((now()-aware(signal.retrieved_at)).total_seconds()/3600, 1), 'publication_time_known': signal.published_at is not None}


def insight_view(db, insight):
    evidence = list(db.scalars(select(MarketSignal).where(MarketSignal.business_id == insight.business_id, MarketSignal.id.in_(insight.evidence_ids))))
    actions = list(db.scalars(select(RecommendedAction).where(RecommendedAction.business_id == insight.business_id, RecommendedAction.insight_id == insight.id)))
    context = db.get(MerchantContext, insight.business_id)
    current = context and context.enabled and aware(insight.assessed_at) >= aware(context.updated_at) and any(relevance(s, context) for s in evidence)
    return {**serial(insight), 'evidence': [signal_view(db, s) for s in evidence], 'actions': [serial(a) for a in actions], 'freshness': 'fresh' if current and evidence and all(aware(s.expires_at) > now() for s in evidence) else 'stale'}


def install(app, session_factory, transaction):
    router = APIRouter(prefix='/api/bijaksense', tags=['FLOW / BijakSense'])

    def actor(db, request, permission='read_finance'):
        result = resolve_actor(db, request)
        require(result, permission)
        return result

    @router.get('/overview')
    def overview(request: Request):
        with session_factory() as db:
            a = actor(db, request)
            context = db.get(MerchantContext, a.business_id)
            business = db.get(Business, a.business_id)
            latest = db.scalar(select(IngestionJob).where(IngestionJob.business_id == a.business_id).order_by(IngestionJob.created_at.desc()))
            refresh = db.scalar(select(IngestionJob).where(IngestionJob.business_id == a.business_id, IngestionJob.kind == 'refresh').order_by(IngestionJob.created_at.desc()))
            recent = list(db.scalars(select(MarketSignal).where(MarketSignal.business_id == a.business_id, MarketSignal.expires_at > now()).order_by(MarketSignal.retrieved_at.desc()).limit(2000)))
            counts = {c: sum(1 for s in recent if s.category == c and context and relevance(s, context)) for c in CATEGORIES}
            profile_products = []
            for deal in db.scalars(select(Deal).where(Deal.business_id == a.business_id, Deal.status == 'confirmed').limit(100)):
                profile_products += [i.get('product', '') for i in deal.terms.get('items', [])]
            statuses = refresh.result.get('categories', {}) if refresh else {}
            return {'merchant_id': a.business_id, 'merchant_name': business.name, 'financial_data_label': 'Sample merchant financial data' if business.mode == 'fixture' else 'Recorded merchant financial data', 'context': serial(context) if context else None, 'suggested_products_from_confirmed_deals': list(dict.fromkeys(profile_products))[:30], 'categories': [{'category': c, 'fresh_signals': counts[c], **statuses.get(c, {'status': 'not_refreshed'})} for c in CATEGORIES], 'last_job': serial(latest) if latest else None, 'as_of': now().isoformat(), 'commodity_options': [{'id': k, 'name': v[0]} for k,v in COMMODITIES.items()], 'can_manage': a.role == 'owner', 'summary': 'Source-backed observations and conditional business actions. Forecasts, international price proxies and incomplete coverage are labelled; no automatic stock or payment actions.'}

    @router.get('/context')
    def get_context(request: Request):
        with session_factory() as db:
            a = actor(db, request)
            row = db.get(MerchantContext, a.business_id)
            return serial(row) if row else None

    @router.post('/context')
    def set_context(payload: ContextInput, request: Request):
        with session_factory() as db:
            a = actor(db, request, 'admin')
        with transaction(business_id=a.business_id) as db:
            require(current_actor(db, a), 'admin')
            row = db.get(MerchantContext, a.business_id)
            if not row:
                row = MerchantContext(business_id=a.business_id)
                db.add(row)
            for k, v in payload.model_dump().items():
                setattr(row, k, v)
            row.updated_at = now()
            db.flush()
            return serial(row)

    @router.get('/signals')
    def signals(request: Request, category: Literal['supply_chain','commodities','weather','trends','competitors'] | None = None, limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0, le=10000), relevant_only: bool = True):
        with session_factory() as db:
            a = actor(db, request)
            q = select(MarketSignal).where(MarketSignal.business_id == a.business_id)
            if category:
                q = q.where(MarketSignal.category == category)
            context = db.get(MerchantContext, a.business_id)
            rows = list(db.scalars(q.order_by(MarketSignal.retrieved_at.desc()).limit(2000)))
            if relevant_only:
                rows = [s for s in rows if context and relevance(s, context)]
            return {'items': [signal_view(db, s) for s in rows[offset:offset+limit]]}

    @router.get('/signals/{signal_id}')
    def signal(signal_id: str, request: Request):
        with session_factory() as db:
            a = actor(db, request)
            return signal_view(db, scoped(db, MarketSignal, signal_id, a))

    @router.get('/commodities')
    def commodities(request: Request):
        with session_factory() as db:
            a = actor(db, request)
            context = db.get(MerchantContext, a.business_id)
            selected = context.commodities if context else []
            return {'items': [series for key in selected if (series := price_series(db, a.business_id, key))], 'unavailable': [key for key in selected if price_series(db, a.business_id, key) is None], 'notice': 'Monthly international USD benchmarks. No dated MYR FX source or local supplier price is assumed.'}

    @router.get('/weather')
    def weather(request: Request):
        return signals(request, 'weather', 100, 0)

    @router.get('/trends')
    def trends(request: Request):
        result = signals(request, 'trends', 100, 0)
        result['notice'] = 'National measured proxies and recorded invoice value are not proof of product demand. Internal comparison needs issued invoices in both completed 28-day windows.'
        return result

    @router.get('/competitors')
    def competitors(request: Request):
        with session_factory() as db:
            a = actor(db, request)
            profiles = list(db.scalars(select(CompetitorProfile).where(CompetitorProfile.business_id == a.business_id)))
            observations = list(db.scalars(select(CompetitorObservation).where(CompetitorObservation.business_id == a.business_id).order_by(CompetitorObservation.observed_at.desc()).limit(100)))
            return {'profiles': [serial(p) for p in profiles], 'observations': [{**serial(o), 'signal': signal_view(db, scoped(db, MarketSignal, o.signal_id, a))} for o in observations]}

    @router.post('/competitors')
    def add_competitor(payload: CompetitorInput, request: Request):
        try:
            public_url(payload.url)
        except (Unavailable, ValueError) as exc:
            fail('INVALID_PUBLIC_URL', 'Use a public HTTPS URL without credentials or a custom port.', 422)
        with session_factory() as db:
            a = actor(db, request, 'admin')
        with transaction(business_id=a.business_id) as db:
            require(current_actor(db, a), 'admin')
            if db.scalar(select(func.count()).select_from(CompetitorProfile).where(CompetitorProfile.business_id == a.business_id)) >= 10:
                fail('COMPETITOR_LIMIT', 'Up to ten competitor sources per merchant.', 422)
            row = CompetitorProfile(business_id=a.business_id, **payload.model_dump())
            db.add(row)
            db.flush()
            return serial(row)

    @router.post('/competitors/{competitor_id}/disable')
    def disable_competitor(competitor_id: str, request: Request):
        with session_factory() as db:
            a = actor(db, request, 'admin')
        with transaction(business_id=a.business_id) as db:
            require(current_actor(db, a), 'admin')
            row = scoped(db, CompetitorProfile, competitor_id, a)
            row.enabled = False
            return serial(row)

    @router.get('/insights')
    def insights(request: Request, limit: int = Query(40, ge=1, le=100)):
        with session_factory() as db:
            a = actor(db, request)
            rows = list(db.scalars(select(MarketInsight).where(MarketInsight.business_id == a.business_id).order_by(MarketInsight.assessed_at.desc()).limit(limit)))
            return {'items': [insight_view(db, row) for row in rows]}

    @router.post('/insights/{insight_id}/feedback')
    def feedback(insight_id: str, payload: FeedbackInput, request: Request):
        with session_factory() as db:
            a = actor(db, request)
        with transaction(business_id=a.business_id) as db:
            require(current_actor(db, a), 'read_finance')
            row = scoped(db, MarketInsight, insight_id, a)
            row.status, row.feedback = payload.status, payload.note
            return serial(row)

    def queue(request, response, kind):
        with session_factory() as db:
            a = actor(db, request, 'admin')
        with transaction(business_id=a.business_id) as db:
            require(current_actor(db, a), 'admin')
            context = db.get(MerchantContext, a.business_id)
            if not context or not context.enabled:
                fail('PROFILE_REQUIRED', 'Save and enable your merchant intelligence profile first.', 422)
            job, created = enqueue(db, a.business_id, kind)
            if not created and job.status not in ('queued', 'running'):
                fail('REFRESH_RATE_LIMIT', 'Refresh and analysis share a 15-minute limit. Existing evidence remains available.', 429)
            response.status_code = 202
            return {'job': serial(job), 'created': created}

    @router.post('/refresh')
    def refresh(request: Request, response: Response):
        return queue(request, response, 'refresh')

    @router.post('/analyze')
    def analyze(request: Request, response: Response):
        return queue(request, response, 'analyze')

    @router.get('/jobs/{job_id}')
    def job(job_id: str, request: Request):
        with session_factory() as db:
            a = actor(db, request)
            return serial(scoped(db, IngestionJob, job_id, a))

    app.include_router(router)
