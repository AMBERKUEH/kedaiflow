"""Durable refresh queue and scheduler, run separately from capture/Telegram work."""
import argparse
import time
from datetime import timedelta
from sqlalchemy import select, or_
from .. import db as database
from ..models import Business, now
from ..security import aware
from .models import MerchantContext, IngestionJob, CompetitorProfile
from . import connectors, engine
from .config import CATEGORIES, option


def transaction(bid=None):
    return database.transaction(factory=database.Session, business_id=bid)


def enqueue(db, bid, kind='refresh'):
    cutoff = now() - timedelta(minutes=15)
    previous = db.scalar(select(IngestionJob).where(IngestionJob.business_id == bid, IngestionJob.created_at >= cutoff).order_by(IngestionJob.created_at.desc()))
    if previous:
        return previous, False
    job = IngestionJob(business_id=bid, kind=kind, bucket=str(int(now().timestamp()) // 900))
    db.add(job)
    db.flush()
    return job, True


def schedule():
    if option('SCHEDULE_ENABLED', 'true') != 'true':
        return
    with database.Session() as db:
        ids = list(db.scalars(select(MerchantContext.business_id).where(MerchantContext.enabled.is_(True))))
    interval = max(1, int(option('REFRESH_HOURS', '6')))
    for bid in ids:
        with transaction(bid) as db:
            latest = db.scalar(select(IngestionJob).where(IngestionJob.business_id == bid, IngestionJob.kind == 'refresh').order_by(IngestionJob.created_at.desc()))
            if not latest or aware(latest.created_at) < now()-timedelta(hours=interval):
                enqueue(db, bid)


def claim():
    with transaction() as db:
        expired = list(db.scalars(select(IngestionJob).where(IngestionJob.status == 'running', IngestionJob.started_at < now()-timedelta(minutes=20))))
        for job in expired:
            job.status, job.completed_at, job.result = 'failed', now(), {'error': 'Worker interrupted; partial evidence preserved. No automatic paid retry.'}
        query = select(IngestionJob).where(IngestionJob.status == 'queued').order_by(IngestionJob.created_at).limit(1)
        if db.bind.dialect.name != 'sqlite':
            query = query.with_for_update(skip_locked=True)
        job = db.scalar(query)
        if not job:
            return None
        job.status, job.started_at = 'running', now()
        return job.id, job.business_id, job.kind


def run_job(job_id, bid, kind):
    with database.Session() as db:
        context = db.get(MerchantContext, bid)
        if not context or not context.enabled:
            raise connectors.Unavailable('Complete and enable the merchant intelligence profile first.')
        profile_revision = context.updated_at
        competitors = list(db.scalars(select(CompetitorProfile).where(CompetitorProfile.business_id == bid, CompetitorProfile.enabled.is_(True)).limit(10)))
    status = {}
    if kind == 'refresh':
        handlers = {'supply_chain': connectors.news, 'commodities': connectors.commodities, 'weather': connectors.weather, 'trends': connectors.trends}
        for category, handler in handlers.items():
            try:
                items = handler(context)
                with transaction(bid) as db:
                    for item in items:
                        engine.persist(db, bid, item)
                status[category] = {'status': 'ok' if items else 'no_data', 'count': len(items), 'checked_at': now().isoformat()}
            except Exception as exc:
                status[category] = {'status': 'unavailable', 'message': str(exc) if isinstance(exc, connectors.Unavailable) else 'Provider response could not be validated; no data invented.', 'checked_at': now().isoformat()}
            with transaction(bid) as db:
                db.get(IngestionJob, job_id).result = {'categories': dict(status)}
        count, problems = 0, []
        for profile in competitors:
            try:
                items = connectors.competitor(profile)
                with transaction(bid) as db:
                    for item in items:
                        engine.persist(db, bid, item)
                count += len(items)
                message = 'ok' if items else 'No public observations found'
            except Exception as exc:
                message = str(exc) if isinstance(exc, connectors.Unavailable) else 'Public source could not be validated.'
                problems.append({'competitor_id': profile.id, 'message': message})
            with transaction(bid) as db:
                row = db.get(CompetitorProfile, profile.id)
                row.last_status, row.last_checked_at = message, now()
        status['competitors'] = {'status': 'ok' if count else 'unavailable' if competitors else 'not_configured', 'count': count, 'problems': problems, 'message': '' if competitors else 'Add your competitors and their public source URLs.', 'checked_at': now().isoformat()}
    with database.Session() as db:
        context = db.get(MerchantContext, bid)
        options, retrieval_mode = engine.candidates(db, context)
        financial = engine.financial_context(db, bid)
        db.commit()  # Persistent embeddings, internal measurement evidence.
    selected, generator = engine.recommend(options, context, financial)
    with transaction(bid) as db:
        current = db.get(MerchantContext, bid)
        if current.updated_at != profile_revision or not current.enabled:
            raise connectors.Unavailable('Merchant profile changed during analysis; refresh again for the new context.')
        ids = engine.save_insights(db, bid, selected, generator, retrieval_mode)
        job = db.get(IngestionJob, job_id)
        job.status, job.completed_at = 'completed', now()
        job.result = {'categories': status, 'insight_ids': ids, 'retrieval_mode': retrieval_mode, 'recommendation_engine': generator, 'financial_context': financial}


def tick():
    item = claim()
    if not item:
        return False
    try:
        run_job(*item)
    except Exception as exc:
        with transaction(item[1]) as db:
            job = db.get(IngestionJob, item[0])
            job.status, job.completed_at = 'failed', now()
            job.result = {**job.result, 'error': str(exc) if isinstance(exc, connectors.Unavailable) else 'Analysis could not be completed. Existing evidence remains available.'}
    return True


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args()
    database.migrate()
    last_schedule = 0
    while True:
        if time.monotonic()-last_schedule > 60:
            schedule()
            last_schedule = time.monotonic()
        worked = tick()
        if args.once:
            break
        if not worked:
            time.sleep(2)
