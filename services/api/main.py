import csv
import io
import json
import secrets
import time
from contextlib import asynccontextmanager
from datetime import date, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo
from pathlib import Path
from collections import defaultdict, deque
from fastapi import FastAPI, Request, Response, UploadFile, File, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from . import schemas as s, domain as d
from .config import settings
from .db import Session, migrate, transaction
from .models import *
from .security import *


@asynccontextmanager
async def lifespan(app):
    if settings.env != 'production':
        migrate()
    yield


app = FastAPI(title='KedaiFlow API', version='0.1.0', lifespan=lifespan, description='Operational finance, explicit evidence and exact approvals. All money is integer sen. No payment initiation.')
app.add_middleware(CORSMiddleware, allow_origins=[settings.web_origin], allow_credentials=True, allow_methods=['GET', 'POST'], allow_headers=['Content-Type', 'Authorization', 'X-Business-Id', 'Idempotency-Key'])
auth_attempts = defaultdict(deque)


@app.middleware('http')
async def boundaries(request, call_next):
    trace_id = secrets.token_hex(12)
    if request.method not in ('GET', 'HEAD', 'OPTIONS'):
        origin = request.headers.get('origin')
        if origin and origin != settings.web_origin:
            return JSONResponse(status_code=403, content={'error': {'code': 'ORIGIN_DENIED', 'message': 'Untrusted request origin.'}})
    response = await call_next(request)
    response.headers['X-Request-Id'] = trace_id
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Cache-Control'] = 'no-store'
    return response


@app.exception_handler(HTTPException)
async def errors(_, exc):
    return JSONResponse(status_code=exc.status_code, content={'error': exc.detail if isinstance(exc.detail, dict) else {'code': 'REQUEST_FAILED', 'message': exc.detail}})


@app.exception_handler(IntegrityError)
async def conflicts(_, exc):
    return JSONResponse(status_code=409, content={'error': {'code': 'CONSTRAINT_CONFLICT', 'message': 'A record already exists or a relationship is invalid. Refresh and retry.'}})


def actor_from(request):
    with Session() as db:
        return resolve_actor(db, request)


def command(request, payload, operation, handler):
    actor = actor_from(request)
    key = request.headers.get('idempotency-key', '')
    if not 8 <= len(key) <= 150:
        fail('IDEMPOTENCY_REQUIRED', 'Supply an Idempotency-Key of 8–150 characters.', 422)
    data = payload.model_dump() if hasattr(payload, 'model_dump') else payload
    hashed = digest(data)
    scope = f'{actor.business_id}:{actor.user_id}:{actor.role}:{operation}'
    with transaction(business_id=actor.business_id) as db:
        actor = current_actor(db, actor)
        prior = db.get(Operation, (scope, key))
        if prior:
            if prior.digest != hashed:
                fail('IDEMPOTENCY_CONFLICT', 'This operation key was already used with different content.')
            return prior.result
        result = handler(db, actor, data)
        # Canonical JSON serialization for dates and DB replay parity.
        result = json.loads(json.dumps(result, default=str))
        db.add(Operation(scope=scope, key=key, digest=hashed, result=result))
        return result


def throttle(request):
    key = request.client.host if request.client else 'unknown'
    attempts = auth_attempts[key]
    while attempts and attempts[0] < time.monotonic() - 60:
        attempts.popleft()
    if len(attempts) >= 20:
        fail('RATE_LIMITED', 'Too many sign-in attempts. Try again in a minute.', 429)
    attempts.append(time.monotonic())


def session_response(db, identity, response):
    token = secrets.token_urlsafe(40)
    db.add(SessionToken(token_hash=token_hash(token), user_id=identity.id, expires_at=now() + timedelta(hours=12)))
    response.set_cookie('kf_session', token, httponly=True, secure=settings.env == 'production', samesite='strict', max_age=43200, path='/')
    return {'user': {'id': identity.id, 'name': identity.name, 'email': identity.email}}


@app.get('/healthz')
def health():
    with Session() as db:
        db.execute(text('SELECT 1'))
    return {'status': 'ok', 'environment': settings.env, 'data_mode': settings.data_mode}


@app.post('/v1/auth/register')
def register(payload: s.Register, request: Request, response: Response):
    throttle(request)
    if settings.auth_mode != 'local':
        fail('USE_IDENTITY_PROVIDER', 'Use the configured Supabase identity provider.', 403)
    with transaction() as db:
        identity = Identity(email=payload.email.lower(), password_hash=passwords.hash(payload.password), name=payload.name)
        db.add(identity)
        business = Business(name=payload.business_name, language=payload.language, mode='imported')
        db.add(business)
        db.flush()
        db.add(Membership(business_id=business.id, user_id=identity.id, role='owner'))
        return session_response(db, identity, response)


@app.post('/v1/auth/login')
def login(payload: s.Login, request: Request, response: Response):
    throttle(request)
    if settings.auth_mode != 'local':
        fail('USE_IDENTITY_PROVIDER', 'Use Supabase sign-in.', 403)
    with transaction() as db:
        identity = db.scalar(select(Identity).where(Identity.email == payload.email.lower()))
        try:
            passwords.verify(identity.password_hash if identity else passwords.hash('no-valid-account'), payload.password)
        except Exception:
            fail('INVALID_CREDENTIALS', 'Email or password is incorrect.', 401)
        if not identity:
            fail('INVALID_CREDENTIALS', 'Email or password is incorrect.', 401)
        return session_response(db, identity, response)


@app.post('/v1/auth/logout')
def logout(request: Request, response: Response):
    with transaction() as db:
        session = db.get(SessionToken, token_hash(request.cookies.get('kf_session', '')))
        if session:
            db.delete(session)
    response.delete_cookie('kf_session', path='/')
    response.delete_cookie('kf_business', path='/')
    return {'signed_out': True}


@app.get('/v1/me')
def me(request: Request):
    with Session() as db:
        actor = resolve_actor(db, request)
        identity = db.get(Identity, actor.user_id)
        business = d.serial(db.get(Business, actor.business_id))
        if actor.role == 'sales':
            business = {k:v for k,v in business.items() if k not in ('opening_minor','opening_date','buffer_minor')}
        return {'user': {'id': actor.user_id, 'name': identity.name if identity else 'Merchant'}, 'role': actor.role, 'business': business, 'environment': settings.env, 'action_mode': settings.action_mode}


class SelectBusiness(s.Model):
    business_id: str


@app.get('/v1/businesses')
def businesses(request: Request):
    with Session() as db:
        actor = resolve_actor(db, request)
        members = list(db.scalars(select(Membership).where(Membership.user_id == actor.user_id, Membership.active.is_(True))))
        return {'items': [{'id': m.business_id, 'name': db.get(Business,m.business_id).name, 'role':m.role} for m in members]}


@app.post('/v1/businesses/select')
def select_business(payload: SelectBusiness, request: Request, response: Response):
    with Session() as db:
        actor = resolve_actor(db, request)
        member = db.get(Membership, (payload.business_id, actor.user_id))
        if not member or not member.active:
            fail('FORBIDDEN', 'Business access denied.', 403)
    response.set_cookie('kf_business', payload.business_id, httponly=True, secure=settings.env=='production', samesite='strict', max_age=43200, path='/')
    return {'selected':payload.business_id}


@app.get('/v1/dashboard')
def dashboard(request: Request):
    with Session() as db:
        actor = resolve_actor(db, request)
        require(actor, 'read_finance')
        business = db.get(Business, actor.business_id)
        today = now().astimezone(ZoneInfo(business.timezone)).date()
        invoices = [d.invoice_view(db, i) for i in d.rows(db, Invoice, actor)]
        receipts = [{**d.serial(r), 'unapplied_minor': d.available(db, r)} for r in d.rows(db, Receipt, actor)]
        actual = business.opening_minor
        if actual is not None and business.opening_date and business.opening_date <= today:
            actual += sum(r['amount_minor'] * (1 if r['direction'] == 'in' else -1) for r in receipts if str(business.opening_date) <= r['booked_on'] <= str(today) and r['category'] != 'transfer' and r['status'] in ('posted', 'reversed'))
        else:
            actual = None
        scenario = d.run_scenario(db, actor, s.ScenarioIn(start=today, buffer_minor=business.buffer_minor).model_dump(), persist=False)
        return {'business': d.serial(business), 'today': str(today), 'actual_cash_minor': actual, 'outstanding_minor': sum(i['outstanding_minor'] for i in invoices if i['direction'] == 'receivable' and i['status'] == 'issued'), 'payable_minor': sum(i['outstanding_minor'] for i in invoices if i['direction'] == 'payable' and i['status'] == 'issued'), 'invoices': invoices, 'receipts': receipts, 'parties': [d.serial(p) for p in d.rows(db, Counterparty, actor)], 'deals': [d.serial(r) for r in d.rows(db, Deal, actor)], 'cases': [d.serial(r) for r in d.rows(db, Case, actor)], 'actions': [d.serial(r) for r in d.rows(db, Action, actor)], 'evidence': [{k: v for k, v in d.serial(r).items() if k != 'storage_key'} for r in d.rows(db, Evidence, actor)], 'forecast': scenario, 'source_label': 'Synthetic merchant • simulator records' if business.mode == 'fixture' else 'Merchant and imported records • no live bank connection', 'as_of': now().isoformat()}


COLLECTIONS = {'counterparties': Counterparty, 'deals': Deal, 'invoices': Invoice, 'receipts': Receipt, 'allocations': Allocation, 'cases': Case, 'actions': Action, 'evidence': Evidence, 'jobs': Job, 'audit': Audit, 'scenarios': Scenario, 'promises': Promise, 'deliveries': Delivery, 'supplements': Supplement}


@app.get('/v1/records/{collection}')
def list_records(collection: str, request: Request, offset: int = 0, limit: int = 100):
    if collection not in COLLECTIONS or not 1 <= limit <= 200 or offset < 0:
        fail('INVALID_COLLECTION', 'Invalid collection or pagination.', 422)
    with Session() as db:
        actor = resolve_actor(db, request)
        model = COLLECTIONS[collection]
        if actor.role == 'sales':
            if collection not in ('counterparties', 'deals', 'evidence'):
                fail('FORBIDDEN', 'Sales access is limited to assigned trade records.', 403)
        else:
            require(actor, 'read_finance')
        query = select(model).where(model.business_id == actor.business_id)
        if actor.role == 'sales':
            if model == Counterparty:
                query = query.where(Counterparty.assigned_user_id == actor.user_id)
            elif model == Deal:
                query = query.where(Deal.counterparty_id.in_(select(Counterparty.id).where(Counterparty.business_id == actor.business_id, Counterparty.assigned_user_id == actor.user_id)))
            else:
                query = query.where(Evidence.creator_id == actor.user_id)
        result = []
        for row in db.scalars(query.order_by(model.created_at.desc(), model.id).offset(offset).limit(limit)):
            item = d.invoice_view(db, row) if model == Invoice else d.serial(row)
            item.pop('storage_key', None)
            if model == Scenario:
                item['stale'] = row.baseline_revision != db.get(Business, actor.business_id).revision
            result.append(item)
        return {'items': result, 'offset': offset, 'limit': limit}


@app.get('/v1/invoices/{record_id}/evidence')
def invoice_evidence(record_id: str, request: Request):
    with Session() as db:
        actor = resolve_actor(db, request)
        require(actor, 'read_finance')
        invoice = scoped(db, Invoice, record_id, actor)
        allocations = [r for r in d.rows(db, Allocation, actor) if r.invoice_id == invoice.id]
        return {'invoice': d.invoice_view(db, invoice), 'claims': [d.serial(r) for r in d.rows(db, Claim, actor) if r.invoice_id == invoice.id], 'allocations': [d.serial(r) for r in allocations], 'receipts': [d.serial(r) for r in d.rows(db, Receipt, actor) if r.id in {a.receipt_id for a in allocations}], 'adjustments': [d.serial(r) for r in d.rows(db, Adjustment, actor) if r.invoice_id == invoice.id]}


@app.post('/v1/counterparties')
def party(payload: s.PartyIn, request: Request):
    def run(db, actor, data):
        require(actor, 'trade')
        if actor.role == 'sales':
            data['assigned_user_id'] = actor.user_id
        row = d.add(db, Counterparty, actor, **data)
        d.audit(db, actor, 'CounterpartyCreated', row)
        return d.serial(row)
    return command(request, payload, 'party', run)


@app.post('/v1/evidence', response_model=s.EvidenceOut)
def evidence(payload: s.EvidenceIn, request: Request):
    return command(request, payload, 'evidence', d.create_evidence)


@app.post('/v1/documents', status_code=202)
async def upload(request: Request, file: UploadFile = File(...)):
    actor = actor_from(request)
    require(actor, 'trade')
    allowed = {'image/png', 'image/jpeg', 'application/pdf', 'audio/ogg', 'audio/mpeg', 'audio/wav', 'audio/mp4', 'audio/webm'}
    if file.content_type not in allowed:
        fail('UNSUPPORTED_MEDIA', 'Use JPEG, PNG, PDF, OGG, MP3, WAV, M4A or WebM.', 422)
    content = await file.read(8 * 1024 * 1024 + 1)
    if not content or len(content) > 8 * 1024 * 1024:
        fail('FILE_SIZE', 'Files must be nonempty and at most 8 MB.', 413)
    from .media import validate_media
    validate_media(content, file.content_type)
    from hashlib import sha256
    hashed = sha256(content).hexdigest()
    def run(db, actor, data):
        existing = db.scalar(select(Evidence).where(Evidence.business_id == actor.business_id, Evidence.content_hash == hashed))
        if existing:
            if actor.role == 'sales' and existing.creator_id != actor.user_id:
                fail('DUPLICATE_SOURCE', 'This document is already in review.', 409)
            return {k: v for k, v in d.serial(existing).items() if k != 'storage_key'}
        key = actor.business_id + '/' + hashed
        path = settings.media / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        row = d.add(db, Evidence, actor, kind='voice' if file.content_type.startswith('audio') else 'document', source='merchant_upload', content_hash=hashed, filename=Path(file.filename or 'upload').name[:200], media_type=file.content_type, storage_key=key, creator_id=actor.user_id)
        d.add(db, Job, actor, kind='extract', record_id=row.id)
        d.audit(db, actor, 'DocumentCaptured', row)
        return {k: v for k, v in d.serial(row).items() if k != 'storage_key'}
    return command(request, {'hash': hashed, 'type': file.content_type}, 'document', run)


@app.get('/v1/evidence/{record_id}/file')
def download(record_id: str, request: Request):
    with Session() as db:
        actor = resolve_actor(db, request)
        ev = scoped(db, Evidence, record_id, actor)
        if actor.role == 'sales' and ev.creator_id != actor.user_id:
            fail('FORBIDDEN', 'Evidence is not assigned to you.', 403)
        if actor.role != 'sales':
            require(actor, 'read_finance')
        if not ev.storage_key:
            fail('NO_FILE', 'This evidence is text-only.', 404)
        path = (settings.media / ev.storage_key).resolve()
        if not path.is_relative_to(settings.media) or not path.is_file():
            fail('NO_FILE', 'Private evidence file is unavailable.', 404)
        return FileResponse(path, filename=ev.filename, media_type='application/octet-stream')


@app.post('/v1/deals', response_model=s.DealOut)
def deal(payload: s.DealIn, request: Request):
    return command(request, payload, 'deal', d.create_deal)


@app.post('/v1/deals/{record_id}/confirm', response_model=s.DealOut)
def confirm(record_id: str, payload: s.Confirm, request: Request):
    return command(request, payload, 'confirm:' + record_id, lambda db, a, p: d.confirm_deal(db, a, record_id, p))


@app.post('/v1/deals/{record_id}/amend')
def amend(record_id: str, payload: s.Amend, request: Request):
    return command(request, payload, 'amend:' + record_id, lambda db, a, p: d.amend_deal(db, a, record_id, p))


@app.post('/v1/invoices', response_model=s.InvoiceOut)
def invoice(payload: s.InvoiceIn, request: Request):
    return command(request, payload, 'invoice', d.create_invoice)


@app.post('/v1/invoices/{record_id}/issue')
def issue(record_id: str, payload: s.Expected, request: Request):
    return command(request, payload, 'issue:' + record_id, lambda db, a, p: d.issue_invoice(db, a, record_id, p))


@app.post('/v1/invoices/{record_id}/dispute')
def dispute(record_id: str, payload: s.Reason, request: Request):
    def run(db, actor, data):
        require(actor, 'write_finance')
        row = scoped(db, Invoice, record_id, actor)
        d.version(row, data['expected_version'])
        row.disputed, row.version = not row.disputed, row.version + 1
        d.audit(db, actor, 'InvoiceDisputeChanged', row, reason=data['reason'])
        d.invalidate_reminders(db, actor, row)
        return d.invoice_view(db, row)
    return command(request, payload, 'dispute:' + record_id, run)


@app.post('/v1/receipts', response_model=s.ReceiptOut)
def receipt(payload: s.ReceiptIn, request: Request):
    return command(request, payload, 'receipt', d.create_receipt)


@app.post('/v1/reconciliations', response_model=s.ReconciliationOut)
def reconcile(payload: s.Reconcile, request: Request):
    return command(request, payload, 'reconcile', d.reconcile)


@app.post('/v1/allocations/{record_id}/reverse')
def unmatch(record_id: str, payload: s.Reason, request: Request):
    return command(request, payload, 'unmatch:' + record_id, lambda db, a, p: d.reverse_allocation(db, a, record_id, p))


@app.post('/v1/receipts/{record_id}/reverse')
def reverse(record_id: str, payload: s.Reason, request: Request):
    return command(request, payload, 'reverse:' + record_id, lambda db, a, p: d.reverse_receipt(db, a, record_id, p))


@app.post('/v1/adjustments')
def adjustment(payload: s.AdjustmentIn, request: Request):
    def run(db, actor, data):
        require(actor, 'approve')
        invoice = scoped(db, Invoice, data['invoice_id'], actor)
        d.version(invoice, data.pop('expected_version'))
        if invoice.status != 'issued':
            fail('INVOICE_NOT_ISSUED', 'Only issued invoices support ledger adjustments.')
        if data['amount_minor'] > d.outstanding(db, invoice):
            fail('ADJUSTMENT_EXCEEDS_BALANCE', 'Adjustment exceeds outstanding balance.')
        row = d.add(db, Adjustment, actor, **data)
        invoice.version += 1
        d.audit(db, actor, 'InvoiceAdjusted', row, reason=data['reason'])
        d.invalidate_reminders(db, actor, invoice)
        return d.invoice_view(db, invoice)
    return command(request, payload, 'adjustment', run)


@app.post('/v1/deliveries')
def delivery(payload: s.DeliveryIn, request: Request):
    def run(db, actor, data):
        require(actor, 'trade')
        deal = scoped(db, Deal, data['deal_id'], actor)
        d.trade_party(db, actor, deal.counterparty_id)
        try:
            quantity = Decimal(data['accepted_quantity'])
            if not quantity.is_finite() or quantity <= 0:
                raise ValueError()
        except Exception:
            fail('QUANTITY_INVALID', 'Supply a positive accepted quantity.', 422)
        if deal.status != 'confirmed':
            fail('DEAL_UNCONFIRMED', 'Confirm deal terms first.')
        row = d.add(db, Delivery, actor, **data)
        d.audit(db, actor, 'DeliveryRecorded', row)
        d.detect_cases(db, actor)
        return d.serial(row)
    return command(request, payload, 'delivery', run)


@app.post('/v1/promises')
def promise(payload: s.PromiseIn, request: Request):
    def run(db, actor, data):
        require(actor, 'write_finance')
        invoice = scoped(db, Invoice, data['invoice_id'], actor)
        if data['amount_minor'] > d.outstanding(db, invoice):
            fail('PROMISE_EXCEEDS_BALANCE', 'Promise exceeds outstanding balance.')
        row = d.add(db, Promise, actor, **data)
        d.audit(db, actor, 'PromiseRecordedNotCash', row)
        return d.serial(row)
    return command(request, payload, 'promise', run)


@app.post('/v1/scenarios')
def scenario(payload: s.ScenarioIn, request: Request):
    return command(request, payload, 'scenario', d.run_scenario)


@app.post('/v1/queries')
def query(payload: s.QueryIn, request: Request):
    return command(request, payload, 'query', d.query_metric)


@app.post('/v1/actions', response_model=s.ActionOut)
def action(payload: s.ActionIn, request: Request):
    return command(request, payload, 'action', d.create_action)


@app.post('/v1/actions/{record_id}/approve', response_model=s.ActionOut)
def approve(record_id: str, payload: s.Approve, request: Request):
    return command(request, payload, 'approve:' + record_id, lambda db, a, p: d.approve_action(db, a, record_id, p))


@app.post('/v1/actions/{record_id}/revoke')
def revoke(record_id: str, payload: s.Reason, request: Request):
    def run(db, actor, data):
        require(actor, 'approve')
        row = scoped(db, Action, record_id, actor)
        d.version(row, data['expected_version'])
        if row.status not in ('queued', 'approval_required'):
            fail('CANNOT_REVOKE', 'Action already started or ended. Review its outcome.')
        row.status, row.version = 'revoked', row.version + 1
        d.audit(db, actor, 'ApprovalRevoked', row, reason=data['reason'])
        return d.serial(row)
    return command(request, payload, 'revoke:' + record_id, run)


@app.post('/v1/actions/{record_id}/outcome')
def outcome(record_id: str, payload: s.OutcomeIn, request: Request):
    def run(db, actor, data):
        require(actor, 'write_finance')
        action = scoped(db, Action, record_id, actor)
        row = d.add(db, Supplement, actor, kind='action_outcome', status=data['status'], data={**data, 'action_id': action.id, 'assurance': 'merchant_recorded_response'})
        d.audit(db, actor, 'ActionOutcomeRecorded', row)
        return d.serial(row)
    return command(request, payload, 'outcome:' + record_id, run)


@app.post('/v1/cases/{record_id}/review')
def review(record_id: str, payload: s.CaseReview, request: Request):
    def run(db, actor, data):
        require(actor, 'write_finance')
        row = scoped(db, Case, record_id, actor)
        d.version(row, data['expected_version'])
        row.status, row.reason, row.version = data['disposition'], data['reason'], row.version + 1
        row.assigned_to = actor.user_id
        d.audit(db, actor, 'CaseReviewed', row, disposition=row.status, reason=row.reason)
        return d.serial(row)
    return command(request, payload, 'case:' + record_id, run)


@app.post('/v1/bank-imports')
def imports(payload: s.ImportIn, request: Request):
    return command(request, payload, 'import', d.import_statement)


@app.post('/v1/batches')
def batch(payload: s.BatchIn, request: Request):
    def run(db, actor, data):
        require(actor, 'write_finance')
        try:
            result = d.batch_cost(data)
        except ValueError as e:
            fail('BATCH_INVALID', str(e), 422)
        row = d.add(db, Supplement, actor, kind='batch_costing', status='merchant_recorded', data={**data, 'result': result})
        d.audit(db, actor, 'BatchCosted', row)
        return d.serial(row)
    return command(request, payload, 'batch', run)


@app.post('/v1/signals')
def signal(payload: s.SignalIn, request: Request):
    def run(db, actor, data):
        require(actor, 'write_finance')
        for deal_id in data['deal_ids']:
            scoped(db, Deal, deal_id, actor)
        data['observed_on'] = str(data['observed_on'])
        data['retrieved_at'] = now().isoformat()
        row = d.add(db, Supplement, actor, kind='market_signal', status='linked_assumption' if data['deal_ids'] else 'informational_only', data=data)
        return d.serial(row)
    return command(request, payload, 'signal', run)


@app.post('/v1/einvoices')
def einvoice(payload: s.EInvoiceIn, request: Request):
    def run(db, actor, data):
        require(actor, 'write_finance')
        invoice = scoped(db, Invoice, data['invoice_id'], actor)
        row = d.add(db, Supplement, actor, kind='einvoice', status='draft', data={**data, 'invoice_version': invoice.version, 'total_minor': invoice.total_minor, 'missing_fields': [k for k in ('seller_tax_id', 'buyer_tax_id') if not data[k]], 'provider_status': 'not_submitted', 'connector': 'MyInvois adapter not configured'})
        d.audit(db, actor, 'EInvoiceDrafted', row)
        return d.serial(row)
    return command(request, payload, 'einvoice', run)


@app.post('/v1/exports')
def export(request: Request):
    def run(db, actor, _):
        require(actor, 'export')
        records = [d.invoice_view(db, r) for r in d.rows(db, Invoice, actor)]
        row = d.add(db, Supplement, actor, kind='accounting_export', status='prepared_not_submitted', data={'invoices': records, 'allocations': [d.serial(r) for r in d.rows(db, Allocation, actor)], 'adjustments': [d.serial(r) for r in d.rows(db, Adjustment, actor)], 'mode': db.get(Business, actor.business_id).mode})
        d.audit(db, actor, 'ExportPrepared', row)
        return d.serial(row)
    return command(request, {}, 'export', run)


@app.get('/v1/exports/{record_id}/csv')
def export_csv(record_id: str, request: Request):
    with Session() as db:
        actor = resolve_actor(db, request)
        require(actor, 'export')
        row = scoped(db, Supplement, record_id, actor)
        if row.kind != 'accounting_export':
            fail('NOT_FOUND', 'Export not found.', 404)
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['record_type', 'id', 'reference', 'amount_minor', 'outstanding_minor', 'currency', 'state', 'environment'])
        def safe(value):
            value = str(value)
            return "'" + value if value.startswith(('=', '+', '-', '@', '\t', '\r', '\n')) else value
        for i in row.data['invoices']:
            writer.writerow([safe(v) for v in ['invoice', i['id'], i['number'], i['total_minor'], i['outstanding_minor'], i['currency'], i['status'], row.data['mode']]])
        for a in row.data['allocations']:
            writer.writerow(['allocation', a['id'], a['invoice_id'], a['amount_minor'], '', 'MYR', 'reversed' if a['reversed'] else 'active', row.data['mode']])
        for a in row.data['adjustments']:
            writer.writerow(['adjustment', a['id'], a['invoice_id'], a['amount_minor'], '', 'MYR', a['kind'], row.data['mode']])
        return Response(output.getvalue(), media_type='text/csv', headers={'Content-Disposition': 'attachment; filename=kedaiflow-operational-export.csv'})


@app.post('/v1/settings')
def business_settings(payload: s.SettingsIn, request: Request):
    def run(db, actor, data):
        require(actor, 'admin')
        row = db.get(Business, actor.business_id)
        if (data['opening_minor'] is None) != (data['opening_date'] is None):
            fail('OPENING_INCOMPLETE', 'Opening amount and date must be supplied together.', 422)
        before = d.serial(row)
        for key, value in data.items():
            setattr(row, key, value)
        d.audit(db, actor, 'BusinessSettingsChanged', row, previous=before)
        return d.serial(row)
    return command(request, payload, 'settings', run)


@app.post('/v1/members')
def member(payload: s.MemberIn, request: Request):
    def run(db, actor, data):
        require(actor, 'admin')
        identity = db.scalar(select(Identity).where(Identity.email == data['email'].lower()))
        if not identity:
            fail('USER_NOT_REGISTERED', 'Ask this colleague to register before granting membership.', 422)
        row = db.get(Membership, (actor.business_id, identity.id))
        if row and row.role == 'owner':
            fail('OWNER_PROTECTED', 'Owner changes require a separate recovery process.', 403)
        if not row:
            row = Membership(business_id=actor.business_id, user_id=identity.id, role=data['role'])
            db.add(row)
        row.role, row.active = data['role'], data['active']
        d.audit(db, actor, 'MembershipChanged', identity, role=row.role, active=row.active)
        return {'user_id': identity.id, 'role': row.role, 'active': row.active}
    return command(request, payload, 'member', run)


@app.post('/v1/controls/pause')
def pause(payload: s.PauseIn, request: Request):
    def run(db, actor, data):
        require(actor, 'admin')
        row = db.get(Business, actor.business_id)
        row.paused = data['paused']
        d.audit(db, actor, 'ActionsPauseChanged', row, paused=row.paused)
        return {'paused': row.paused}
    return command(request, payload, 'pause', run)


@app.get('/v1/connectors')
def connectors(request: Request):
    actor = actor_from(request)
    require(actor, 'read_finance')
    return {'items': [{'name': 'Telegram', 'status': 'configured_unverified' if settings.telegram_token else 'not_connected', 'setup': 'TELEGRAM_BOT_TOKEN, TELEGRAM_BOT_ID and authenticated binding'}, {'name': 'Gemini extraction', 'status': 'configured_unverified' if settings.gemini_key and settings.model_approved else 'manual_review', 'setup': 'GEMINI_API_KEY, GEMINI_MODEL and MODEL_PROCESSING_APPROVED'}, {'name': 'Bank feed', 'status': 'not_connected', 'setup': 'Use reviewed statement imports; select and authorize a bank provider later.'}, {'name': 'MyInvois / ERP', 'status': 'draft_export_only', 'setup': 'Taxpayer/provider authorization and adapter validation required.'}, {'name': 'Anomaly ML', 'status': 'disabled', 'setup': 'Consented data, reviewed labels and evaluation required.'}]}


@app.get('/v1/brief')
def brief(request: Request):
    data = dashboard(request)
    count = len([c for c in data['cases'] if c['status'] not in ('resolved', 'dismissed', 'intentional')])
    language = data['business']['language']
    amount = f"RM{Decimal(data['outstanding_minor']) / 100:,.2f}"
    templates = {'en': f"Your recorded outstanding invoices total {amount}. You have {count} potential exceptions to review. Cash forecasts include assumptions. Check source coverage before making a decision.", 'ms': f"Baki invois yang direkodkan ialah {amount}. Terdapat {count} perkara untuk disemak. Ramalan tunai mengandungi andaian. Semak sumber sebelum membuat keputusan.", 'zh': f"已记录的应收账款为 {amount}。有 {count} 项待核查事项。现金预测包含假设，请先检查数据来源。"}
    return {'text': templates[language], 'language': language, 'source_as_of': data['as_of'], 'mode': data['business']['mode'], 'metrics': {'outstanding_minor': data['outstanding_minor'], 'case_count': count}, 'voice': 'Optional browser speech; availability depends on installed voices.'}


@app.post('/v1/channels/telegram/bind-code')
def bind_code(request: Request):
    def run(db, actor, _):
        require(actor, 'trade')
        code = secrets.token_urlsafe(24)
        row = d.add(db, BindCode, actor, code_hash=token_hash(code), user_id=actor.user_id, expires_at=now() + timedelta(minutes=5))
        return {'code': code, 'expires_at': str(row.expires_at), 'instruction': 'Send /bind ' + code + ' to your bot in a private chat.'}
    return command(request, {}, 'bind-code', run)


@app.post('/v1/channels/telegram/webhook')
async def telegram_webhook(request: Request):
    if settings.telegram_mode != 'webhook' or not settings.webhook_secret or not settings.telegram_id:
        fail('WEBHOOK_DISABLED', 'Webhook mode is not configured.', 503)
    supplied = request.headers.get('x-telegram-bot-api-secret-token', '')
    if not secrets.compare_digest(supplied, settings.webhook_secret):
        fail('WEBHOOK_SECRET', 'Invalid webhook secret.', 403)
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > 256000:
            fail('UPDATE_TOO_LARGE', 'Telegram update is too large.', 413)
    try:
        update = json.loads(body)
    except ValueError:
        fail('UPDATE_INVALID', 'Invalid update.', 422)
    from .telegram import accept_update
    accepted = accept_update(update)
    return {'ok': True, 'accepted': accepted}


from .extensions import install
install(app, command, lambda: Session(), lambda **kwargs: transaction(**kwargs))

