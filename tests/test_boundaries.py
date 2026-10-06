from datetime import date, timedelta
from uuid import uuid4
import httpx
from sqlalchemy import select
from services.api import telegram, worker, main, domain as d
from services.api.models import *
from services.api.security import token_hash, Actor
from test_workflows import register, setup, post, allocation, draft_action, DAY


def test_one_receipt_covers_three_invoices(env):
    c = env[0]
    _, party, first, receipt = setup(c, env)
    lines = [{'invoice_id': first['id'], 'expected_invoice_version': first['version'], 'amount_minor': 100000}]
    for n in range(2):
        row = post(c, 'invoices', {'counterparty_id': party['id'], 'number': 'EXTRA' + str(n), 'total_minor': 100000, 'issued_on': str(DAY), 'due_date': str(DAY)})
        row = post(c, f"invoices/{row['id']}/issue", {'expected_version': 1})
        lines.append({'invoice_id': row['id'], 'expected_invoice_version': row['version'], 'amount_minor': 100000})
    result = post(c, 'reconciliations', {'receipt_id': receipt['id'], 'expected_receipt_version': 1, 'allocations': lines, 'reason': 'Combined remittance explicitly reviewed'})
    assert sum(a['amount_minor'] for a in result['allocations']) == 300000
    assert result['unapplied_minor'] == 0


def test_sales_scope_and_unauthorized_approval(env):
    c, factory, tx = env
    me, party, invoice, receipt = setup(c, env)
    action = draft_action(c, party, invoice)
    with tx() as db:
        db.get(Membership, (me['business']['id'], me['user']['id'])).role = 'sales'
    assert c.get('/v1/dashboard').status_code == 403
    assert c.get('/v1/records/counterparties').json()['items'] == []
    assert c.get('/v1/records/receipts').status_code == 403
    post(c, f"actions/{action['id']}/approve", {'expected_version': 1, 'payload_digest': action['payload_digest']}, expected=403)


def test_webhook_auth_persist_dedupe(env, monkeypatch):
    c, factory, tx = env
    monkeypatch.setattr(main.settings, 'telegram_mode', 'webhook')
    monkeypatch.setattr(main.settings, 'telegram_id', 'test')
    monkeypatch.setattr(main.settings, 'webhook_secret', 'test-secret')
    update = {'update_id': 42, 'message': {'chat': {'id': 1, 'type': 'private'}, 'from': {'id': 1}, 'text': 'unbound'}}
    assert c.post('/v1/channels/telegram/webhook', json=update).status_code == 403
    assert c.post('/v1/channels/telegram/webhook', json=update, headers={'x-telegram-bot-api-secret-token': 'test-secret'}).json()['accepted']
    assert not c.post('/v1/channels/telegram/webhook', json=update, headers={'x-telegram-bot-api-secret-token': 'test-secret'}).json()['accepted']
    with factory() as db:
        assert db.get(TelegramInbox, ('test', 42)).status == 'queued'


def test_callback_actor_chat_expiry_and_replay(env, monkeypatch):
    c, factory, tx = env
    me, party, invoice, receipt = setup(c, env)
    action = draft_action(c, party, invoice)
    actor = Actor(me['user']['id'], me['business']['id'], 'owner')
    with tx() as db:
        d.add(db, Binding, actor, user_id=actor.user_id, telegram_user_id='100', chat_id='100')
        d.add(db, Callback, actor, token_hash=token_hash('good-token'), action_id=action['id'], user_id=actor.user_id, chat_id='100', digest=action['payload_digest'], expires_at=now()+timedelta(minutes=5))
    class Fake:
        def call(self, *args, **kwargs):
            return {}
    monkeypatch.setattr(telegram, 'TelegramClient', Fake)
    wrong = {'callback_query': {'id': 'callback', 'from': {'id': 999}, 'data': 'good-token', 'message': {'chat': {'id': 999, 'type': 'private'}}}}
    telegram.process_update(wrong)
    with factory() as db:
        assert db.get(Action, action['id']).status == 'approval_required'
    good = {'callback_query': {'id': 'callback', 'from': {'id': 100}, 'data': 'good-token', 'message': {'chat': {'id': 100, 'type': 'private'}}}}
    telegram.process_update(good)
    with factory() as db:
        assert db.get(Action, action['id']).status == 'queued'
    import pytest
    with pytest.raises(ValueError):
        telegram.process_update(good)


def test_telegram_timeout_is_unknown_and_bad_file_path_denied(env, monkeypatch):
    monkeypatch.setattr(telegram.settings, 'telegram_token', 'test-only-not-real')
    def timeout(request):
        raise httpx.ReadTimeout('connection interrupted')
    client = telegram.TelegramClient(transport=httpx.MockTransport(timeout))
    import pytest
    with pytest.raises(telegram.UnknownOutcome):
        client.send('100', 'synthetic test')
    def unsafe(request):
        return httpx.Response(200, json={'ok': True, 'result': {'file_path': '../secret'}})
    client = telegram.TelegramClient(transport=httpx.MockTransport(unsafe))
    with pytest.raises(ValueError):
        client.download('file1')


def test_expired_read_job_recovers_without_external_retry(env):
    c, factory, tx = env
    register(c)
    ev = post(c, 'evidence', {'text': '20 crates @ RM60 per crate'})
    with tx() as db:
        job = db.scalar(select(Job).where(Job.record_id == ev['id']))
        job.status, job.lease_until = 'processing', now()-timedelta(seconds=1)
    assert worker.tick()
    with factory() as db:
        assert db.get(Evidence, ev['id']).status == 'needs_review'


def test_android_claim_boundary_allowlist_revocation_and_otp(env):
    c, factory, tx = env
    me, party, invoice, receipt = setup(c, env)
    device = post(c, 'android/devices', {'name': 'Test device', 'allowed_packages': ['test.payment.app']})
    headers = {'x-device-token': device['token']}
    payload = {'package_name': 'test.payment.app', 'source_event_id': 'one', 'text': 'Received RM8000', 'occurred_at': now().isoformat()}
    first = c.post('/v1/android/notifications', json=payload, headers=headers)
    assert first.status_code == 200
    assert c.post('/v1/android/notifications', json=payload, headers=headers).json()['id'] == first.json()['id']
    assert c.post('/v1/android/notifications', json={**payload, 'text': 'Your OTP is 123456'}, headers=headers).status_code == 422
    assert c.post('/v1/android/notifications', json={**payload, 'package_name': 'private.messages'}, headers=headers).status_code == 403
    assert c.get(f"/v1/invoices/{invoice['id']}/evidence").json()['invoice']['outstanding_minor'] == 800000
    post(c, f"android/devices/{device['device_id']}/revoke", {'reason': 'Device disabled'})
    assert c.post('/v1/android/notifications', json=payload, headers=headers).status_code == 401


def test_einvoice_submit_fails_closed_and_no_fabricated_validation(env):
    c = env[0]
    _, _, invoice, _ = setup(c, env)
    row = post(c, 'einvoices', {'invoice_id': invoice['id'], 'seller_tax_id': 'TESTSELLER', 'buyer_tax_id': 'TESTBUYER'})
    checked = post(c, f"einvoices/{row['id']}/validate")
    assert checked['status'] == 'local_fields_checked'
    post(c, f"einvoices/{row['id']}/submit", expected=503)
    records = c.get('/v1/records/supplements').json()['items']
    assert records[0]['data']['provider_status'] == 'not_submitted'


def test_exact_cash_bridge_fixture():
    from services.api.finance import forecast
    values = [700000, -400000, -200000, -50000, -100000]
    movements = [{'date': str(DAY), 'amount_minor': v, 'label': 'fixture'} for v in values]
    result = forecast(500000, DAY, 7, movements, 0)
    assert result['daily'][0]['closing_minor'] == 450000


def test_delivery_case_dedup_and_link_closure(env):
    c = env[0]
    _, party, _, _ = setup(c, env)
    deal = post(c, 'deals', {'counterparty_id': party['id'], 'title': '20 crates', 'items': [{'product': 'greens', 'quantity': '20', 'unit': 'crate', 'unit_price_minor': 6000}]})
    post(c, f"deals/{deal['id']}/confirm", {'expected_version': 1, 'due_date': str(DAY), 'delivery_date': str(DAY), 'charges': 'none'})
    post(c, 'deliveries', {'deal_id': deal['id'], 'accepted_quantity': '20', 'delivered_on': str(DAY)})
    post(c, 'cases/detect')
    post(c, 'cases/detect')
    cases = [r for r in c.get('/v1/records/cases').json()['items'] if r['rule'] == 'delivered_unbilled']
    assert len(cases) == 1
    invoice = post(c, 'invoices', {'counterparty_id': party['id'], 'number': 'EXISTING', 'total_minor': 120000, 'issued_on': str(DAY), 'due_date': str(DAY)})
    post(c, f"invoices/{invoice['id']}/issue", {'expected_version': 1})
    result = post(c, f"cases/{cases[0]['id']}/link-invoice", {'invoice_id': invoice['id'], 'expected_version': cases[0]['version'], 'reason': 'Located the existing invoice'})
    assert result['status'] == 'resolved'
