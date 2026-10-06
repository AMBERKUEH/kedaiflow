-- KedaiFlow 0001: initial schema. Generated from services/api/models.py.

BEGIN;


CREATE TABLE actions (
	kind VARCHAR(40) NOT NULL, 
	invoice_id VARCHAR(64), 
	invoice_version INTEGER, 
	recipient_id VARCHAR(64) NOT NULL, 
	recipient_version INTEGER NOT NULL, 
	message TEXT NOT NULL, 
	language VARCHAR(5) NOT NULL, 
	payload_digest VARCHAR(64) NOT NULL, 
	status VARCHAR(40) NOT NULL, 
	expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	approved_by VARCHAR(64), 
	approved_digest VARCHAR(64), 
	outcome TEXT NOT NULL, 
	external_id VARCHAR(100), 
	id VARCHAR(64) NOT NULL, 
	business_id VARCHAR(64) NOT NULL, 
	version INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
)

;

CREATE INDEX ix_actions_business_id ON actions (business_id);


CREATE TABLE adjustments (
	invoice_id VARCHAR(64) NOT NULL, 
	amount_minor BIGINT NOT NULL, 
	kind VARCHAR(20) NOT NULL, 
	reason TEXT NOT NULL, 
	id VARCHAR(64) NOT NULL, 
	business_id VARCHAR(64) NOT NULL, 
	version INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
)

;

CREATE INDEX ix_adjustments_business_id ON adjustments (business_id);


CREATE TABLE audit (
	actor_id VARCHAR(64) NOT NULL, 
	event VARCHAR(80) NOT NULL, 
	record_id VARCHAR(64) NOT NULL, 
	detail JSON NOT NULL, 
	id VARCHAR(64) NOT NULL, 
	business_id VARCHAR(64) NOT NULL, 
	version INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
)

;

CREATE INDEX ix_audit_business_id ON audit (business_id);


CREATE TABLE bind_codes (
	code_hash VARCHAR(64) NOT NULL, 
	user_id VARCHAR(64) NOT NULL, 
	expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	consumed BOOLEAN NOT NULL, 
	id VARCHAR(64) NOT NULL, 
	business_id VARCHAR(64) NOT NULL, 
	version INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (code_hash)
)

;

CREATE INDEX ix_bind_codes_business_id ON bind_codes (business_id);


CREATE TABLE bindings (
	user_id VARCHAR(64) NOT NULL, 
	telegram_user_id VARCHAR(40) NOT NULL, 
	chat_id VARCHAR(40) NOT NULL, 
	active BOOLEAN NOT NULL, 
	id VARCHAR(64) NOT NULL, 
	business_id VARCHAR(64) NOT NULL, 
	version INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (telegram_user_id)
)

;

CREATE INDEX ix_bindings_business_id ON bindings (business_id);


CREATE TABLE businesses (
	id VARCHAR(64) NOT NULL, 
	name VARCHAR(150) NOT NULL, 
	timezone VARCHAR(64) NOT NULL, 
	currency VARCHAR(3) NOT NULL, 
	language VARCHAR(5) NOT NULL, 
	mode VARCHAR(20) NOT NULL, 
	paused BOOLEAN NOT NULL, 
	opening_minor BIGINT, 
	opening_date DATE, 
	buffer_minor BIGINT NOT NULL, 
	revision INTEGER NOT NULL, 
	quiet_start INTEGER NOT NULL, 
	quiet_end INTEGER NOT NULL, 
	PRIMARY KEY (id)
)

;


CREATE TABLE callbacks (
	token_hash VARCHAR(64) NOT NULL, 
	action_id VARCHAR(64) NOT NULL, 
	user_id VARCHAR(64) NOT NULL, 
	chat_id VARCHAR(40) NOT NULL, 
	digest VARCHAR(64) NOT NULL, 
	expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	consumed BOOLEAN NOT NULL, 
	id VARCHAR(64) NOT NULL, 
	business_id VARCHAR(64) NOT NULL, 
	version INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (token_hash)
)

;

CREATE INDEX ix_callbacks_business_id ON callbacks (business_id);


CREATE TABLE cases (
	rule VARCHAR(50) NOT NULL, 
	record_id VARCHAR(64) NOT NULL, 
	title VARCHAR(200) NOT NULL, 
	amount_minor BIGINT, 
	status VARCHAR(30) NOT NULL, 
	explanation TEXT NOT NULL, 
	reason TEXT NOT NULL, 
	assigned_to VARCHAR(64), 
	id VARCHAR(64) NOT NULL, 
	business_id VARCHAR(64) NOT NULL, 
	version INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (business_id, rule, record_id)
)

;

CREATE INDEX ix_cases_business_id ON cases (business_id);


CREATE TABLE claims (
	invoice_id VARCHAR(64), 
	evidence_id VARCHAR(64) NOT NULL, 
	amount_minor BIGINT, 
	status VARCHAR(40) NOT NULL, 
	id VARCHAR(64) NOT NULL, 
	business_id VARCHAR(64) NOT NULL, 
	version INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
)

;

CREATE INDEX ix_claims_business_id ON claims (business_id);


CREATE TABLE counterparties (
	name VARCHAR(150) NOT NULL, 
	kind VARCHAR(20) NOT NULL, 
	language VARCHAR(5) NOT NULL, 
	assigned_user_id VARCHAR(64), 
	telegram_chat_id VARCHAR(40), 
	binding_verified BOOLEAN NOT NULL, 
	id VARCHAR(64) NOT NULL, 
	business_id VARCHAR(64) NOT NULL, 
	version INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (business_id, id)
)

;

CREATE INDEX ix_counterparties_business_id ON counterparties (business_id);


CREATE TABLE deal_versions (
	deal_id VARCHAR(64) NOT NULL, 
	snapshot JSON NOT NULL, 
	reason TEXT NOT NULL, 
	id VARCHAR(64) NOT NULL, 
	business_id VARCHAR(64) NOT NULL, 
	version INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (business_id, deal_id, version)
)

;

CREATE INDEX ix_deal_versions_business_id ON deal_versions (business_id);


CREATE TABLE deliveries (
	deal_id VARCHAR(64) NOT NULL, 
	accepted_quantity VARCHAR(40) NOT NULL, 
	delivered_on DATE NOT NULL, 
	note TEXT NOT NULL, 
	id VARCHAR(64) NOT NULL, 
	business_id VARCHAR(64) NOT NULL, 
	version INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
)

;

CREATE INDEX ix_deliveries_business_id ON deliveries (business_id);


CREATE TABLE evidence (
	kind VARCHAR(30) NOT NULL, 
	source VARCHAR(40) NOT NULL, 
	content_hash VARCHAR(64) NOT NULL, 
	text TEXT NOT NULL, 
	filename VARCHAR(200), 
	media_type VARCHAR(100), 
	storage_key VARCHAR(100), 
	status VARCHAR(30) NOT NULL, 
	extraction JSON NOT NULL, 
	creator_id VARCHAR(64) NOT NULL, 
	id VARCHAR(64) NOT NULL, 
	business_id VARCHAR(64) NOT NULL, 
	version INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (business_id, content_hash), 
	UNIQUE (business_id, id)
)

;

CREATE INDEX ix_evidence_business_id ON evidence (business_id);


CREATE TABLE identities (
	id VARCHAR(64) NOT NULL, 
	email VARCHAR(254) NOT NULL, 
	password_hash TEXT NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (email)
)

;


CREATE TABLE jobs (
	kind VARCHAR(40) NOT NULL, 
	record_id VARCHAR(64) NOT NULL, 
	status VARCHAR(40) NOT NULL, 
	attempts INTEGER NOT NULL, 
	available_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	lease_until TIMESTAMP WITH TIME ZONE, 
	error VARCHAR(200), 
	id VARCHAR(64) NOT NULL, 
	business_id VARCHAR(64) NOT NULL, 
	version INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
)

;

CREATE INDEX ix_jobs_business_id ON jobs (business_id);


CREATE TABLE memberships (
	business_id VARCHAR(64) NOT NULL, 
	user_id VARCHAR(64) NOT NULL, 
	role VARCHAR(20) NOT NULL, 
	active BOOLEAN NOT NULL, 
	PRIMARY KEY (business_id, user_id)
)

;


CREATE TABLE operations (
	scope VARCHAR(240) NOT NULL, 
	key VARCHAR(150) NOT NULL, 
	digest VARCHAR(64) NOT NULL, 
	result JSON NOT NULL, 
	PRIMARY KEY (scope, key)
)

;


CREATE TABLE promises (
	invoice_id VARCHAR(64) NOT NULL, 
	amount_minor BIGINT NOT NULL, 
	promised_on DATE NOT NULL, 
	note TEXT NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	id VARCHAR(64) NOT NULL, 
	business_id VARCHAR(64) NOT NULL, 
	version INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
)

;

CREATE INDEX ix_promises_business_id ON promises (business_id);


CREATE TABLE receipts (
	account VARCHAR(100) NOT NULL, 
	source_event_id VARCHAR(150) NOT NULL, 
	source VARCHAR(40) NOT NULL, 
	amount_minor BIGINT NOT NULL, 
	currency VARCHAR(3) NOT NULL, 
	booked_on DATE NOT NULL, 
	reference VARCHAR(200) NOT NULL, 
	direction VARCHAR(10) NOT NULL, 
	category VARCHAR(40) NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	reversal_of VARCHAR(64), 
	evidence_id VARCHAR(64), 
	id VARCHAR(64) NOT NULL, 
	business_id VARCHAR(64) NOT NULL, 
	version INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (business_id, id), 
	UNIQUE (business_id, account, source_event_id), 
	CHECK (amount_minor > 0)
)

;

CREATE INDEX ix_receipts_business_id ON receipts (business_id);


CREATE TABLE recipient_invites (
	token_hash VARCHAR(64) NOT NULL, 
	counterparty_id VARCHAR(64) NOT NULL, 
	expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	status VARCHAR(30) NOT NULL, 
	telegram_user_id VARCHAR(40), 
	chat_id VARCHAR(40), 
	id VARCHAR(64) NOT NULL, 
	business_id VARCHAR(64) NOT NULL, 
	version INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (token_hash)
)

;

CREATE INDEX ix_recipient_invites_business_id ON recipient_invites (business_id);


CREATE TABLE scenarios (
	name VARCHAR(100) NOT NULL, 
	baseline_revision INTEGER NOT NULL, 
	assumptions JSON NOT NULL, 
	result JSON NOT NULL, 
	id VARCHAR(64) NOT NULL, 
	business_id VARCHAR(64) NOT NULL, 
	version INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
)

;

CREATE INDEX ix_scenarios_business_id ON scenarios (business_id);


CREATE TABLE sessions (
	token_hash VARCHAR(64) NOT NULL, 
	user_id VARCHAR(64) NOT NULL, 
	expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (token_hash)
)

;


CREATE TABLE supplements (
	kind VARCHAR(40) NOT NULL, 
	status VARCHAR(40) NOT NULL, 
	data JSON NOT NULL, 
	id VARCHAR(64) NOT NULL, 
	business_id VARCHAR(64) NOT NULL, 
	version INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
)

;

CREATE INDEX ix_supplements_business_id ON supplements (business_id);

CREATE INDEX ix_supplements_kind ON supplements (kind);


CREATE TABLE telegram_inbox (
	bot_id VARCHAR(40) NOT NULL, 
	update_id BIGINT NOT NULL, 
	payload JSON NOT NULL, 
	status VARCHAR(30) NOT NULL, 
	error VARCHAR(200), 
	PRIMARY KEY (bot_id, update_id)
)

;


CREATE TABLE deals (
	counterparty_id VARCHAR(64) NOT NULL, 
	title VARCHAR(180) NOT NULL, 
	status VARCHAR(40) NOT NULL, 
	total_minor BIGINT NOT NULL, 
	deposit_minor BIGINT NOT NULL, 
	currency VARCHAR(3) NOT NULL, 
	due_date DATE, 
	delivery_date DATE, 
	terms JSON NOT NULL, 
	evidence_ids JSON NOT NULL, 
	confirmed_by VARCHAR(64), 
	confirmation_level VARCHAR(40) NOT NULL, 
	id VARCHAR(64) NOT NULL, 
	business_id VARCHAR(64) NOT NULL, 
	version INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (business_id, id), 
	FOREIGN KEY(business_id, counterparty_id) REFERENCES counterparties (business_id, id)
)

;

CREATE INDEX ix_deals_business_id ON deals (business_id);


CREATE TABLE invoices (
	number VARCHAR(80) NOT NULL, 
	counterparty_id VARCHAR(64) NOT NULL, 
	deal_id VARCHAR(64), 
	deal_version INTEGER, 
	direction VARCHAR(10) NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	total_minor BIGINT NOT NULL, 
	currency VARCHAR(3) NOT NULL, 
	issued_on DATE NOT NULL, 
	due_date DATE NOT NULL, 
	disputed BOOLEAN NOT NULL, 
	id VARCHAR(64) NOT NULL, 
	business_id VARCHAR(64) NOT NULL, 
	version INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (business_id, id), 
	UNIQUE (business_id, number), 
	CHECK (total_minor > 0), 
	FOREIGN KEY(business_id, counterparty_id) REFERENCES counterparties (business_id, id)
)

;

CREATE INDEX ix_invoices_business_id ON invoices (business_id);


CREATE TABLE allocations (
	receipt_id VARCHAR(64) NOT NULL, 
	invoice_id VARCHAR(64) NOT NULL, 
	amount_minor BIGINT NOT NULL, 
	reversed BOOLEAN NOT NULL, 
	reason TEXT NOT NULL, 
	id VARCHAR(64) NOT NULL, 
	business_id VARCHAR(64) NOT NULL, 
	version INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CHECK (amount_minor > 0), 
	FOREIGN KEY(business_id, receipt_id) REFERENCES receipts (business_id, id), 
	FOREIGN KEY(business_id, invoice_id) REFERENCES invoices (business_id, id)
)

;

CREATE INDEX ix_allocations_business_id ON allocations (business_id);

CREATE TABLE IF NOT EXISTS schema_migrations (version text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now());

INSERT INTO schema_migrations(version) VALUES ('0001');

COMMIT;