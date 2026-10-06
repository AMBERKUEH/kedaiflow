import argparse
import time
from datetime import timedelta
from zoneinfo import ZoneInfo
from fastapi import HTTPException
from sqlalchemy import select
from .config import settings
from .db import Session, transaction, migrate
from .models import *
from .security import Actor, aware
from . import domain as d


def claim_job():
    with transaction() as db:
        # Extract/read jobs can be retried. External sends must never be blindly replayed.
        abandoned = list(db.scalars(select(Job).where(Job.status == 'processing', Job.lease_until < now()).with_for_update(skip_locked=True)))
        for job in abandoned:
            if job.kind == 'execute_action':
                job.status, job.error = 'outcome_unknown', 'Worker lease expired during an external action; reconcile manually.'
                action = db.get(Action, job.record_id)
                if action and action.status == 'executing':
                    action.status, action.outcome = 'outcome_unknown', job.error
            else:
                job.status = 'queued' if job.attempts < 3 else 'dead_letter'
        job = db.scalar(select(Job).where(Job.status == 'queued', Job.available_at <= now()).order_by(Job.created_at).with_for_update(skip_locked=True).limit(1))
        if not job:
            return None
        job.status, job.attempts, job.lease_until = 'processing', job.attempts + 1, now() + timedelta(minutes=3)
        return d.serial(job)


def extract_job(job):
    from .ai import model_extract
    from .media import pdf_text
    with Session() as db:
        ev = db.get(Evidence, job['record_id'])
        if not ev or ev.business_id != job['business_id']:
            raise ValueError('Evidence unavailable')
        ev_data = d.serial(ev)
    media = (settings.media / ev_data['storage_key']).read_bytes() if ev_data['storage_key'] else None
    text = ev_data['text']
    pages = []
    if ev_data['media_type'] == 'application/pdf' and media:
        pages = pdf_text(media)
        text = '\n'.join(p['text'] for p in pages)[:30000]
    result = model_extract(text, ev_data['id'], media, ev_data['media_type'])
    if pages:
        result['pages'] = pages
    no_parse = not text and not (settings.gemini_key and settings.model_approved)
    with transaction(business_id=job['business_id']) as db:
        ev = db.get(Evidence, job['record_id'])
        ev.extraction = result
        ev.status = 'manual_entry_required' if no_parse else 'needs_review'
        db.get(Job, job['id']).status = 'completed'


def execute_job(job):
    from .telegram import TelegramClient, UnknownOutcome
    # Current role, binding, balance, digest and expiry are checked in the same
    # business transaction that reserves the external effect.
    with transaction(business_id=job['business_id']) as db:
        action = db.get(Action, job['record_id'])
        j = db.get(Job, job['id'])
        if not action or action.business_id != job['business_id'] or action.status != 'queued':
            j.status = 'canceled'
            return
        actor = Actor(action.approved_by or '', action.business_id, 'owner')
        try:
            recipient = d.check_action(db, actor, action)
            if action.approved_digest != action.payload_digest:
                raise ValueError('Approval digest does not match')
        except (HTTPException, ValueError):
            action.status, action.outcome, j.status = 'stale', 'Current permission or financial state invalidates approval.', 'canceled'
            return
        if settings.action_mode == 'draft':
            action.status, action.outcome, j.status = 'draft_only', 'External execution disabled by server configuration.', 'completed'
            return
        if settings.action_mode == 'simulation':
            if db.get(Business, action.business_id).mode != 'fixture':
                action.status, action.outcome, j.status = 'blocked', 'Simulation is permitted only in fixture businesses.', 'completed'
                return
            action.status, action.outcome, j.status = 'simulated_sent', 'Simulator recorded the approved message. No real customer was contacted.', 'completed'
            d.audit(db, actor, 'ActionSimulated', action)
            return
        if not recipient.binding_verified or not recipient.telegram_chat_id or not settings.telegram_token:
            action.status, action.outcome, j.status = 'blocked', 'Authenticated recipient binding and Telegram credentials required.', 'completed'
            return
        business = db.get(Business, actor.business_id)
        hour = now().astimezone(ZoneInfo(business.timezone)).hour
        quiet = (hour >= business.quiet_start or hour < business.quiet_end) if business.quiet_start > business.quiet_end else business.quiet_start <= hour < business.quiet_end
        if quiet:
            j.status, j.available_at = 'queued', now() + timedelta(minutes=30)
            return
        action.status = 'executing'
        chat_id, message, aid = recipient.telegram_chat_id, action.message, action.id
    # There is an unavoidable distributed race after the final check; preserve
    # the result and never claim that a send implies receipt or acceptance.
    try:
        result = TelegramClient().send(chat_id, message)
        status, outcome, external_id = 'telegram_accepted', 'Telegram API accepted message; reading/acceptance is unknown.', str(result['message_id'])
    except UnknownOutcome:
        status, outcome, external_id = 'outcome_unknown', 'Delivery may have occurred. Do not resend without independent review.', None
    except Exception:
        status, outcome, external_id = 'failed', 'Telegram rejected the send. Review connector and recipient.', None
    with transaction(business_id=job['business_id']) as db:
        action = db.get(Action, aid)
        action.status, action.outcome, action.external_id = status, outcome, external_id
        db.get(Job, job['id']).status = status
        d.audit(db, actor, 'ActionExecutionObserved', action, result=status)


def tick():
    job = claim_job()
    if not job:
        from .telegram import process_one
        return process_one()
    try:
        if job['kind'] == 'extract':
            extract_job(job)
        elif job['kind'] == 'execute_action':
            execute_job(job)
        else:
            raise ValueError('Unknown job kind')
    except Exception:
        with transaction(business_id=job['business_id']) as db:
            current = db.get(Job, job['id'])
            current.error = 'Processing failed. Source preserved; inspect configuration or enter data manually.'
            if current.kind == 'execute_action':
                current.status = 'outcome_unknown'
                action = db.get(Action, current.record_id)
                if action and action.status == 'executing':
                    action.status = 'outcome_unknown'
            else:
                current.status = 'queued' if current.attempts < 3 else 'dead_letter'
                current.available_at = now() + timedelta(seconds=2 ** current.attempts * 10)
    return True


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args()
    if settings.env != 'production':
        migrate()
    while True:
        did_work = tick()
        if args.once:
            break
        if not did_work:
            time.sleep(1)
