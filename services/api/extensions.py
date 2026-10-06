"""Supporting workflows. External capabilities fail closed when unavailable."""
import secrets
from datetime import timedelta
from fastapi import Request
from pydantic import Field
from sqlalchemy import select
from . import schemas as s, domain as d
from .models import *
from .security import Actor, require, scoped, fail, token_hash, digest, resolve_actor, aware


class Reason(s.Model):
    reason: str = Field(min_length=3, max_length=1000)


class LinkInvoice(s.Model):
    invoice_id: str
    expected_version: s.Version
    reason: str = Field(min_length=3, max_length=1000)


class Notification(s.Model):
    package_name: str = Field(max_length=200)
    source_event_id: str = Field(min_length=1, max_length=150)
    text: str = Field(min_length=1, max_length=1000)
    occurred_at: str = Field(max_length=40)


class Device(s.Model):
    name: str = Field(min_length=1, max_length=100)
    allowed_packages: list[str] = Field(min_length=1, max_length=10)


class RecipientConfirm(s.Expected):
    observed_chat_id: str = Field(min_length=1, max_length=40)
    reason: str = Field(min_length=3, max_length=1000)


def install(app, command, Session, transaction):
    @app.get('/v1/cases/{record_id}/evidence')
    def case_evidence(record_id: str, request: Request):
        with Session() as db:
            actor = resolve_actor(db, request)
            require(actor, 'read_finance')
            case = scoped(db, Case, record_id, actor)
            result = {'case': d.serial(case), 'records': [], 'rule_version': 'v1', 'coverage': 'Recorded business sources only'}
            if case.rule == 'delivered_unbilled':
                delivery = scoped(db, Delivery, case.record_id, actor)
                deal = scoped(db, Deal, delivery.deal_id, actor)
                result['records'] = [{'type':'delivery', **d.serial(delivery)}, {'type':'deal', **d.serial(deal)}]
                for eid in deal.evidence_ids:
                    ev = scoped(db, Evidence, eid, actor)
                    result['records'].append({'type':'evidence', **{k:v for k,v in d.serial(ev).items() if k!='storage_key'}})
            elif case.rule == 'unapplied_receipt':
                receipt = scoped(db, Receipt, case.record_id, actor)
                result['records'] = [{'type':'receipt', **d.serial(receipt), 'unapplied_minor': d.available(db,receipt)}]
            else:
                invoice = scoped(db, Invoice, case.record_id, actor)
                result['records'] = [{'type':'invoice', **d.invoice_view(db,invoice)}]
                for allocation in d.rows(db,Allocation,actor):
                    if allocation.invoice_id==invoice.id:
                        result['records'].append({'type':'allocation', **d.serial(allocation)})
                for claim in d.rows(db,Claim,actor):
                    if claim.invoice_id==invoice.id:
                        result['records'].append({'type':'claim', **d.serial(claim)})
            return result

    @app.post('/v1/counterparties/{record_id}/telegram-invite')
    def recipient_invite(record_id: str, request: Request):
        def run(db, actor, _):
            require(actor, 'admin')
            party = scoped(db, Counterparty, record_id, actor)
            token = secrets.token_urlsafe(24)
            invite = d.add(db, RecipientInvite, actor, token_hash=token_hash(token), counterparty_id=party.id, expires_at=now()+timedelta(hours=24))
            d.audit(db, actor, 'RecipientInvitePrepared', invite)
            return {'id': invite.id, 'recipient': party.name, 'instruction': '/connect ' + token, 'expires_at': d.serial(invite)['expires_at'], 'note': 'Share manually with the intended recipient. After they connect, independently verify their identity and approve the exact chat ID.'}
        return command(request, {}, 'recipient-invite:' + record_id, run)

    @app.get('/v1/channels/telegram/recipient-invites')
    def recipient_invites(request: Request):
        with Session() as db:
            actor = resolve_actor(db, request)
            require(actor, 'admin')
            return {'items': [{k:v for k,v in d.serial(row).items() if k != 'token_hash'} for row in d.rows(db, RecipientInvite, actor)]}

    @app.post('/v1/channels/telegram/recipient-invites/{record_id}/confirm')
    def confirm_recipient(record_id: str, payload: RecipientConfirm, request: Request):
        def run(db, actor, data):
            require(actor, 'admin')
            invite = scoped(db, RecipientInvite, record_id, actor)
            d.version(invite, data['expected_version'])
            if invite.status != 'owner_review_required' or not invite.chat_id or invite.chat_id != data['observed_chat_id'] or aware(invite.expires_at) <= now():
                fail('RECIPIENT_NOT_VERIFIED', 'Confirm the current pending chat and independently verify the intended person.')
            party = scoped(db, Counterparty, invite.counterparty_id, actor)
            party.telegram_chat_id, party.binding_verified = invite.chat_id, True
            party.version += 1
            for prior in d.rows(db, RecipientInvite, actor):
                if prior.counterparty_id == party.id and prior.id != invite.id:
                    prior.status = 'superseded'
            invite.status, invite.version = 'confirmed', invite.version + 1
            for action in d.rows(db, Action, actor):
                if action.recipient_id == party.id and action.status in ('approval_required','queued'):
                    action.status, action.outcome = 'stale', 'Recipient binding changed. Review a fresh action.'
            d.audit(db, actor, 'RecipientBindingConfirmed', invite, reason=data['reason'], chat_id=invite.chat_id)
            return {'id': party.id, 'binding_verified': True, 'version': party.version}
        return command(request, payload, 'recipient-confirm:' + record_id, run)

    @app.get('/v1/reconciliation/proposals')
    def proposals(request: Request):
        with Session() as db:
            actor = resolve_actor(db, request)
            require(actor, 'read_finance')
            invoices = d.rows(db, Invoice, actor)
            result = []
            for receipt in d.rows(db, Receipt, actor):
                if d.available(db, receipt) <= 0 or receipt.category not in ('customer_receipt', 'supplier_payment'):
                    continue
                candidates = []
                for invoice in invoices:
                    if invoice.status != 'issued' or invoice.disputed or invoice.currency != receipt.currency or (invoice.direction == 'receivable') != (receipt.direction == 'in') or d.outstanding(db, invoice) <= 0:
                        continue
                    reasons = []
                    if invoice.number.lower() in receipt.reference.lower():
                        reasons.append('Invoice reference occurs in receipt reference')
                    if d.outstanding(db, invoice) == d.available(db, receipt):
                        reasons.append('Exact amount; does not establish payer identity')
                    if reasons:
                        candidates.append({'invoice_id': invoice.id, 'invoice_version': invoice.version, 'outstanding_minor': d.outstanding(db, invoice), 'reasons': reasons})
                result.append({'receipt_id': receipt.id, 'receipt_version': receipt.version, 'available_minor': d.available(db, receipt), 'candidates': candidates, 'ambiguous': len(candidates) != 1, 'auto_match': False, 'policy': 'Explicit human review required; match precision not calibrated'})
            return {'items': result}

    @app.post('/v1/jobs/{record_id}/retry')
    def retry(record_id: str, payload: Reason, request: Request):
        def run(db, actor, data):
            require(actor, 'write_finance')
            job = scoped(db, Job, record_id, actor)
            if job.kind != 'extract' or job.status not in ('dead_letter', 'completed'):
                fail('RETRY_UNSAFE', 'Only extraction jobs can be retried. External outcomes require reconciliation.')
            job.status, job.attempts, job.available_at = 'queued', 0, now()
            job.version += 1
            d.audit(db, actor, 'ExtractionRetryRequested', job, reason=data['reason'])
            return d.serial(job)
        return command(request, payload, 'retry:' + record_id, run)

    @app.post('/v1/cases/detect')
    def detect(request: Request):
        def run(db, actor, _):
            require(actor, 'write_finance')
            d.detect_cases(db, actor)
            return {'items': [d.serial(r) for r in d.rows(db, Case, actor)]}
        return command(request, {}, 'detect', run)

    @app.post('/v1/cases/{record_id}/link-invoice')
    def link_invoice(record_id: str, payload: LinkInvoice, request: Request):
        def run(db, actor, data):
            require(actor, 'write_finance')
            case = scoped(db, Case, record_id, actor)
            d.version(case, data['expected_version'])
            if case.rule != 'delivered_unbilled':
                fail('CASE_TYPE', 'This case is not a delivery-to-invoice gap.')
            delivery = scoped(db, Delivery, case.record_id, actor)
            deal = scoped(db, Deal, delivery.deal_id, actor)
            invoice = scoped(db, Invoice, data['invoice_id'], actor)
            if invoice.status != 'issued' or invoice.counterparty_id != deal.counterparty_id or invoice.total_minor != deal.total_minor or invoice.deal_id not in (None, deal.id):
                fail('INVOICE_MISMATCH', 'Review a matching issued invoice for this deal and counterparty.')
            invoice.deal_id, invoice.deal_version = deal.id, deal.version
            invoice.version += 1
            d.audit(db, actor, 'InvoiceLinkedToDelivery', invoice, case_id=case.id, reason=data['reason'])
            d.invalidate_reminders(db, actor, invoice)
            return d.serial(case)
        return command(request, payload, 'link-invoice:' + record_id, run)

    @app.post('/v1/einvoices/{record_id}/validate')
    def validate_einvoice(record_id: str, request: Request):
        def run(db, actor, _):
            require(actor, 'write_finance')
            record = scoped(db, Supplement, record_id, actor)
            if record.kind != 'einvoice' or record.status != 'draft':
                fail('EINVOICE_STATE', 'Only draft e-Invoices can be checked locally.')
            invoice = scoped(db, Invoice, record.data['invoice_id'], actor)
            if invoice.status != 'issued' or invoice.version != record.data['invoice_version']:
                fail('INVOICE_CHANGED', 'Draft must reference the current issued invoice.')
            if record.data['missing_fields']:
                fail('IDENTIFIERS_REQUIRED', 'Enter real seller and buyer identifiers in a new draft.', 422)
            record.status, record.version = 'local_fields_checked', record.version + 1
            record.data = {**record.data, 'check_scope': 'Application identifiers and invoice version only; official UBL/tax validation remains a provider gate'}
            d.audit(db, actor, 'EInvoiceLocalFieldsChecked', record)
            return d.serial(record)
        return command(request, {}, 'einvoice-check:' + record_id, run)

    @app.post('/v1/einvoices/{record_id}/submit')
    def submit_einvoice(record_id: str, request: Request):
        def run(db, actor, _):
            require(actor, 'approve')
            record = scoped(db, Supplement, record_id, actor)
            if record.kind != 'einvoice' or record.status != 'local_fields_checked':
                fail('EINVOICE_STATE', 'Review local fields before requesting submission.')
            fail('MYINVOIS_UNAVAILABLE', 'MyInvois adapter and taxpayer authorization are not configured. Draft retained; nothing submitted.', 503)
        return command(request, {}, 'einvoice-submit:' + record_id, run)

    @app.post('/v1/android/devices')
    def device(payload: Device, request: Request):
        def run(db, actor, data):
            require(actor, 'admin')
            token = secrets.token_urlsafe(40)
            record = d.add(db, Supplement, actor, kind='android_device', status='active', data={**data, 'token_hash': token_hash(token), 'owner_id': actor.user_id})
            d.audit(db, actor, 'AndroidDeviceAuthorized', record)
            return {'device_id': record.id, 'token': token, 'scope': 'notification_claims_only', 'warning': 'Store on the device in encrypted storage. Token cannot access financial read/write endpoints.'}
        return command(request, payload, 'android-device', run)

    @app.post('/v1/android/notifications')
    def notification(payload: Notification, request: Request):
        token = request.headers.get('x-device-token', '')
        if not token:
            fail('DEVICE_REQUIRED', 'Device authentication required.', 401)
        with Session() as db:
            devices = db.scalars(select(Supplement).where(Supplement.kind == 'android_device', Supplement.status == 'active'))
            device = next((r for r in devices if secrets.compare_digest(r.data['token_hash'], token_hash(token))), None)
            if not device:
                fail('DEVICE_INVALID', 'Device authentication failed.', 401)
            bid, device_id, owner_id = device.business_id, device.id, device.data['owner_id']
        with transaction(business_id=bid) as db:
            member = db.get(Membership, (bid, owner_id))
            if not member or not member.active or member.role != 'owner':
                fail('DEVICE_REVOKED', 'Authorizing owner is no longer active.', 403)
            device = db.get(Supplement, device_id)
            if device.status != 'active' or payload.package_name not in device.data['allowed_packages']:
                fail('PACKAGE_DENIED', 'This payment source is not enabled.', 403)
            if any(word in payload.text.lower() for word in ('otp', 'one-time', 'verification code', '验证码', 'tac')):
                fail('PRIVATE_CONTENT', 'Authentication notifications are excluded.', 422)
            actor = Actor(owner_id, bid, 'owner')
            key = digest({'device_id': device_id, 'event_id': payload.source_event_id})
            previous = db.get(Operation, ('android:' + device_id, key))
            payload_hash = digest(payload.model_dump())
            if previous:
                if previous.digest != payload_hash:
                    fail('NOTIFICATION_REVISION', 'Notification changed. Retain prior claim and review a linked correction.')
                return previous.result
            result = d.create_evidence(db, actor, {'text': payload.text, 'kind': 'notification', 'invoice_id': None, 'claimed_minor': None})
            db.add(Operation(scope='android:' + device_id, key=key, digest=payload_hash, result=result))
            return result

    @app.post('/v1/android/devices/{record_id}/revoke')
    def revoke_device(record_id: str, payload: Reason, request: Request):
        def run(db, actor, data):
            require(actor, 'admin')
            record = scoped(db, Supplement, record_id, actor)
            if record.kind != 'android_device':
                fail('NOT_FOUND', 'Device not found.', 404)
            record.status = 'revoked'
            d.audit(db, actor, 'AndroidDeviceRevoked', record, reason=data['reason'])
            return {'id': record.id, 'status': record.status}
        return command(request, payload, 'device-revoke:' + record_id, run)

    @app.get('/v1/operations/health')
    def operations_health(request: Request):
        with Session() as db:
            actor = resolve_actor(db, request)
            require(actor, 'admin')
            jobs = d.rows(db, Job, actor)
            return {'queued': sum(j.status == 'queued' for j in jobs), 'processing': sum(j.status == 'processing' for j in jobs), 'dead_letter': sum(j.status == 'dead_letter' for j in jobs), 'unknown': sum(j.status == 'outcome_unknown' for j in jobs), 'source_as_of': now().isoformat(), 'external_effects_paused': db.get(Business, actor.business_id).paused}
