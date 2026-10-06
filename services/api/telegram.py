"""Telegram transport: durable inbox, private binding, safe media and opaque approvals."""
import argparse
import json
import secrets
import time
from hashlib import sha256
from pathlib import PurePosixPath
import httpx
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from .config import settings
from .db import transaction, Session, migrate
from .models import *
from .security import Actor, aware, token_hash, require, fail
from . import domain as d


class UnknownOutcome(Exception):
    pass


class TelegramClient:
    def __init__(self, transport=None):
        if not settings.telegram_token:
            raise ValueError('TELEGRAM_BOT_TOKEN is not configured')
        self.client = httpx.Client(timeout=40, transport=transport)

    def call(self, method, payload=None, write=False):
        try:
            response = self.client.post('https://api.telegram.org/bot' + settings.telegram_token + '/' + method, json=payload or {})
            if response.status_code >= 500 and write:
                raise UnknownOutcome()
            data = response.json()
            if isinstance(data, dict) and data.get('ok') is False:
                raise ValueError('Telegram rejected operation')
            if not isinstance(data, dict) or data.get('ok') is not True or 'result' not in data:
                if write:
                    raise UnknownOutcome()
                raise RuntimeError('Malformed Telegram response')
            return data['result']
        except (httpx.TransportError, json.JSONDecodeError):
            if write:
                raise UnknownOutcome() from None
            raise RuntimeError('Telegram read failed') from None

    def send(self, chat_id, text, reply_markup=None):
        payload = {'chat_id': chat_id, 'text': text}
        if reply_markup:
            payload['reply_markup'] = reply_markup
        return self.call('sendMessage', payload, write=True)

    def download(self, file_id):
        result = self.call('getFile', {'file_id': file_id})
        path = PurePosixPath(result['file_path'])
        if path.is_absolute() or '..' in path.parts or '\\' in str(path) or ':' in str(path) or result.get('file_size', 0) > 8 * 1024 * 1024:
            raise ValueError('Unsafe or oversized media path')
        content = bytearray()
        with self.client.stream('GET', 'https://api.telegram.org/file/bot' + settings.telegram_token + '/' + str(path)) as response:
            response.raise_for_status()
            for block in response.iter_bytes():
                content.extend(block)
                if len(content) > 8 * 1024 * 1024:
                    raise ValueError('Telegram media exceeds 8 MB')
        return bytes(content), str(path)


def accept_update(update):
    if not isinstance(update, dict) or type(update.get('update_id')) is not int or update['update_id'] < 0:
        fail('UPDATE_INVALID', 'Invalid Telegram update.', 422)
    try:
        with transaction() as db:
            if db.get(TelegramInbox, (settings.telegram_id, update['update_id'])):
                return False
            db.add(TelegramInbox(bot_id=settings.telegram_id, update_id=update['update_id'], payload=update))
        return True
    except IntegrityError:
        return False


def process_one():
    with transaction() as db:
        row = db.scalar(select(TelegramInbox).where(TelegramInbox.status == 'queued', TelegramInbox.bot_id == settings.telegram_id).order_by(TelegramInbox.update_id).with_for_update(skip_locked=True).limit(1))
        if not row:
            return False
        row.status = 'processing'
        update, update_id = row.payload, row.update_id
    # Crash during Telegram processing leaves explicit processing/unknown state;
    # no automatic replay of potentially completed sends.
    try:
        process_update(update)
        state, error = 'completed', None
    except UnknownOutcome:
        state, error = 'outcome_unknown', 'Telegram response delivery is uncertain; do not blindly replay.'
    except Exception:
        state, error = 'needs_review', 'Check binding, permissions, update or media. Raw content omitted.'
    with transaction() as db:
        row = db.get(TelegramInbox, (settings.telegram_id, update_id))
        row.status, row.error = state, error
    return True


def process_update(update):
    callback = update.get('callback_query')
    message = callback.get('message', {}) if callback else update.get('message', update.get('edited_message', {}))
    sender = callback.get('from', {}) if callback else message.get('from', {})
    chat = message.get('chat', {})
    if chat.get('type') != 'private' or str(chat.get('id')) != str(sender.get('id')):
        # Fail closed for shared rooms. No financial response is sent.
        return
    user_id, chat_id = str(sender['id']), str(chat['id'])
    text = message.get('text', '')
    client = TelegramClient()
    if text.startswith('/connect '):
        with transaction() as db:
            invite = db.scalar(select(RecipientInvite).where(RecipientInvite.token_hash == token_hash(text[9:].strip())).with_for_update())
            if not invite or invite.status != 'awaiting_recipient' or aware(invite.expires_at) <= now():
                raise ValueError('Invalid recipient invite')
            invite.telegram_user_id, invite.chat_id, invite.status = user_id, chat_id, 'owner_review_required'
            invite.version += 1
        client.send(chat_id, 'Connection request saved. The business owner must independently verify and approve this chat before sharing records or sending proposals.')
        return
    if text.startswith(('/deal ', '/confirm ')):
        parts = text.split()
        if len(parts) not in (2, 3):
            raise ValueError('Specify deal ID and, for confirmation, exact version')
        with transaction() as db:
            invitations = list(db.scalars(select(RecipientInvite).where(RecipientInvite.telegram_user_id == user_id, RecipientInvite.chat_id == chat_id, RecipientInvite.status == 'confirmed')))
            deal = db.get(Deal, parts[1])
            invite = next((r for r in invitations if deal and r.business_id == deal.business_id and r.counterparty_id == deal.counterparty_id), None)
            if not invite or deal.status != 'confirmed':
                raise ValueError('No authorized confirmed deal')
            if text.startswith('/confirm '):
                if len(parts) != 3 or not parts[2].isdigit() or int(parts[2]) != deal.version:
                    raise ValueError('Deal version changed or unspecified')
                actor = Actor('telegram-recipient:' + user_id, deal.business_id, 'customer')
                if deal.confirmation_level != 'both_parties_confirmed':
                    d.add(db, Supplement, actor, kind='counterparty_confirmation', status='confirmed', data={'deal_id': deal.id, 'terms_version': deal.version, 'telegram_user_id': user_id, 'chat_id': chat_id})
                    deal.confirmation_level = 'both_parties_confirmed'
                    d.audit(db, actor, 'CounterpartyConfirmedExactTerms', deal, terms_version=deal.version)
                response = 'Your confirmation of deal version ' + str(deal.version) + ' is recorded. No payment has been recorded by this confirmation.'
            else:
                from decimal import Decimal
                response = f'Deal {deal.id}\n{deal.title}\nVersion {deal.version}\nTotal RM{Decimal(deal.total_minor)/100:,.2f}\nDelivery {deal.delivery_date}\nBalance due {deal.due_date}\nItems: ' + '; '.join(f"{i['quantity']} {i['unit']} {i['product']}" for i in deal.terms['items']) + f'\nTo confirm these exact terms, send /confirm {deal.id} {deal.version}'
        client.send(chat_id, response)
        return
    if text.startswith('/bind '):
        with transaction() as db:
            code = db.scalar(select(BindCode).where(BindCode.code_hash == token_hash(text[6:].strip())).with_for_update())
            if not code or code.consumed or aware(code.expires_at) <= now():
                raise ValueError('Invalid binding code')
            member = db.get(Membership, (code.business_id, code.user_id))
            if not member or not member.active:
                raise ValueError('Inactive membership')
            existing = db.scalar(select(Binding).where(Binding.telegram_user_id == user_id))
            if existing and (existing.user_id != code.user_id or existing.business_id != code.business_id):
                raise ValueError('Rebinding requires owner recovery')
            if not existing:
                d.add(db, Binding, Actor(code.user_id, code.business_id, member.role), user_id=code.user_id, telegram_user_id=user_id, chat_id=chat_id)
            code.consumed = True
        client.send(chat_id, 'KedaiFlow connected to your authenticated business. Only your private chat can access this binding.')
        return
    with Session() as db:
        binding = db.scalar(select(Binding).where(Binding.telegram_user_id == user_id, Binding.chat_id == chat_id, Binding.active.is_(True)))
        if not binding:
            return
        member = db.get(Membership, (binding.business_id, binding.user_id))
        if not member or not member.active:
            return
        actor = Actor(binding.user_id, binding.business_id, member.role)
    if callback:
        with transaction(business_id=actor.business_id) as db:
            token = db.scalar(select(Callback).where(Callback.token_hash == token_hash(callback.get('data', '')), Callback.business_id == actor.business_id))
            if not token or token.consumed or token.user_id != actor.user_id or token.chat_id != chat_id or aware(token.expires_at) <= now():
                raise ValueError('Invalid approval callback')
            action = d.scoped(db, Action, token.action_id, actor)
            d.approve_action(db, actor, action.id, {'expected_version': action.version, 'payload_digest': token.digest})
            token.consumed = True
        client.call('answerCallbackQuery', {'callback_query_id': callback['id'], 'text': 'Exact proposal approved. Worker will recheck current state.'}, write=True)
        return
    if text.startswith('/review '):
        require(actor, 'approve')
        with transaction(business_id=actor.business_id) as db:
            action = d.scoped(db, Action, text[8:].strip(), actor)
            if action.status != 'approval_required':
                raise ValueError('Not pending approval')
            recipient = d.scoped(db, Counterparty, action.recipient_id, actor)
            token = secrets.token_urlsafe(24)
            d.add(db, Callback, actor, token_hash=token_hash(token), action_id=action.id, user_id=actor.user_id, chat_id=chat_id, digest=action.payload_digest, expires_at=min(aware(action.expires_at), now() + timedelta(minutes=5)))
            preview = f'Recipient: {recipient.name}\nMode: {settings.action_mode}\nKind: {action.kind}\n\n{action.message}\n\nApproval authorizes this exact version only.'
        client.send(chat_id, preview, {'inline_keyboard': [[{'text': 'Approve exact proposal', 'callback_data': token}]]})
        return
    if text.startswith('/money'):
        require(actor, 'read_finance')
        with transaction(business_id=actor.business_id) as db:
            day = now().date()
            result = d.query_metric(db, actor, {'metric': 'outstanding', 'question': '', 'start': day, 'end': day})
        client.send(chat_id, f"Recorded outstanding: RM{result['amount_minor'] / 100:,.2f}. Coverage: {result['coverage']}. Promise and screenshot claims are not receipts.")
        return
    media = message.get('voice') or message.get('document') or (message.get('photo') or [None])[-1]
    if media:
        if media.get('file_size', 0) > 8 * 1024 * 1024 or media.get('duration', 0) > 180:
            raise ValueError('Media exceeds limit')
        content, path = client.download(media['file_id'])
        mime = media.get('mime_type', 'image/jpeg' if message.get('photo') else 'audio/ogg')
        if mime not in ('application/pdf', 'image/jpeg', 'image/png', 'audio/ogg', 'audio/mpeg', 'audio/wav', 'audio/mp4'):
            raise ValueError('Unsupported media')
        from .media import validate_media
        validate_media(content, mime)
        hashed = sha256(content).hexdigest()
        with transaction(business_id=actor.business_id) as db:
            require(actor, 'trade')
            ev = db.scalar(select(Evidence).where(Evidence.business_id == actor.business_id, Evidence.content_hash == hashed))
            if not ev:
                key = actor.business_id + '/' + hashed
                target = settings.media / key
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content)
                ev = d.add(db, Evidence, actor, kind='voice' if mime.startswith('audio') else 'document', source='telegram', content_hash=hashed, filename=PurePosixPath(path).name, media_type=mime, storage_key=key, creator_id=actor.user_id)
                d.add(db, Job, actor, kind='extract', record_id=ev.id)
            evidence_id = ev.id
    else:
        if not text:
            return
        with transaction(business_id=actor.business_id) as db:
            from .schemas import EvidenceIn
            result = d.create_evidence(db, actor, EvidenceIn(text=text).model_dump())
            evidence_id = result['id']
    client.send(chat_id, 'Evidence saved privately. Review extracted terms in KedaiFlow before confirming. Evidence: ' + evidence_id)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['identity', 'poll', 'webhook-info', 'set-webhook', 'delete-webhook'])
    args = parser.parse_args()
    client = TelegramClient()
    if args.command == 'identity':
        identity = client.call('getMe')
        print(json.dumps({'id': identity['id'], 'username': identity.get('username')}))
    elif args.command == 'webhook-info':
        result = client.call('getWebhookInfo')
        print(json.dumps({'configured': bool(result.get('url')), 'pending_update_count': result.get('pending_update_count')}))
    elif args.command == 'set-webhook':
        import os
        url = os.getenv('APP_BASE_URL', '')
        if not url.startswith('https://') or not settings.webhook_secret or settings.telegram_mode != 'webhook':
            raise ValueError('HTTPS APP_BASE_URL, secret and webhook mode required; stop poller first')
        client.call('setWebhook', {'url': url.rstrip('/') + '/v1/channels/telegram/webhook', 'secret_token': settings.webhook_secret, 'drop_pending_updates': False, 'allowed_updates': ['message', 'edited_message', 'callback_query']}, write=True)
        print('Webhook registered; pending updates retained.')
    elif args.command == 'delete-webhook':
        client.call('deleteWebhook', {'drop_pending_updates': False}, write=True)
        print('Webhook removed; pending updates retained. Set polling mode before starting poller.')
    else:
        if settings.telegram_mode != 'polling' or not settings.telegram_id:
            raise ValueError('Polling mode and TELEGRAM_BOT_ID required')
        if client.call('getWebhookInfo').get('url'):
            raise ValueError('Webhook exists; polling refused')
        migrate()
        offset = None
        while True:
            updates = client.call('getUpdates', {'offset': offset, 'timeout': 25, 'allowed_updates': ['message', 'edited_message', 'callback_query']})
            for update in updates:
                accept_update(update)  # commit before advancing Telegram acknowledgement offset
                offset = update['update_id'] + 1


if __name__ == '__main__':
    main()
