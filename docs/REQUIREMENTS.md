# Requirements traceability

Every section of the supplied PRD is preserved below. “Core tested” does not imply every subrequirement is complete. See STATUS.md for the exact unfinished engineering scope and external setup gates.

| PRD section | Implementation / validation mapping | Status |
|---|---|---|
| 01 / Product thesis & differentiation | README; connected core; merchant differentiation remains a research hypothesis | Implemented and tested locally; research outstanding |
| 02 / Target users, research & roles | security.py, auth/member/business APIs, scoped sales UI; local onboarding tests | Local implementation tested; Supabase onboarding unfinished |
| 03 / Complete feature map | STATUS.md preserves every feature group and remaining depth | Mixed; see detailed status |
| 04 / Signature journey: from voice to cash | domain.py / companion; text-to-deal, invoice, receipt, scenario and action tests | Implemented and tested locally; live voice integration blocked |
| 05 / Telegram intake & channel behavior | telegram.py: durable intake, private actor binding, groups denied, outbound status | Mock/HTTP tested; live token unavailable; full chat journeys incomplete |
| 06 / Language, voice & meaning preservation | ai.py, multilingual intent registry, brief templates, UI navigation languages | Rules tested; Groq adapter unverified; full localization/glossary unfinished |
| 07 / Documents, extraction & business memory | media.py, private upload/download, source hashes, candidates, version history | Local intake tested; provider OCR unverified; field spans/sandbox unfinished |
| 08 / Deal, order & delivery lifecycle | Deal/DealVersion/Delivery models; confirm/amend and invoice-link tests | Core tested; inventory, returns and split-billing unfinished |
| 09 / Receivables & intelligent collection | Invoice/Promise/Action; aging, exact drafts, pre-send cancellation | Core tested; automated cadence and rich collections policy unfinished |
| 10 / Payables, supplier statements & exports | Payable invoices, operational export; e-Invoice fail-closed route | Local tested; supplier statement matching and ERP adapter unfinished |
| 11 / Layer 1 — Payment evidence verification | Claim vs Receipt tables; simulator/import/cash source enforcement | Implemented and tested; no bank-provider integration |
| 12 / Layer 2 — Intelligent reconciliation | Atomic reconciliation, proposals, unapplied credit, reversals | Implemented and tested in SQLite; PostgreSQL not verified; FX unfinished |
| 13 / Layer 3 — Anomalies & permission checks | Deterministic case rules; policy/current-state checks; malicious-text fixtures | Tested local safeguards; not a validated fraud detector |
| 14 / Optional ML & evidence requirements | Connector status explicitly disables optional ML | External dataset/evaluation gate; models not implemented |
| 15 / Cash-flow engine & financial semantics | finance.py and run_scenario; source/assumption labels and unknown baseline | Core tested; immutable event snapshots and FX unfinished |
| 16 / Scenario lab: can we accept this order? | DecisionLab; dated inputs, no-change comparison, proposal preconditions | Core tested; broader generated alternative search unfinished |
| 17 / Market signals tied to real exposure | Source-linked signal API/UI; unrelated signal remains informational | Manual workflow tested; no live signal adapters |
| 18 / Operational recommendations & actions | Action, approvals, worker and outcome supplements | Core tested; bounded mandates/milestones/payment links unfinished |
| 19 / Experience, personality & daily rhythm | Original SVG companion, five surfaces, brief transcript/browser voice | Build/browser verified; video and scheduled briefs unfinished |
| 20 / Authorization, shared data & control | Tenant/role checks, digest-bound approval, audit, scoped recipient commands | Local/mocked tests pass; production rollout not verified |
| 21 / System architecture | Modular API, domain/finance/adapters, separate worker, ARCHITECTURE.md | Implemented locally |
| 22 / Backend stack & service selection | Next.js, FastAPI, SQLAlchemy, PostgreSQL driver and SQLite local mode | Local stack tested; PostgreSQL/Supabase unverified |
| 23 / Accounts, configuration & secrets | .env.example, configuration gates, server-only secrets, startup scripts | Local startup tested; external credentials absent |
| 24 / Data model & accounting invariants | Typed financial tables, composite FKs, unique source IDs, audit/reversals | SQLite constraints and commands tested; production migration unverified |
| 25 / API contracts & action boundaries | Typed Pydantic requests/core responses, generated OpenAPI, API_EXAMPLES | API tested; not all response envelopes fully typed |
| 26 / Jobs, events & recovery design | Job leases, retries, unknown external outcomes, transaction-bound enqueue | Local recovery tested; full event outbox/operations ownership unfinished |
| 27 / Security, privacy & offline limits | Scope, origin checks, hashed sessions, private files; architecture limitations | Local tested; production privacy/retention/sandbox/offline work remains |
| 28 / Failure handling & nonfunctional targets | Manual fallback, error UI, recovery cases, no invented success | Functional tests pass; service targets and usability targets unmeasured |
| 29 / Evaluation suite & release criteria | tests/test_workflows.py, test_boundaries.py, test_extended_flow.py | 82 tests passed; no claimed full PRD release pass |
| 30 / Competition mapping & demonstration | docs/DEMO.md, synthetic fixture files and simulator seed | Local demonstration verified; organizer rubric not revalidated |
| 31 / Product metrics, economics & validation | STATUS.md and financial metric semantics; no pilot metrics fabricated | Merchant research/economics/backtesting not performed |
| 32 / Implementation plan & developer handoff | Runnable repository, contracts, tests, docs, dependency locks | Core delivered; full-product gates remain open |
| 33 / Feature traceability & open decisions | REQUIREMENTS.md and STATUS.md | Scope preserved with explicit remaining work |
| 34 / Sources & factual boundaries | Original PRD retained; selected current technical docs consulted | References retained; external product/provider claims not adopted |
| 35 / Sources, glossary & final handoff | README/ARCHITECTURE financial definitions and traceability | Implemented core; full acceptance not claimed |
| 36 / Detailed edition: the complete operating model | Shared records across five surfaces and optional batch-costing tool | Local workflow tested; complete operating profiles unfinished |
| 37 / Money Leak Detective: finding the missing link | detect_cases; delivery/receipt/invoice/duplicate rules | Case dedupe tested; richer evidence-linked rule configuration unfinished |
| 38 / Money Leak Detective: review to verified outcome | Case review with reasons, link existing invoice, receipt-based resolution | Tested locally; no causal money-recovered claim |
| 39 / Deal Rescue: help a viable order survive | Forecast shifts, incremental costs/deposits, trough and beyond-horizon output | Deterministic tests pass; automatic plan generation unfinished |
| 40 / Deal Rescue: multilingual negotiation and closure | Exact scenario-bound proposal, approval, response record, versioned amendment | Core tested; multilingual bounded negotiation/milestones unfinished |
| 41 / Where Did My Money Go? Explain cash without confusing profit | Controlled cash bridge and sources; sales/cash distinction; transfers excluded | Exact fixture tested; complete account/till subsystem unfinished |
| 42 / Optional micro-vendor profile: per-pack economics | Batch costing API/UI; remaining inventory versus waste | Exact pack fixture tested; full recipe/version/inventory workflow unfinished |
| 43 / Natural-language finance: answers from controlled queries | Metric registry and ORM queries only; prompt/SQL refusal; source IDs | Implemented and tested; richer NL intent model/evaluation unfinished |
| 44 / Android notifications and e-Invoice boundaries | Android claim-only API; e-Invoice draft/local-check/provider-unavailable states | Server boundaries tested; Android app and official adapters unfinished |
| 45 / Telegram integration: what you actually need | docs/TELEGRAM.md; BotFather setup, authenticated staff/recipient pairing | Application paths and mock tests; no live bot |
| 46 / Telegram integration: run your first local test | telegram CLI identity/poll and separate durable worker | Code present; real polling not verified |
| 47 / Telegram integration: deploy a webhook | Webhook registration/deletion with retained updates; secret validation | HTTP intake tested; public HTTPS deployment not performed |
| 48 / Telegram webhook: code and processing architecture | Durable inbox and worker, dedup, scoped roles, recovery states | Mock/HTTP tests; full Telegram processing lease recovery unfinished |
| 49 / Telegram voice, photos, groups and approvals | Bounded file retrieval, private storage, callbacks, recipient confirmation | Boundary tests pass; Mini App and shared-room feature unfinished |
| 50 / API conventions and domain boundaries | OpenAPI, idempotency, version checks, tenant membership selection | Core API tests pass; pagination consistency/read scaling unfinished |
| 51 / API example: from a voice note to a confirmed deal | Evidence/deal APIs, explicit dates, confirm and version history | Connected text flow tested; real voice quality not measured |
| 52 / API example: evidence-aware reconciliation | Source-derived receipt mode and transactional allocations/reversals | Exact tests pass; bank connectors/FX not implemented |
| 53 / API example: scenario, case and approved action | Scenario/review/action contracts and per-action preconditions | Local tests plus browser approval flow; external sends mocked |
| 54 / Database design and consistency rules | models.py, generated 0001 DDL, optional 0002 Supabase RLS | SQLite tested; PostgreSQL/RLS not executed here |
| 55 / AI service contracts and model evaluation | Candidate-only adapters, deterministic arithmetic and permission boundary | Rules tested; provider/language ground-truth evaluation blocked |
| 56 / User interface specification: detailed states | Responsive companion forms, review previews, chart tables, source labels | Build/typecheck/browser passed; complete a11y/localization/offline audit remains |
| 57 / Full-product deployment and operations | compose, launcher, jobs health, pause, unknown outcomes, locks | Local lifecycle tested; managed deployment/backups/retention incomplete |
| 58 / Extended acceptance and adversarial test plan | Automated adversarial/financial/integration boundaries test suite | 82 tests pass; full 22-case acceptance coverage not claimed |
| 59 / Competition demonstration and measurable completion | DEMO.md, seed, fixtures and validation report | Local connected demo; live provider evidence unavailable |
| 60 / Reference kit: delivery contents and validation status | Reference ZIP not supplied; independent transport implementation | No reference-kit reuse or claimed validation |
| 61 / Additional sources and implementation decisions | ARCHITECTURE choices; STATUS release gates; original source notes | Decisions recorded; full product acceptance remains open |
