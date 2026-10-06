from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import BigInteger, Boolean, CheckConstraint, Date, DateTime, ForeignKeyConstraint, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def uid():
    return str(uuid4())


def now():
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Identity(Base):
    __tablename__ = 'identities'
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=uid)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(Text, default='')
    name: Mapped[str] = mapped_column(String(100))


class SessionToken(Base):
    __tablename__ = 'sessions'
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Business(Base):
    __tablename__ = 'businesses'
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(150))
    timezone: Mapped[str] = mapped_column(String(64), default='Asia/Kuala_Lumpur')
    currency: Mapped[str] = mapped_column(String(3), default='MYR')
    language: Mapped[str] = mapped_column(String(5), default='en')
    mode: Mapped[str] = mapped_column(String(20), default='fixture')
    paused: Mapped[bool] = mapped_column(Boolean, default=False)
    opening_minor: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    opening_date: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    buffer_minor: Mapped[int] = mapped_column(BigInteger, default=100000)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    quiet_start: Mapped[int] = mapped_column(Integer, default=21)
    quiet_end: Mapped[int] = mapped_column(Integer, default=8)


class Membership(Base):
    __tablename__ = 'memberships'
    business_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    role: Mapped[str] = mapped_column(String(20))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class TenantRecord:
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=uid)
    business_id: Mapped[str] = mapped_column(String(64), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Counterparty(TenantRecord, Base):
    __tablename__ = 'counterparties'
    __table_args__ = (UniqueConstraint('business_id', 'id'),)
    name: Mapped[str] = mapped_column(String(150))
    kind: Mapped[str] = mapped_column(String(20), default='customer')
    language: Mapped[str] = mapped_column(String(5), default='ms')
    assigned_user_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Only authenticated recipient binding can populate this; never an extraction.
    telegram_chat_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    binding_verified: Mapped[bool] = mapped_column(Boolean, default=False)


class Evidence(TenantRecord, Base):
    __tablename__ = 'evidence'
    __table_args__ = (UniqueConstraint('business_id', 'content_hash'), UniqueConstraint('business_id', 'id'))
    kind: Mapped[str] = mapped_column(String(30))
    source: Mapped[str] = mapped_column(String(40), default='merchant_upload')
    content_hash: Mapped[str] = mapped_column(String(64))
    text: Mapped[str] = mapped_column(Text, default='')
    filename: Mapped[str | None] = mapped_column(String(200), nullable=True)
    media_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    storage_key: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default='queued')
    extraction: Mapped[dict] = mapped_column(JSON, default=dict)
    creator_id: Mapped[str] = mapped_column(String(64))


class Deal(TenantRecord, Base):
    __tablename__ = 'deals'
    __table_args__ = (UniqueConstraint('business_id', 'id'), ForeignKeyConstraint(['business_id', 'counterparty_id'], ['counterparties.business_id', 'counterparties.id']))
    counterparty_id: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(180))
    status: Mapped[str] = mapped_column(String(40), default='needs_clarification')
    total_minor: Mapped[int] = mapped_column(BigInteger)
    deposit_minor: Mapped[int] = mapped_column(BigInteger, default=0)
    currency: Mapped[str] = mapped_column(String(3), default='MYR')
    due_date: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    delivery_date: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    terms: Mapped[dict] = mapped_column(JSON)
    evidence_ids: Mapped[list] = mapped_column(JSON, default=list)
    confirmed_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    confirmation_level: Mapped[str] = mapped_column(String(40), default='unconfirmed')


class DealVersion(TenantRecord, Base):
    __tablename__ = 'deal_versions'
    __table_args__ = (UniqueConstraint('business_id', 'deal_id', 'version'),)
    deal_id: Mapped[str] = mapped_column(String(64))
    snapshot: Mapped[dict] = mapped_column(JSON)
    reason: Mapped[str] = mapped_column(Text)


class Delivery(TenantRecord, Base):
    __tablename__ = 'deliveries'
    deal_id: Mapped[str] = mapped_column(String(64))
    accepted_quantity: Mapped[str] = mapped_column(String(40))
    delivered_on: Mapped[datetime] = mapped_column(Date)
    note: Mapped[str] = mapped_column(Text, default='')


class Invoice(TenantRecord, Base):
    __tablename__ = 'invoices'
    __table_args__ = (UniqueConstraint('business_id', 'id'), UniqueConstraint('business_id', 'number'), CheckConstraint('total_minor > 0'), ForeignKeyConstraint(['business_id', 'counterparty_id'], ['counterparties.business_id', 'counterparties.id']))
    number: Mapped[str] = mapped_column(String(80))
    counterparty_id: Mapped[str] = mapped_column(String(64))
    deal_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    deal_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    direction: Mapped[str] = mapped_column(String(10), default='receivable')
    status: Mapped[str] = mapped_column(String(20), default='draft')
    total_minor: Mapped[int] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(String(3), default='MYR')
    issued_on: Mapped[datetime] = mapped_column(Date)
    due_date: Mapped[datetime] = mapped_column(Date)
    disputed: Mapped[bool] = mapped_column(Boolean, default=False)


class Receipt(TenantRecord, Base):
    __tablename__ = 'receipts'
    __table_args__ = (UniqueConstraint('business_id', 'id'), UniqueConstraint('business_id', 'account', 'source_event_id'), CheckConstraint('amount_minor > 0'))
    account: Mapped[str] = mapped_column(String(100))
    source_event_id: Mapped[str] = mapped_column(String(150))
    source: Mapped[str] = mapped_column(String(40))
    amount_minor: Mapped[int] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(String(3), default='MYR')
    booked_on: Mapped[datetime] = mapped_column(Date)
    reference: Mapped[str] = mapped_column(String(200), default='')
    direction: Mapped[str] = mapped_column(String(10), default='in')
    category: Mapped[str] = mapped_column(String(40), default='customer_receipt')
    status: Mapped[str] = mapped_column(String(20), default='posted')
    reversal_of: Mapped[str | None] = mapped_column(String(64), nullable=True)
    evidence_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


class Allocation(TenantRecord, Base):
    __tablename__ = 'allocations'
    __table_args__ = (CheckConstraint('amount_minor > 0'), ForeignKeyConstraint(['business_id', 'receipt_id'], ['receipts.business_id', 'receipts.id']), ForeignKeyConstraint(['business_id', 'invoice_id'], ['invoices.business_id', 'invoices.id']))
    receipt_id: Mapped[str] = mapped_column(String(64))
    invoice_id: Mapped[str] = mapped_column(String(64))
    amount_minor: Mapped[int] = mapped_column(BigInteger)
    reversed: Mapped[bool] = mapped_column(Boolean, default=False)
    reason: Mapped[str] = mapped_column(Text)


class Adjustment(TenantRecord, Base):
    __tablename__ = 'adjustments'
    invoice_id: Mapped[str] = mapped_column(String(64))
    amount_minor: Mapped[int] = mapped_column(BigInteger)
    kind: Mapped[str] = mapped_column(String(20))
    reason: Mapped[str] = mapped_column(Text)


class Claim(TenantRecord, Base):
    __tablename__ = 'claims'
    invoice_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    evidence_id: Mapped[str] = mapped_column(String(64))
    amount_minor: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    status: Mapped[str] = mapped_column(String(40), default='unverified_payment_claim')


class Promise(TenantRecord, Base):
    __tablename__ = 'promises'
    invoice_id: Mapped[str] = mapped_column(String(64))
    amount_minor: Mapped[int] = mapped_column(BigInteger)
    promised_on: Mapped[datetime] = mapped_column(Date)
    note: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default='awaiting_receipt')


class Case(TenantRecord, Base):
    __tablename__ = 'cases'
    __table_args__ = (UniqueConstraint('business_id', 'rule', 'record_id'),)
    rule: Mapped[str] = mapped_column(String(50))
    record_id: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(200))
    amount_minor: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default='detected')
    explanation: Mapped[str] = mapped_column(Text)
    reason: Mapped[str] = mapped_column(Text, default='')
    assigned_to: Mapped[str | None] = mapped_column(String(64), nullable=True)


class Action(TenantRecord, Base):
    __tablename__ = 'actions'
    kind: Mapped[str] = mapped_column(String(40))
    invoice_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    invoice_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    recipient_id: Mapped[str] = mapped_column(String(64))
    recipient_version: Mapped[int] = mapped_column(Integer)
    message: Mapped[str] = mapped_column(Text)
    language: Mapped[str] = mapped_column(String(5))
    payload_digest: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(40), default='approval_required')
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    approved_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    approved_digest: Mapped[str | None] = mapped_column(String(64), nullable=True)
    outcome: Mapped[str] = mapped_column(Text, default='')
    external_id: Mapped[str | None] = mapped_column(String(100), nullable=True)


class Scenario(TenantRecord, Base):
    __tablename__ = 'scenarios'
    name: Mapped[str] = mapped_column(String(100))
    baseline_revision: Mapped[int] = mapped_column(Integer)
    assumptions: Mapped[dict] = mapped_column(JSON)
    result: Mapped[dict] = mapped_column(JSON)


class Supplement(TenantRecord, Base):
    """Non-ledger records: signal evidence, recipes, export and regulatory workflow metadata."""
    __tablename__ = 'supplements'
    kind: Mapped[str] = mapped_column(String(40), index=True)
    status: Mapped[str] = mapped_column(String(40), default='draft')
    data: Mapped[dict] = mapped_column(JSON)


class Audit(TenantRecord, Base):
    __tablename__ = 'audit'
    actor_id: Mapped[str] = mapped_column(String(64))
    event: Mapped[str] = mapped_column(String(80))
    record_id: Mapped[str] = mapped_column(String(64))
    detail: Mapped[dict] = mapped_column(JSON, default=dict)


class Operation(Base):
    __tablename__ = 'operations'
    scope: Mapped[str] = mapped_column(String(240), primary_key=True)
    key: Mapped[str] = mapped_column(String(150), primary_key=True)
    digest: Mapped[str] = mapped_column(String(64))
    result: Mapped[dict] = mapped_column(JSON)


class Job(TenantRecord, Base):
    __tablename__ = 'jobs'
    kind: Mapped[str] = mapped_column(String(40))
    record_id: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(40), default='queued')
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[str | None] = mapped_column(String(200), nullable=True)


class TelegramInbox(Base):
    __tablename__ = 'telegram_inbox'
    bot_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    update_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    payload: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(30), default='queued')
    error: Mapped[str | None] = mapped_column(String(200), nullable=True)


class Binding(TenantRecord, Base):
    __tablename__ = 'bindings'
    __table_args__ = (UniqueConstraint('telegram_user_id'),)
    user_id: Mapped[str] = mapped_column(String(64))
    telegram_user_id: Mapped[str] = mapped_column(String(40))
    chat_id: Mapped[str] = mapped_column(String(40))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class BindCode(TenantRecord, Base):
    __tablename__ = 'bind_codes'
    code_hash: Mapped[str] = mapped_column(String(64), unique=True)
    user_id: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consumed: Mapped[bool] = mapped_column(Boolean, default=False)


class Callback(TenantRecord, Base):
    __tablename__ = 'callbacks'
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    action_id: Mapped[str] = mapped_column(String(64))
    user_id: Mapped[str] = mapped_column(String(64))
    chat_id: Mapped[str] = mapped_column(String(40))
    digest: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consumed: Mapped[bool] = mapped_column(Boolean, default=False)


class RecipientInvite(TenantRecord, Base):
    __tablename__ = 'recipient_invites'
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    counterparty_id: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(30), default='awaiting_recipient')
    telegram_user_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    chat_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
