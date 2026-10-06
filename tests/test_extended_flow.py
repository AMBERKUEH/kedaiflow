from datetime import timedelta
from sqlalchemy import select
from services.api import telegram, worker, domain as d
from services.api.models import *
from services.api.security import Actor
from test_workflows import setup, post, DAY


def test_recipient_binding_requires_owner_then_exact_terms(env, monkeypatch):
    c, factory, tx = env
    me, party, invoice, receipt = setup(c, env)
    invite = post(c, f"counterparties/{party['id']}/telegram-invite")
    sent = []
    class Fake:
        def send(self, chat, message, reply_markup=None):
            sent.append((chat, message))
    monkeypatch.setattr(telegram, 'TelegramClient', Fake)
    telegram.process_update({'message': {'chat': {'id': 4242, 'type': 'private'}, 'from': {'id': 4242}, 'text': invite['instruction']}})
    pending = c.get('/v1/channels/telegram/recipient-invites').json()['items'][0]
    with factory() as db:
        assert not db.get(Counterparty, party['id']).binding_verified
    post(c, f"channels/telegram/recipient-invites/{invite['id']}/confirm", {'expected_version': pending['version'], 'observed_chat_id': '4242', 'reason': 'Verified intended synthetic recipient'})
    deal = post(c, 'deals', {'counterparty_id': party['id'], 'title': 'Confirmed supply', 'items': [{'product':'tomato','quantity':'10','unit':'crate','unit_price_minor':10000}]})
    post(c, f"deals/{deal['id']}/confirm", {'expected_version':1,'delivery_date':str(DAY),'due_date':str(DAY+timedelta(days=7)),'charges':'none'})
    telegram.process_update({'message': {'chat': {'id':4242,'type':'private'},'from':{'id':4242},'text':f"/deal {deal['id']}"}})
    assert 'Version 2' in sent[-1][1] and 'cash' not in sent[-1][1].lower()
    telegram.process_update({'message': {'chat': {'id':4242,'type':'private'},'from':{'id':4242},'text':f"/confirm {deal['id']} 2"}})
    with factory() as db:
        assert db.get(Deal, deal['id']).confirmation_level == 'both_parties_confirmed'


def test_proposal_binds_current_scenario_and_worker_rechecks(env):
    c, factory, tx = env
    me, party, invoice, receipt = setup(c, env)
    scenario = post(c, 'scenarios', {'start':str(DAY), 'movements':[{'date':str(DAY),'amount_minor':100000,'label':'Proposed deposit'}]})
    proposal = post(c, 'actions', {'kind':'deposit_proposal','scenario_id':scenario['id'],'recipient_id':party['id'],'message':'Proposed deposit RM1,000 on 7 October. Please confirm.'})
    post(c, f"actions/{proposal['id']}/approve", {'expected_version':1,'payload_digest':proposal['payload_digest']})
    worker.tick()
    with factory() as db:
        assert db.get(Action, proposal['id']).status == 'simulated_sent'
    post(c, 'actions', {'kind':'deposit_proposal','scenario_id':scenario['id'],'recipient_id':party['id'],'message':'Old scenario must be refreshed'}, expected=409)


def test_proposal_without_scenario_is_rejected(env):
    c = env[0]
    _, party, _, _ = setup(c, env)
    post(c, 'actions', {'kind':'supplier_extension','recipient_id':party['id'],'message':'Please change terms'}, expected=422)


def test_sales_me_does_not_leak_opening_cash(env):
    c, factory, tx = env
    me, _, _, _ = setup(c, env)
    with tx() as db:
        db.get(Membership,(me['business']['id'],me['user']['id'])).role='sales'
    result=c.get('/v1/me').json()
    assert 'opening_minor' not in result['business'] and 'buffer_minor' not in result['business']
