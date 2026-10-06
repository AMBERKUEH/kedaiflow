from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from argon2 import PasswordHasher
from fastapi import HTTPException, Request
import jwt
from sqlalchemy import select
from .config import settings
from .models import Membership, SessionToken, Business

passwords = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1)


def fail(code, message, status=409):
    raise HTTPException(status, {'code': code, 'message': message})


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), default=str, ensure_ascii=False).encode()).hexdigest()


def token_hash(value):
    return hashlib.sha256(value.encode()).hexdigest()


def aware(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


@dataclass
class Actor:
    user_id: str
    business_id: str
    role: str


PERMISSIONS = {
    'read_finance': {'owner', 'bookkeeper', 'accountant'},
    'write_finance': {'owner', 'bookkeeper'},
    'trade': {'owner', 'bookkeeper', 'sales'},
    'approve': {'owner'},
    'admin': {'owner'},
    'export': {'owner', 'bookkeeper', 'accountant'},
}


def require(actor, permission):
    if actor.role not in PERMISSIONS[permission]:
        fail('FORBIDDEN', 'Your role does not permit this action.', 403)


def resolve_actor(db, request: Request):
    authorization = request.headers.get('authorization', '')
    token = authorization.removeprefix('Bearer ') if authorization.startswith('Bearer ') else request.cookies.get('kf_session', '')
    if not token:
        fail('AUTH_REQUIRED', 'Please sign in.', 401)
    if settings.auth_mode == 'supabase':
        url = os.environ.get('SUPABASE_URL', '')
        if not url.startswith('https://'):
            fail('AUTH_CONFIGURATION', 'Supabase is not configured.', 503)
        try:
            client = jwt.PyJWKClient(url + '/auth/v1/.well-known/jwks.json')
            key = client.get_signing_key_from_jwt(token)
            payload = jwt.decode(token, key.key, algorithms=['ES256', 'RS256'], audience=os.getenv('SUPABASE_JWT_AUDIENCE', 'authenticated'), issuer=url + '/auth/v1', options={'require': ['exp', 'sub']})
            user_id = payload['sub']
        except Exception:
            fail('AUTH_INVALID', 'Session is invalid or expired.', 401)
    else:
        session = db.get(SessionToken, token_hash(token))
        if not session or aware(session.expires_at) <= datetime.now(timezone.utc):
            fail('AUTH_INVALID', 'Session is invalid or expired.', 401)
        user_id = session.user_id
    bid = request.headers.get('x-business-id') or request.cookies.get('kf_business')
    query = select(Membership).where(Membership.user_id == user_id, Membership.active.is_(True))
    if bid:
        query = query.where(Membership.business_id == bid)
    membership = db.scalars(query.order_by(Membership.business_id)).first()
    if not membership:
        fail('FORBIDDEN', 'No active business membership.', 403)
    return Actor(user_id, membership.business_id, membership.role)


def current_actor(db, actor):
    member = db.get(Membership, (actor.business_id, actor.user_id))
    if not member or not member.active:
        fail('MEMBERSHIP_REVOKED', 'Business membership is no longer active.', 403)
    return Actor(actor.user_id, actor.business_id, member.role)


def scoped(db, model, record_id, actor):
    row = db.scalar(select(model).where(model.id == record_id, model.business_id == actor.business_id))
    if row is None:
        fail('NOT_FOUND', 'Record not found in this business.', 404)
    return row
