from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator

Minor = Annotated[int, Field(strict=True, ge=0, le=9000000000000)]
PositiveMinor = Annotated[int, Field(strict=True, gt=0, le=9000000000000)]
Version = Annotated[int, Field(strict=True, ge=1)]


class Model(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Register(Model):
    email: str = Field(min_length=5, max_length=254, pattern=r'^[^\s@]+@[^\s@]+\.[^\s@]+$')
    password: str = Field(min_length=12, max_length=128)
    name: str = Field(min_length=1, max_length=100)
    business_name: str = Field(min_length=1, max_length=150)
    language: Literal['en', 'ms', 'zh'] = 'en'


class Login(Model):
    email: str = Field(max_length=254)
    password: str = Field(max_length=128)


class PartyIn(Model):
    name: str = Field(min_length=1, max_length=150)
    kind: Literal['customer', 'supplier'] = 'customer'
    language: Literal['en', 'ms', 'zh'] = 'ms'
    assigned_user_id: str | None = None


class EvidenceIn(Model):
    text: str = Field(min_length=1, max_length=30000)
    kind: Literal['text', 'payment_claim', 'notification'] = 'text'
    invoice_id: str | None = None
    claimed_minor: Minor | None = None


class Item(Model):
    product: str = Field(min_length=1, max_length=150)
    quantity: str = Field(max_length=24)
    unit: str = Field(min_length=1, max_length=30)
    unit_price_minor: PositiveMinor

    @field_validator('quantity')
    @classmethod
    def quantity_valid(cls, value):
        n = Decimal(value)
        if not n.is_finite() or not 0 < n <= 1000000 or n.as_tuple().exponent < -3:
            raise ValueError('Quantity must be positive with at most three decimals')
        return value


class DealIn(Model):
    counterparty_id: str
    title: str = Field(min_length=1, max_length=180)
    items: list[Item] = Field(min_length=1, max_length=100)
    currency: Literal['MYR'] = 'MYR'
    deposit_minor: Minor = 0
    due_date: date | None = None
    delivery_date: date | None = None
    charges: Literal['included', 'none', 'unknown'] = 'unknown'
    evidence_ids: list[str] = Field(default_factory=list, max_length=30)


class Confirm(Model):
    expected_version: Version
    due_date: date
    delivery_date: date
    charges: Literal['included', 'none']


class Amend(DealIn):
    expected_version: Version
    reason: str = Field(min_length=3, max_length=1000)


class InvoiceIn(Model):
    counterparty_id: str
    deal_id: str | None = None
    number: str = Field(min_length=1, max_length=80)
    direction: Literal['receivable', 'payable'] = 'receivable'
    total_minor: PositiveMinor
    due_date: date
    issued_on: date
    currency: Literal['MYR'] = 'MYR'


class Expected(Model):
    expected_version: Version


class Reason(Expected):
    reason: str = Field(min_length=3, max_length=1000)


class ReceiptIn(Model):
    account: str = Field(min_length=1, max_length=100)
    source_event_id: str = Field(min_length=1, max_length=150)
    source: Literal['simulator', 'statement_import', 'merchant_cash']
    amount_minor: PositiveMinor
    currency: Literal['MYR'] = 'MYR'
    booked_on: date
    reference: str = Field(default='', max_length=200)
    direction: Literal['in', 'out'] = 'in'
    category: Literal['customer_receipt', 'supplier_payment', 'wages', 'expense', 'owner_drawing', 'loan', 'transfer', 'unclassified'] = 'customer_receipt'
    evidence_id: str | None = None


class AllocationLine(Model):
    invoice_id: str
    expected_invoice_version: Version
    amount_minor: PositiveMinor


class Reconcile(Model):
    receipt_id: str
    expected_receipt_version: Version
    allocations: list[AllocationLine] = Field(min_length=1, max_length=100)
    reason: str = Field(min_length=3, max_length=1000)


class DeliveryIn(Model):
    deal_id: str
    accepted_quantity: str = Field(min_length=1, max_length=24)
    delivered_on: date
    note: str = Field(default='', max_length=2000)


class PromiseIn(Model):
    invoice_id: str
    amount_minor: PositiveMinor
    promised_on: date
    note: str = Field(min_length=3, max_length=1000)


class AdjustmentIn(Model):
    invoice_id: str
    expected_version: Version
    amount_minor: PositiveMinor
    kind: Literal['credit', 'write_off']
    reason: str = Field(min_length=3, max_length=1000)


class Movement(Model):
    label: str = Field(min_length=1, max_length=200)
    date: date
    amount_minor: Annotated[int, Field(strict=True, ge=-9000000000000, le=9000000000000)]


class Shift(Model):
    invoice_id: str
    date: date


class ScenarioIn(Model):
    name: str = Field(default='My scenario', min_length=1, max_length=100)
    start: date
    horizon: int = Field(default=30, ge=7, le=90)
    buffer_minor: Minor = 100000
    shifts: list[Shift] = Field(default_factory=list, max_length=100)
    movements: list[Movement] = Field(default_factory=list, max_length=100)
    use_promises: bool = False


class ActionIn(Model):
    kind: Literal['collection_reminder', 'deposit_proposal', 'supplier_extension']
    recipient_id: str
    invoice_id: str | None = None
    expected_invoice_version: Version | None = None
    scenario_id: str | None = None
    message: str = Field(min_length=1, max_length=4000)
    language: Literal['en', 'ms', 'zh'] = 'ms'
    expires_minutes: int = Field(default=30, ge=1, le=1440)


class Approve(Expected):
    payload_digest: str = Field(min_length=64, max_length=64)


class CaseReview(Expected):
    disposition: Literal['under_review', 'validated', 'dismissed', 'intentional', 'insufficient_evidence', 'disputed']
    reason: str = Field(min_length=3, max_length=2000)


class QueryIn(Model):
    question: str = Field(default='', max_length=1000)
    metric: Literal['sales', 'cash_received', 'outstanding', 'cash_bridge'] | None = None
    start: date
    end: date


class SettingsIn(Model):
    opening_minor: Minor | None = None
    opening_date: date | None = None
    buffer_minor: Minor = 100000
    language: Literal['en', 'ms', 'zh'] = 'en'


class MemberIn(Model):
    email: str = Field(max_length=254)
    role: Literal['bookkeeper', 'sales', 'accountant']
    active: bool = True


class BatchIn(Model):
    name: str = Field(min_length=1, max_length=150)
    produced: int = Field(gt=0, le=1000000)
    sold: int = Field(ge=0, le=1000000)
    wasted: int = Field(ge=0, le=1000000)
    ingredient_minor: Minor
    packaging_minor: Minor
    price_minor: PositiveMinor
    complete_costs: bool = False


class SignalIn(Model):
    title: str = Field(min_length=1, max_length=200)
    source_url: str = Field(max_length=1000)
    observed_on: date
    deal_ids: list[str] = Field(max_length=50)
    assumption: str = Field(min_length=3, max_length=2000)


class OutcomeIn(Model):
    status: Literal['replied', 'declined', 'accepted_candidate', 'no_response', 'manual_sent']
    note: str = Field(min_length=3, max_length=2000)


class ImportIn(Model):
    csv_text: str = Field(min_length=1, max_length=200000)
    account: str = Field(min_length=1, max_length=100)
    confirm: bool = False


class EInvoiceIn(Model):
    invoice_id: str
    seller_tax_id: str = Field(default='', max_length=100)
    buyer_tax_id: str = Field(default='', max_length=100)


class PauseIn(Model):
    paused: bool


class RecordOut(BaseModel):
    model_config = ConfigDict(extra='allow')
    id: str
    business_id: str
    version: int
    created_at: datetime


class EvidenceOut(RecordOut):
    kind: str
    source: str
    status: str
    text: str
    extraction: dict


class DealOut(RecordOut):
    counterparty_id: str
    title: str
    status: str
    total_minor: int
    currency: str
    due_date: date | None
    delivery_date: date | None
    confirmation_level: str
    evidence_ids: list[str]


class InvoiceOut(RecordOut):
    number: str
    counterparty_id: str
    status: str
    total_minor: int
    outstanding_minor: int
    payment_state: str
    currency: str
    due_date: date
    direction: str


class ReceiptOut(RecordOut):
    amount_minor: int
    unapplied_minor: int
    source: str
    status: str
    currency: str
    booked_on: date


class ReconciliationOut(BaseModel):
    allocations: list[dict]
    invoices: list[InvoiceOut]
    unapplied_minor: int


class ActionOut(RecordOut):
    kind: str
    recipient_id: str
    message: str
    payload_digest: str
    status: str
    expires_at: datetime
    outcome: str
