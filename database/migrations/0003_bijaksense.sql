-- FLOW additive schema. Existing financial tables are not changed.
-- Run as database owner; backend authorizes every merchant operation.


CREATE TABLE IF NOT EXISTS flow_competitors (
	name VARCHAR(120) NOT NULL,
	url TEXT NOT NULL,
	source_type VARCHAR(20) NOT NULL,
	public_access_confirmed BOOLEAN NOT NULL,
	enabled BOOLEAN NOT NULL,
	last_status VARCHAR(180) NOT NULL,
	last_checked_at TIMESTAMP WITH TIME ZONE,
	id VARCHAR(64) NOT NULL,
	business_id VARCHAR(64) NOT NULL,
	version INTEGER NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (business_id, id),
	UNIQUE (business_id, url)
)

;

CREATE INDEX IF NOT EXISTS ix_flow_competitors_business_id ON flow_competitors (business_id);


CREATE TABLE IF NOT EXISTS flow_ingestion_jobs (
	kind VARCHAR(20) NOT NULL,
	bucket VARCHAR(40) NOT NULL,
	status VARCHAR(30) NOT NULL,
	started_at TIMESTAMP WITH TIME ZONE,
	completed_at TIMESTAMP WITH TIME ZONE,
	result JSON NOT NULL,
	id VARCHAR(64) NOT NULL,
	business_id VARCHAR(64) NOT NULL,
	version INTEGER NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (business_id, kind, bucket)
)

;

CREATE INDEX IF NOT EXISTS ix_flow_ingestion_jobs_status ON flow_ingestion_jobs (status);

CREATE INDEX IF NOT EXISTS ix_flow_ingestion_jobs_business_id ON flow_ingestion_jobs (business_id);


CREATE TABLE IF NOT EXISTS flow_market_insights (
	fingerprint VARCHAR(64) NOT NULL,
	category VARCHAR(30) NOT NULL,
	kind VARCHAR(30) NOT NULL,
	title VARCHAR(500) NOT NULL,
	explanation TEXT NOT NULL,
	uncertainty TEXT NOT NULL,
	evidence_ids JSON NOT NULL,
	metrics JSON NOT NULL,
	relevance JSON NOT NULL,
	generator VARCHAR(120) NOT NULL,
	status VARCHAR(30) NOT NULL,
	feedback TEXT NOT NULL,
	assessed_at TIMESTAMP WITH TIME ZONE NOT NULL,
	id VARCHAR(64) NOT NULL,
	business_id VARCHAR(64) NOT NULL,
	version INTEGER NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (business_id, id),
	UNIQUE (business_id, fingerprint)
)

;

CREATE INDEX IF NOT EXISTS ix_flow_market_insights_business_id ON flow_market_insights (business_id);


CREATE TABLE IF NOT EXISTS flow_merchant_contexts (
	business_id VARCHAR(64) NOT NULL,
	industry VARCHAR(80) NOT NULL,
	location VARCHAR(120) NOT NULL,
	latitude FLOAT,
	longitude FLOAT,
	products JSON NOT NULL,
	materials JSON NOT NULL,
	markets JSON NOT NULL,
	commodities JSON NOT NULL,
	cost_categories JSON NOT NULL,
	enabled BOOLEAN NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (business_id)
)

;


CREATE TABLE IF NOT EXISTS flow_signal_sources (
	name VARCHAR(180) NOT NULL,
	url TEXT NOT NULL,
	provider VARCHAR(60) NOT NULL,
	reliability VARCHAR(40) NOT NULL,
	retrieved_at TIMESTAMP WITH TIME ZONE NOT NULL,
	published_at TIMESTAMP WITH TIME ZONE,
	id VARCHAR(64) NOT NULL,
	business_id VARCHAR(64) NOT NULL,
	version INTEGER NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (business_id, id),
	UNIQUE (business_id, url)
)

;

CREATE INDEX IF NOT EXISTS ix_flow_signal_sources_business_id ON flow_signal_sources (business_id);


CREATE TABLE IF NOT EXISTS flow_market_signals (
	category VARCHAR(30) NOT NULL,
	source_id VARCHAR(64) NOT NULL,
	fingerprint VARCHAR(64) NOT NULL,
	title VARCHAR(500) NOT NULL,
	text TEXT NOT NULL,
	geography JSON NOT NULL,
	tags JSON NOT NULL,
	basis VARCHAR(40) NOT NULL,
	data JSON NOT NULL,
	published_at TIMESTAMP WITH TIME ZONE,
	retrieved_at TIMESTAMP WITH TIME ZONE NOT NULL,
	expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
	embedding JSON NOT NULL,
	embedding_model VARCHAR(180) NOT NULL,
	id VARCHAR(64) NOT NULL,
	business_id VARCHAR(64) NOT NULL,
	version INTEGER NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (business_id, id),
	UNIQUE (business_id, fingerprint),
	FOREIGN KEY(business_id, source_id) REFERENCES flow_signal_sources (business_id, id)
)

;

CREATE INDEX IF NOT EXISTS ix_flow_market_signals_category ON flow_market_signals (category);

CREATE INDEX IF NOT EXISTS ix_flow_market_signals_business_id ON flow_market_signals (business_id);


CREATE TABLE IF NOT EXISTS flow_recommended_actions (
	insight_id VARCHAR(64) NOT NULL,
	code VARCHAR(60) NOT NULL,
	text TEXT NOT NULL,
	id VARCHAR(64) NOT NULL,
	business_id VARCHAR(64) NOT NULL,
	version INTEGER NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(business_id, insight_id) REFERENCES flow_market_insights (business_id, id)
)

;

CREATE INDEX IF NOT EXISTS ix_flow_recommended_actions_business_id ON flow_recommended_actions (business_id);


CREATE TABLE IF NOT EXISTS flow_commodity_prices (
	signal_id VARCHAR(64) NOT NULL,
	commodity VARCHAR(60) NOT NULL,
	value NUMERIC(24, 8) NOT NULL,
	currency VARCHAR(3) NOT NULL,
	unit VARCHAR(30) NOT NULL,
	original_value VARCHAR(60) NOT NULL,
	original_unit VARCHAR(40) NOT NULL,
	location VARCHAR(120) NOT NULL,
	observed_at TIMESTAMP WITH TIME ZONE NOT NULL,
	retrieved_at TIMESTAMP WITH TIME ZONE NOT NULL,
	is_proxy BOOLEAN NOT NULL,
	id VARCHAR(64) NOT NULL,
	business_id VARCHAR(64) NOT NULL,
	version INTEGER NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (business_id, commodity, observed_at, currency, unit, location),
	FOREIGN KEY(business_id, signal_id) REFERENCES flow_market_signals (business_id, id)
)

;

CREATE INDEX IF NOT EXISTS ix_flow_commodity_prices_business_id ON flow_commodity_prices (business_id);


CREATE TABLE IF NOT EXISTS flow_competitor_observations (
	competitor_id VARCHAR(64) NOT NULL,
	signal_id VARCHAR(64) NOT NULL,
	content_hash VARCHAR(64) NOT NULL,
	observed_at TIMESTAMP WITH TIME ZONE NOT NULL,
	kind VARCHAR(30) NOT NULL,
	advertised_prices JSON NOT NULL,
	id VARCHAR(64) NOT NULL,
	business_id VARCHAR(64) NOT NULL,
	version INTEGER NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (business_id, competitor_id, content_hash),
	FOREIGN KEY(business_id, competitor_id) REFERENCES flow_competitors (business_id, id),
	FOREIGN KEY(business_id, signal_id) REFERENCES flow_market_signals (business_id, id)
)

;

CREATE INDEX IF NOT EXISTS ix_flow_competitor_observations_business_id ON flow_competitor_observations (business_id);

DO $$
DECLARE t text; r text;
BEGIN
  FOREACH t IN ARRAY ARRAY['flow_merchant_contexts','flow_signal_sources','flow_market_signals','flow_commodity_prices','flow_competitors','flow_competitor_observations','flow_market_insights','flow_recommended_actions','flow_ingestion_jobs'] LOOP
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
    FOREACH r IN ARRAY ARRAY['anon','authenticated'] LOOP
      IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r) THEN
        EXECUTE format('REVOKE ALL ON TABLE %I FROM %I', t, r);
      END IF;
    END LOOP;
  END LOOP;
END $$;
-- No direct-client policies: access is exclusively through the authenticated API.
