# Architecture and implementation decisions

## Shared record flow

Browser or Telegram → authenticated actor / tenant → evidence intake → durable extraction job → editable candidate → merchant confirmation → versioned deal → internal invoice → sourced receipt → atomic allocations → case/forecast updates → exact action approval → worker preflight → adapter result → observed outcome.

The model adapter has no ledger, SQL, payment, permission or messaging tools. Its only result is a schema-validated interpretation with provenance and questions. All money is integer MYR sen. Quantities use validated decimal strings and ROUND_HALF_UP at line level. The current application rejects other currencies; FX has not been silently approximated.

## Transactions and identity

Local development uses Argon2id password hashes and random hashed sessions in HttpOnly/SameSite cookies. Mutations validate browser origin and current membership. Production configuration requires Supabase JWT verification against its configured issuer/JWKS, including expiry and audience. Supabase browser sign-in/onboarding provisioning is not complete; do not deploy production auth by merely changing the flag.

Tenant IDs select only verified memberships. Domain queries always carry business scope. Finance tables have typed monetary fields, positive amount checks, composite cross-tenant foreign keys for allocations and counterparty links, stable IDs and unique source references. Financial commands serialize on the business row in PostgreSQL; SQLite uses BEGIN IMMEDIATE. This deliberately favors simple correctness over cross-business throughput assumptions.

Repeated idempotency keys are scoped by business/user/role/operation and compare a canonical payload hash. Changed payloads return 409. Receipt source identity is independently unique by tenant/account/source event. A receipt can fund multiple invoices, and multiple receipts can fund one invoice. Amounts above outstanding remain credit; excess allocations fail atomically. Reversing an allocation preserves its record and audit. Receipt reversals append compensating cash events and reopen balances.

## Financial definitions

- Sales: issued receivable invoices in period minus credit notes recorded in period. Drafts are excluded. Write-offs are not presented as sales credits.
- Cash received: recorded customer receipt movements net of their reversals. Loans/transfers are excluded.
- Outstanding: **current** invoice state; this metric does not claim historical as-of receivables.
- Cash bridge: opening at the start of the selected day plus included, classified actual records. Original receipts and reversal movements retain their own dates.
- Consolidated internal transfers are excluded. The current model has account labels, not a full paired-transfer/account-balance subsystem.
- Forecast: starting cash plus recorded future movements and outstanding obligations under explicit date assumptions. A promise affects only optional expected dates/amounts. Unknown opening cash propagates null. Deferred items beyond the horizon are returned separately.
- Batch costs: exact unit-cost allocation under the declared simple model; usable remaining stock and waste are separate. Contribution excludes unstated overhead and tax.

This is an operational finance assistant, **not a statutory double-entry accounting ledger**. CSVs explicitly export operational records. MyInvois local checks do not establish official schema/tax validity.

## Permission model

Owner: all business workflows and exact approvals. Bookkeeper: finance edits/reconciliation and drafts, no approval authority. Sales: own evidence and assigned counterparties/deals; financial dashboards and invoice queries denied. Accountant: financial read and export only. External recipients: private Telegram terms for their explicitly bound counterparty only, confirmed by exact deal/version command. Shared groups receive no private finance response. Platform operators are not granted a business role by application code.

Membership changes, action pause, invoice changes, recipient version changes, expiry and payload tampering all invalidate execution. Drafting and approval are separate steps. The worker records an external reservation before the send. If it crashes or a response is uncertain, it marks outcome_unknown and does not retry automatically. A distributed receipt/send race after the last check remains possible and is not claimed solved.

## Workers and recovery

Jobs persist in the same database transaction as evidence/actions. Claims use row locks / SKIP LOCKED on PostgreSQL and the SQLite transaction mutex locally. Extraction leases expire after three minutes, with bounded retries and exponential backoff. External-action leases become uncertain on crash. The worker remains a separate process.

Telegram updates commit before webhook acknowledgement or polling offset advancement. Inbox processing left in processing after crash requires manual review. No automated replay of possible outbound effects exists. Jobs, audit and connector health are inspectable; retry endpoints only allow safe extraction jobs.

## AI, files and privacy

Without approved model credentials, deterministic extraction recognizes a narrow quantity/unit/price subset and always asks about dates and charges. Text PDFs use local text extraction; images/voice are retained for manual entry. Groq receives bounded source text and optional explicitly configured inline image bytes only when the server operator configures GROQ_API_KEY, GROQ_MODEL and MODEL_PROCESSING_APPROVED=true. Results identify provider/model/schema and cannot execute actions. Critical-field span grounding and merchant-language evaluation remain unfinished; whole-document provenance is explicitly labeled.

Uploads allow JPEG/PNG/PDF and documented audio types, cap size at 8 MB, validate basic signatures, limit image pixels/PDF pages and store content-addressed bytes privately. The API never serves storage as a public directory. PDF parsing has bounds but is not a hardened OS-level malware sandbox. Managed object storage, antivirus/CDR, encrypted backups, retention automation, per-tenant model quotas and a deployment privacy review remain release work.

## Operating profile and decisions

- Initial profile: Malaysian B2B produce wholesaler, MYR, Asia/Kuala_Lumpur.
- System of record: local operational records; no existing ERP assumed.
- Cash: authorized owner/bookkeeper attestation, not bank verification.
- Outbound: per-action approval; simulation only for fixture businesses. No real transfers.
- Default storage: private local directory for local use. Production region/retention not selected.
- Signals: owner-entered source links tied to actual deal IDs; no invented weather feed.
- ML: disabled until consented labeled data, benchmark, shadow evaluation and approval exist.
- UI: original SVG shop-bag companion, self-hosted fonts, cream/mint/navy, responsive views. Navigation and briefs support English/Malay/Chinese; full UI localization remains partial.


## Groq language-model configuration - 16 October 2026

The runtime now supports LLM_PROVIDER=groq or manual. Groq uses the fixed server-only OpenAI-compatible chat completion endpoint, strict JSON Schema for supported models and locally validated JSON mode for other selected models. Default GROQ_MODEL is openai/gpt-oss-20b. No Gemini runtime adapter or audio fallback remains. ElevenLabs handles speech; only its transcript reaches Groq. Local PDF text goes to the text model; image extraction requires an explicit GROQ_VISION_MODEL, and scanned PDFs without text remain manual review. All candidate money/date/quantity fields are locally validated; models have no action or financial authority.
