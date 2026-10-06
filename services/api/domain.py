"""Transport-independent commands. Caller supplies an authenticated actor and transaction."""
import csv
import io
from datetime import date, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo
from sqlalchemy import select, func
from .models import *
from .security import Actor, aware, current_actor, digest, fail, require, scoped
from .finance import total_items, forecast, batch_cost


def serial(row):
    def value(v):
        if isinstance(v, datetime):
            return aware(v).isoformat()
        return v.isoformat() if isinstance(v, date) else v
    return {c.name: value(getattr(row, c.name)) for c in row.__table__.columns}


def rows(db, model, actor):
    return list(db.scalars(select(model).where(model.business_id == actor.business_id)))


def add(db, model, actor, **values):
    row = model(business_id=actor.business_id, **values)
    db.add(row)
    db.flush()
    return row


def audit(db, actor, event, row, **detail):
    add(db, Audit, actor, actor_id=actor.user_id, event=event, record_id=row.id, detail=detail)
    business = db.get(Business, actor.business_id)
    business.revision += 1


def version(row, expected):
    if row.version != expected:
        fail('STALE_VERSION', 'This record changed. Refresh and review the current version.')


def trade_party(db, actor, party_id):
    party = scoped(db, Counterparty, party_id, actor)
    if actor.role == 'sales' and party.assigned_user_id != actor.user_id:
        fail('NOT_FOUND', 'Counterparty is not assigned to you.', 404)
    return party


def outstanding(db, invoice):
    allocated = db.scalar(select(func.coalesce(func.sum(Allocation.amount_minor), 0)).where(Allocation.business_id == invoice.business_id, Allocation.invoice_id == invoice.id, Allocation.reversed.is_(False)))
    adjusted = db.scalar(select(func.coalesce(func.sum(Adjustment.amount_minor), 0)).where(Adjustment.business_id == invoice.business_id, Adjustment.invoice_id == invoice.id))
    return invoice.total_minor - allocated - adjusted


def available(db, receipt):
    allocated = db.scalar(select(func.coalesce(func.sum(Allocation.amount_minor), 0)).where(Allocation.business_id == receipt.business_id, Allocation.receipt_id == receipt.id, Allocation.reversed.is_(False)))
    return receipt.amount_minor - allocated if receipt.status == 'posted' and not receipt.reversal_of else 0


def invoice_view(db, row):
    data = serial(row)
    data['outstanding_minor'] = outstanding(db, row)
    data['payment_state'] = 'paid' if data['outstanding_minor'] == 0 else 'partially_paid' if data['outstanding_minor'] < row.total_minor else 'unpaid'
    data['days_overdue'] = max(0, (now().astimezone(ZoneInfo('Asia/Kuala_Lumpur')).date() - row.due_date).days) if data['outstanding_minor'] else 0
    return data


def invalidate_reminders(db, actor, invoice):
    for action in rows(db, Action, actor):
        if action.invoice_id == invoice.id and action.status in ('approval_required', 'queued'):
            action.status = 'stale'
            action.outcome = 'Invoice changed. Review a fresh proposal before sending.'
            action.version += 1
    for promise in rows(db, Promise, actor):
        if promise.invoice_id == invoice.id and outstanding(db, invoice) == 0:
            promise.status = 'resolved_by_receipt'
    detect_cases(db, actor)


def create_evidence(db, actor, data):
    require(actor, 'trade')
    if data.get('invoice_id'):
        require(actor, 'write_finance')
        scoped(db, Invoice, data['invoice_id'], actor)
    content_hash = digest({'text': data['text'], 'kind': data['kind']})
    prior = db.scalar(select(Evidence).where(Evidence.business_id == actor.business_id, Evidence.content_hash == content_hash))
    if prior:
        if prior.creator_id != actor.user_id and actor.role == 'sales':
            fail('DUPLICATE_SOURCE', 'This source already exists. Ask the bookkeeper to review.', 409)
        return serial(prior)
    evidence = add(db, Evidence, actor, kind=data['kind'], source='android_notification' if data['kind'] == 'notification' else 'merchant_input', content_hash=content_hash, text=data['text'], creator_id=actor.user_id)
    if data['kind'] in ('payment_claim', 'notification'):
        add(db, Claim, actor, invoice_id=data.get('invoice_id'), evidence_id=evidence.id, amount_minor=data.get('claimed_minor'))
    add(db, Job, actor, kind='extract', record_id=evidence.id)
    audit(db, actor, 'EvidenceCaptured', evidence, assurance='untrusted_source')
    return serial(evidence)


def create_deal(db, actor, data):
    require(actor, 'trade')
    trade_party(db, actor, data['counterparty_id'])
    for eid in data['evidence_ids']:
        ev = scoped(db, Evidence, eid, actor)
        if actor.role == 'sales' and ev.creator_id != actor.user_id:
            fail('FORBIDDEN', 'Evidence is not assigned to you.', 403)
    total = total_items(data['items'])
    if data['deposit_minor'] > total:
        fail('DEPOSIT_EXCEEDS_TOTAL', 'Deposit cannot exceed the deal total.', 422)
    deal = add(db, Deal, actor, title=data['title'], counterparty_id=data['counterparty_id'], total_minor=total, deposit_minor=data['deposit_minor'], due_date=data['due_date'], delivery_date=data['delivery_date'], currency=data['currency'], terms={'items': data['items'], 'charges': data['charges']}, evidence_ids=data['evidence_ids'])
    if deal.due_date and deal.delivery_date and data['charges'] != 'unknown':
        deal.status = 'draft'
    add(db, DealVersion, actor, deal_id=deal.id, snapshot=serial(deal), reason='Initial candidate terms')
    audit(db, actor, 'DealDrafted', deal)
    return serial(deal)


def confirm_deal(db, actor, deal_id, data):
    require(actor, 'trade')
    deal = scoped(db, Deal, deal_id, actor)
    trade_party(db, actor, deal.counterparty_id)
    version(deal, data['expected_version'])
    if deal.status == 'confirmed':
        fail('ALREADY_CONFIRMED', 'These terms are already confirmed.')
    deal.due_date, deal.delivery_date = data['due_date'], data['delivery_date']
    deal.terms = {**deal.terms, 'charges': data['charges']}
    deal.status, deal.confirmation_level, deal.confirmed_by = 'confirmed', 'owner_recorded_interpretation' if actor.role == 'owner' else 'staff_recorded_interpretation', actor.user_id
    deal.version += 1
    add(db, DealVersion, actor, deal_id=deal.id, version=deal.version, snapshot=serial(deal), reason='Merchant confirmed exact terms; counterparty acceptance not established')
    audit(db, actor, 'DealConfirmed', deal)
    return serial(deal)


def amend_deal(db, actor, deal_id, data):
    require(actor, 'trade')
    old = scoped(db, Deal, deal_id, actor)
    trade_party(db, actor, old.counterparty_id)
    trade_party(db, actor, data['counterparty_id'])
    version(old, data['expected_version'])
    for eid in data['evidence_ids']:
        scoped(db, Evidence, eid, actor)
    total = total_items(data['items'])
    if data['deposit_minor'] > total:
        fail('INVALID_DEPOSIT', 'Deposit exceeds total.', 422)
    for key in ('title', 'counterparty_id', 'deposit_minor', 'due_date', 'delivery_date', 'currency', 'evidence_ids'):
        setattr(old, key, data[key])
    old.total_minor, old.terms = total, {'items': data['items'], 'charges': data['charges']}
    old.status, old.confirmation_level, old.confirmed_by = 'draft', 'unconfirmed', None
    old.version += 1
    add(db, DealVersion, actor, deal_id=old.id, version=old.version, snapshot=serial(old), reason=data['reason'])
    audit(db, actor, 'DealAmended', old, reason=data['reason'])
    return serial(old)


def create_invoice(db, actor, data):
    require(actor, 'write_finance')
    scoped(db, Counterparty, data['counterparty_id'], actor)
    deal_version = None
    if data['deal_id']:
        deal = scoped(db, Deal, data['deal_id'], actor)
        if deal.status != 'confirmed' or deal.counterparty_id != data['counterparty_id'] or deal.total_minor != data['total_minor']:
            fail('DEAL_MISMATCH', 'Invoice must match confirmed terms. Record an amendment first.')
        if db.scalar(select(Invoice).where(Invoice.business_id == actor.business_id, Invoice.deal_id == deal.id)):
            fail('ALREADY_INVOICED', 'This deal already has an invoice. Use a reviewed adjustment.')
        deal_version = deal.version
    invoice = add(db, Invoice, actor, **data, deal_version=deal_version)
    audit(db, actor, 'InvoiceDrafted', invoice)
    return invoice_view(db, invoice)


def issue_invoice(db, actor, invoice_id, data):
    require(actor, 'write_finance')
    invoice = scoped(db, Invoice, invoice_id, actor)
    version(invoice, data['expected_version'])
    if invoice.status != 'draft':
        fail('INVALID_STATE', 'Only drafts can be issued.')
    if invoice.deal_id:
        deal = scoped(db, Deal, invoice.deal_id, actor)
        if deal.status != 'confirmed' or deal.version != invoice.deal_version:
            fail('DEAL_CHANGED', 'Refresh the invoice after the deal amendment.')
    invoice.status, invoice.version = 'issued', invoice.version + 1
    audit(db, actor, 'InvoiceIssuedInternally', invoice)
    detect_cases(db, actor)
    return invoice_view(db, invoice)


def create_receipt(db, actor, data):
    require(actor, 'write_finance')
    business = db.get(Business, actor.business_id)
    if data['source'] == 'simulator' and business.mode != 'fixture':
        fail('SOURCE_MODE', 'Simulator receipts cannot enter an imported or connected business.', 403)
    if business.mode == 'fixture' and data['source'] != 'simulator':
        fail('SOURCE_MODE', 'Use a separate business for real imports; this business is isolated fixture data.', 403)
    if data['source'] == 'statement_import':
        if not data['evidence_id']:
            fail('SOURCE_REQUIRED', 'Statement evidence is required.', 422)
        evidence = scoped(db, Evidence, data['evidence_id'], actor)
        if evidence.kind != 'statement':
            fail('SOURCE_REQUIRED', 'Use the reviewed statement import workflow.', 422)
    elif data.get('evidence_id'):
        scoped(db, Evidence, data['evidence_id'], actor)
    prior = db.scalar(select(Receipt).where(Receipt.business_id == actor.business_id, Receipt.account == data['account'], Receipt.source_event_id == data['source_event_id']))
    if prior:
        if any(getattr(prior, k) != v for k, v in data.items()):
            fail('SOURCE_CONFLICT', 'This source transaction exists with different fields.')
        return {**serial(prior), 'unapplied_minor': available(db, prior)}
    receipt = add(db, Receipt, actor, **data)
    audit(db, actor, 'ReceiptRecorded', receipt, assurance=receipt.source)
    detect_cases(db, actor)
    return {**serial(receipt), 'unapplied_minor': available(db, receipt)}


def reconcile(db, actor, data):
    require(actor, 'write_finance')
    receipt = scoped(db, Receipt, data['receipt_id'], actor)
    version(receipt, data['expected_receipt_version'])
    if receipt.status != 'posted' or receipt.category not in ('customer_receipt', 'supplier_payment') or receipt.reversal_of:
        fail('RECEIPT_UNUSABLE', 'This receipt cannot be allocated.')
    if len({line['invoice_id'] for line in data['allocations']}) != len(data['allocations']):
        fail('DUPLICATE_INVOICE', 'An invoice can appear only once per allocation command.', 422)
    if sum(line['amount_minor'] for line in data['allocations']) > available(db, receipt):
        fail('INSUFFICIENT_RECEIPT', 'Allocations exceed the available receipt amount.')
    invoices = []
    for line in sorted(data['allocations'], key=lambda line: line['invoice_id']):
        invoice = scoped(db, Invoice, line['invoice_id'], actor)
        version(invoice, line['expected_invoice_version'])
        if invoice.status != 'issued' or invoice.disputed or invoice.currency != receipt.currency or (invoice.direction == 'receivable') != (receipt.direction == 'in'):
            fail('INVOICE_INELIGIBLE', 'Check invoice state, dispute, direction and currency.')
        if line['amount_minor'] > outstanding(db, invoice):
            fail('OVERALLOCATION', 'Allocate only the outstanding balance. Leave the remainder as unapplied credit.')
        invoices.append((invoice, line))
    allocations = []
    for invoice, line in invoices:
        allocation = add(db, Allocation, actor, receipt_id=receipt.id, invoice_id=invoice.id, amount_minor=line['amount_minor'], reason=data['reason'])
        allocations.append(serial(allocation))
        invoice.version += 1
        audit(db, actor, 'AllocationCommitted', allocation, invoice_id=invoice.id)
        invalidate_reminders(db, actor, invoice)
    receipt.version += 1
    detect_cases(db, actor)
    return {'allocations': allocations, 'invoices': [invoice_view(db, i) for i, _ in invoices], 'unapplied_minor': available(db, receipt)}


def reverse_allocation(db, actor, allocation_id, data):
    require(actor, 'write_finance')
    allocation = scoped(db, Allocation, allocation_id, actor)
    version(allocation, data['expected_version'])
    if allocation.reversed:
        fail('ALREADY_REVERSED', 'This allocation was already reversed.')
    allocation.reversed = True
    allocation.version += 1
    invoice = scoped(db, Invoice, allocation.invoice_id, actor)
    receipt = scoped(db, Receipt, allocation.receipt_id, actor)
    invoice.version += 1
    receipt.version += 1
    audit(db, actor, 'AllocationReversed', allocation, reason=data['reason'])
    invalidate_reminders(db, actor, invoice)
    return invoice_view(db, invoice)


def reverse_receipt(db, actor, receipt_id, data):
    require(actor, 'write_finance')
    receipt = scoped(db, Receipt, receipt_id, actor)
    version(receipt, data['expected_version'])
    if receipt.status != 'posted' or receipt.reversal_of:
        fail('INVALID_REVERSAL', 'Receipt is not reversible.')
    receipt.status = 'reversed'
    receipt.version += 1
    for allocation in rows(db, Allocation, actor):
        if allocation.receipt_id == receipt.id and not allocation.reversed:
            allocation.reversed = True
            allocation.version += 1
            invoice = scoped(db, Invoice, allocation.invoice_id, actor)
            invoice.version += 1
            invalidate_reminders(db, actor, invoice)
    reversal = add(db, Receipt, actor, account=receipt.account, source_event_id='reversal:' + receipt.id, source=receipt.source, amount_minor=receipt.amount_minor, currency=receipt.currency, booked_on=now().astimezone(ZoneInfo('Asia/Kuala_Lumpur')).date(), reference=data['reason'], direction='out' if receipt.direction == 'in' else 'in', category=receipt.category, reversal_of=receipt.id)
    audit(db, actor, 'ReceiptReversed', reversal, original_id=receipt.id, reason=data['reason'])
    detect_cases(db, actor)
    return serial(reversal)


def detect_cases(db, actor):
    active = {}
    invoices = rows(db, Invoice, actor)
    for delivery in rows(db, Delivery, actor):
        if not any(i.deal_id == delivery.deal_id and i.status == 'issued' for i in invoices):
            deal = scoped(db, Deal, delivery.deal_id, actor)
            active[('delivered_unbilled', delivery.id)] = ('Delivered, but no issued invoice', deal.total_minor, 'Delivery and confirmed deal exist; no issued invoice is linked. Review accepted quantities, returns and billing schedule.')
    for receipt in rows(db, Receipt, actor):
        amount = available(db, receipt)
        if amount > 0 and receipt.direction == 'in' and receipt.category != 'transfer':
            active[('unapplied_receipt', receipt.id)] = ('A receipt needs matching', amount, f'Recorded {receipt.source} receipt has unapplied funds. This is not another sale.')
    today = now().astimezone(ZoneInfo('Asia/Kuala_Lumpur')).date()
    for invoice in invoices:
        remaining = outstanding(db, invoice)
        if invoice.status == 'issued' and invoice.direction == 'receivable' and remaining > 0 and invoice.due_date < today:
            active[('overdue_receivable', invoice.id)] = ('An invoice is overdue', remaining, 'Outstanding in available records. Missing or delayed account evidence may change this result.')
        if invoice.deal_id:
            deal = scoped(db, Deal, invoice.deal_id, actor)
            if invoice.deal_version != deal.version and invoice.status == 'issued':
                active[('terms_changed', invoice.id)] = ('Deal terms changed after invoicing', invoice.total_minor, 'Review a credit or replacement. Historical issued amounts have been preserved.')
    for invoice in invoices:
        if invoice.direction == 'payable' and any(other.id != invoice.id and other.counterparty_id == invoice.counterparty_id and other.total_minor == invoice.total_minor and other.issued_on == invoice.issued_on for other in invoices):
            active[('duplicate_bill_candidate', invoice.id)] = ('Possible duplicate supplier charge', invoice.total_minor, 'Same supplier, date and amount. Review source documents; this is not proof of duplication or fraud.')
    existing = {(case.rule, case.record_id): case for case in rows(db, Case, actor)}
    for key, (title, amount, explanation) in active.items():
        case = existing.get(key)
        if not case:
            add(db, Case, actor, rule=key[0], record_id=key[1], title=title, amount_minor=amount, explanation=explanation)
        else:
            if case.amount_minor != amount:
                case.version += 1
            case.amount_minor = amount
            if case.status == 'resolved':
                case.status, case.version = 'detected', case.version + 1
    for key, case in existing.items():
        if key not in active and case.status not in ('dismissed', 'intentional', 'resolved'):
            case.status, case.version = 'resolved', case.version + 1
            case.reason = 'Underlying discrepancy no longer present in the recorded ledger.'
    db.flush()


def run_scenario(db, actor, data, persist=True):
    require(actor, 'read_finance')
    business = db.get(Business, actor.business_id)
    opening = business.opening_minor
    start = data['start']
    warnings = ['Coverage: isolated synthetic records only.' if business.mode == 'fixture' else 'Coverage: merchant/imported records; no live bank feed connected.']
    if not business.opening_date or business.opening_date > start:
        opening = None
        warnings.append('Opening balance/as-of date is missing or later than forecast start.')
    receipts = rows(db, Receipt, actor)
    movements = []
    # Reversed originals and their compensating events both remain in historical cash.
    for r in receipts:
        if r.category == 'transfer' or r.status not in ('posted', 'reversed'):
            continue
        value = r.amount_minor * (1 if r.direction == 'in' else -1)
        if opening is not None and business.opening_date <= r.booked_on < start:
            opening += value
        if r.booked_on >= start:
            movements.append({'id': r.id, 'date': r.booked_on.isoformat(), 'amount_minor': value, 'label': r.reference or r.category, 'basis': 'recorded_' + r.source})
    shifts = {s['invoice_id']: s['date'] for s in data['shifts']}
    for iid in shifts:
        scoped(db, Invoice, iid, actor)
    promises = rows(db, Promise, actor)
    for invoice in rows(db, Invoice, actor):
        balance = outstanding(db, invoice)
        if invoice.status != 'issued' or balance <= 0:
            continue
        expected = shifts.get(invoice.id, invoice.due_date)
        basis = 'scenario_date' if invoice.id in shifts else 'contractual_due_date'
        if data['use_promises'] and invoice.id not in shifts:
            candidates = sorted([p for p in promises if p.invoice_id == invoice.id and p.status == 'awaiting_receipt'], key=lambda p: p.created_at, reverse=True)
            if candidates:
                p = candidates[0]
                promised = min(balance, p.amount_minor)
                movements.append({'id': p.id, 'date': max(start, p.promised_on).isoformat(), 'amount_minor': promised * (1 if invoice.direction == 'receivable' else -1), 'label': invoice.number + ' promise', 'basis': 'promise_not_cash'})
                balance -= promised
        if balance:
            if expected < start:
                warnings.append(invoice.number + ': overdue amount assumed at forecast start; timing is uncertain.')
            movements.append({'id': invoice.id, 'date': max(start, expected).isoformat(), 'amount_minor': balance * (1 if invoice.direction == 'receivable' else -1), 'label': invoice.number, 'basis': basis})
    for m in data['movements']:
        if m['date'] < start:
            fail('SCENARIO_DATE', 'Scenario movements cannot precede the forecast start.', 422)
        movements.append({**m, 'date': m['date'].isoformat(), 'basis': 'user_assumption'})
    result = forecast(opening, start, data['horizon'], movements, data['buffer_minor'])
    result.update({'opening_minor': opening, 'buffer_minor': data['buffer_minor'], 'coverage_warnings': warnings, 'baseline_revision': business.revision, 'firm_affordability': False, 'source_as_of': now().isoformat()})
    if persist:
        scenario = add(db, Scenario, actor, name=data['name'], baseline_revision=business.revision, assumptions={**data, 'start': start.isoformat(), 'shifts': [{**s, 'date': s['date'].isoformat()} for s in data['shifts']], 'movements': [{**m, 'date': m['date'].isoformat()} for m in data['movements']]}, result=result)
        return serial(scenario)
    return result


def action_digest(action):
    values = {key: getattr(action, key) for key in ('kind', 'invoice_id', 'invoice_version', 'recipient_id', 'recipient_version', 'message', 'language')}
    return digest({**values, 'expires_at': aware(action.expires_at).isoformat()})


def create_action(db, actor, data):
    require(actor, 'write_finance')
    party = scoped(db, Counterparty, data['recipient_id'], actor)
    scenario = None
    if data.get('scenario_id'):
        scenario = scoped(db, Scenario, data['scenario_id'], actor)
        if scenario.baseline_revision != db.get(Business, actor.business_id).revision:
            fail('SCENARIO_STALE', 'Business records changed. Recalculate this scenario before proposing terms.')
    if data['kind'] != 'collection_reminder' and not scenario:
        fail('SCENARIO_REQUIRED', 'Terms proposals must reference a current calculated scenario.', 422)
    if data['kind'] == 'collection_reminder' and not data['invoice_id']:
        fail('INVOICE_REQUIRED', 'Collection reminders require an invoice.', 422)
    invoice = None
    if data['invoice_id']:
        invoice = scoped(db, Invoice, data['invoice_id'], actor)
        version(invoice, data['expected_invoice_version'])
        if invoice.counterparty_id != party.id or invoice.status != 'issued':
            fail('RECIPIENT_MISMATCH', 'Recipient must own the issued invoice.', 422)
        if invoice.disputed or outstanding(db, invoice) <= 0:
            fail('NO_COLLECTION', 'Invoice is paid or disputed; ordinary collection is not permitted.')
    action = add(db, Action, actor, kind=data['kind'], invoice_id=data['invoice_id'], invoice_version=invoice.version if invoice else None, recipient_id=party.id, recipient_version=party.version, message=data['message'], language=data['language'], payload_digest='', expires_at=now() + timedelta(minutes=data['expires_minutes']))
    # Canonicalize timestamp for identical digests across SQLite/Postgres reloads.
    action.payload_digest = action_digest(action)
    audit(db, actor, 'ActionDrafted', action)
    if scenario:
        add(db, Supplement, actor, kind='action_precondition', status='active', data={'action_id': action.id, 'scenario_id': scenario.id, 'revision_after_draft': db.get(Business, actor.business_id).revision})
    return serial(action)


def check_action(db, actor, action):
    actor = current_actor(db, actor)
    require(actor, 'approve')
    if db.get(Business, actor.business_id).paused:
        fail('PAUSED', 'External actions are paused.', 403)
    if aware(action.expires_at) <= now():
        fail('APPROVAL_EXPIRED', 'This proposal has expired. Prepare a new one.')
    if action.payload_digest != action_digest(action):
        fail('PAYLOAD_CHANGED', 'Proposal content changed. Review a new version.')
    for precondition in rows(db, Supplement, actor):
        if precondition.kind == 'action_precondition' and precondition.data['action_id'] == action.id:
            expected = precondition.data.get('revision_after_approval', precondition.data['revision_after_draft'])
            if db.get(Business, actor.business_id).revision != expected:
                fail('SCENARIO_STALE', 'Business records changed after this proposal. Recalculate and review new terms.')
    party = scoped(db, Counterparty, action.recipient_id, actor)
    if party.version != action.recipient_version:
        fail('RECIPIENT_CHANGED', 'Recipient binding changed. Review a fresh action.')
    if action.invoice_id:
        invoice = scoped(db, Invoice, action.invoice_id, actor)
        if invoice.version != action.invoice_version or invoice.disputed or invoice.status != 'issued' or outstanding(db, invoice) <= 0:
            fail('APPROVAL_STALE', 'Invoice changed, is disputed or has been paid. Review a new draft.')
    return party


def approve_action(db, actor, action_id, data):
    require(actor, 'approve')
    action = scoped(db, Action, action_id, actor)
    version(action, data['expected_version'])
    if action.status != 'approval_required':
        fail('APPROVAL_REPLAY', 'This proposal cannot be approved again.')
    check_action(db, actor, action)
    if action.payload_digest != data['payload_digest']:
        fail('PAYLOAD_CHANGED', 'Approve the exact displayed content.')
    action.approved_by, action.approved_digest, action.status = actor.user_id, action.payload_digest, 'queued'
    action.version += 1
    add(db, Job, actor, kind='execute_action', record_id=action.id)
    audit(db, actor, 'ActionApproved', action, digest=action.payload_digest)
    for precondition in rows(db, Supplement, actor):
        if precondition.kind == 'action_precondition' and precondition.data['action_id'] == action.id:
            precondition.data = {**precondition.data, 'revision_after_approval': db.get(Business, actor.business_id).revision}
    return serial(action)


def query_metric(db, actor, data):
    require(actor, 'read_finance')
    if (data['end'] - data['start']).days not in range(0, 3661):
        fail('PERIOD_INVALID', 'Choose a date range up to ten years.', 422)
    metric = data['metric']
    if not metric:
        q = data['question'].lower()
        if any(s in q for s in ('select ', 'drop ', 'sql', 'other business', 'ignore', 'bank account')):
            return {'clarification': 'Only approved financial metrics are available. Choose sales, receipts, outstanding or cash bridge.'}
        if any(s in q for s in ('profit', 'untung', '利润')):
            return {'clarification': 'Profit needs cost and inventory coverage. Sales and receipts alone cannot establish net profit.'}
        choices = [('sales', ['sales', 'jualan', '销售']), ('cash_received', ['received', 'terima', '收款']), ('outstanding', ['outstanding', 'baki', '欠款']), ('cash_bridge', ['money go', 'cash', 'duit', '现金'])]
        matches = {key for key, words in choices if any(w in q for w in words)}
        if len(matches) != 1:
            return {'clarification': 'Do you mean recorded sales, cash received, outstanding invoices or cash movement?'}
        metric = matches.pop()
    business = db.get(Business, actor.business_id)
    invoices = rows(db, Invoice, actor)
    receipts = [r for r in rows(db, Receipt, actor) if data['start'] <= r.booked_on <= data['end'] and r.status in ('posted', 'reversed') and r.category != 'transfer']
    source_ids = []
    if metric == 'sales':
        chosen = [i for i in invoices if i.status == 'issued' and i.direction == 'receivable' and data['start'] <= i.issued_on <= data['end']]
        value = sum(i.total_minor for i in chosen)
        credits = [a for a in rows(db, Adjustment, actor) if a.kind == 'credit' and data['start'] <= aware(a.created_at).astimezone(ZoneInfo(business.timezone)).date() <= data['end']]
        value -= sum(a.amount_minor for a in credits)
        source_ids = [i.id for i in chosen] + [a.id for a in credits]
        definition = 'Issued receivable invoice totals in period minus credit notes recorded in period; write-offs separate.'
    elif metric == 'cash_received':
        chosen = [r for r in receipts if r.category == 'customer_receipt']
        value = sum(r.amount_minor * (1 if r.direction == 'in' else -1) for r in chosen)
        source_ids = [r.id for r in chosen]
        definition = 'Recorded customer receipts, net of receipt reversals; excludes transfers and loans.'
    elif metric == 'outstanding':
        chosen = [i for i in invoices if i.status == 'issued' and i.direction == 'receivable']
        value = sum(outstanding(db, i) for i in chosen)
        source_ids = [i.id for i in chosen]
        definition = 'Current issued receivables less active allocations and approved adjustments; not a historical snapshot.'
    else:
        opening = business.opening_minor if business.opening_date and business.opening_date <= data['start'] else None
        if opening is not None:
            for r in rows(db, Receipt, actor):
                if business.opening_date <= r.booked_on < data['start'] and r.category != 'transfer' and r.status in ('posted', 'reversed'):
                    opening += r.amount_minor * (1 if r.direction == 'in' else -1)
        components = {}
        for r in receipts:
            components[r.category] = components.get(r.category, 0) + r.amount_minor * (1 if r.direction == 'in' else -1)
        net = sum(components.values())
        result = {'opening_minor': opening, 'net_minor': net, 'closing_minor': None if opening is None else opening + net, 'components': components}
        value, source_ids, definition = result['closing_minor'], [r.id for r in receipts], 'Cash movements within recorded account coverage; opening is at start of day. Internal transfers net to zero.'
    response = {'metric': metric, 'amount_minor': value, 'currency': 'MYR', 'definition': definition, 'definition_version': metric + '_v1', 'period': [str(data['start']), str(data['end'])], 'timezone': business.timezone, 'source_ids': source_ids, 'coverage': 'fixture_only' if business.mode == 'fixture' else 'recorded_data_only_no_live_feed', 'source_as_of': now().isoformat()}
    if metric == 'cash_bridge':
        response.update(result)
    run = add(db, Supplement, actor, kind='query_run', status='calculated', data=response)
    return {**response, 'query_run_id': run.id}


def import_statement(db, actor, data):
    require(actor, 'write_finance')
    try:
        reader = csv.DictReader(io.StringIO(data['csv_text']))
        if set(reader.fieldnames or []) != {'transaction_id', 'date', 'amount_minor', 'direction', 'category', 'reference'}:
            fail('CSV_COLUMNS', 'Required headers: transaction_id,date,amount_minor,direction,category,reference', 422)
        from .schemas import ReceiptIn
        parsed = [ReceiptIn(account=data['account'], source_event_id=r['transaction_id'], source='statement_import', amount_minor=int(r['amount_minor']), booked_on=r['date'], direction=r['direction'], category=r['category'], reference=r['reference']).model_dump() for r in reader]
        if len(parsed) > 1000 or not parsed:
            fail('CSV_ROWS', 'Import between 1 and 1,000 rows.', 422)
    except (ValueError, TypeError, KeyError):
        fail('CSV_INVALID', 'Check dates, integer sen, directions and categories.', 422)
    if not data['confirm']:
        return {'rows': [{**r, 'booked_on': str(r['booked_on'])} for r in parsed], 'assurance': 'Uploaded statement; not independently verified', 'confirmed': False}
    business = db.get(Business, actor.business_id)
    if business.mode == 'fixture':
        fail('SOURCE_MODE', 'Import into a new business, not the isolated fixture business.', 403)
    content_hash = digest(data['csv_text'])
    ev = db.scalar(select(Evidence).where(Evidence.business_id == actor.business_id, Evidence.content_hash == content_hash))
    if not ev:
        ev = add(db, Evidence, actor, kind='statement', source='statement_import', content_hash=content_hash, text=data['csv_text'], creator_id=actor.user_id, status='reviewed')
    result = [create_receipt(db, actor, {**r, 'evidence_id': ev.id}) for r in parsed]
    return {'confirmed': True, 'receipts': result, 'assurance': 'Uploaded statement; not independently verified'}
