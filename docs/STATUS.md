# Implementation status — 7 October 2026

The local application is runnable and the connected core workflow has passed automated and browser checks. **The full PRD is not complete.** This file preserves unfinished scope instead of relabeling it as finished or merely credential-blocked.

## Implemented and tested locally

| Capability | Implementation | Validation |
|---|---|---|
| Local onboarding and sessions | Argon2id credentials, hashed opaque sessions, HttpOnly cookies, role/tenant checks, member grants/revocation | HTTP auth and cross-tenant tests |
| Exact ledger primitives | Typed invoice/receipt/allocation/adjustment fields, exact sen, operation/source dedupe, transactions | Partial, combined, excess, concurrency, unmatch/reversal tests |
| Candidate to confirmed deal | Text intake, durable job, conservative extraction, explicit dates/charges, versioned confirmation/amendment | Connected workflow and injection-text test |
| Invoices and payables | Draft/issue, aging, disputes, credits/write-offs; source drill-down | API tests and browser partial-payment flow |
| Cases | Delivered-unbilled, overdue, unapplied, changed terms and duplicate-charge candidates; reasoned review; link existing invoice | Case dedupe and automatic closure test |
| Deterministic decisions | Daily forecasts, date shifts, incremental deposits/costs, original terms preserved, deferred items visible | Timing, deferred liabilities, unknown baseline tests |
| Financial explanations | Controlled metric registry, source IDs/definitions, sales/receipts separation, cash bridge | Distinct metric, transfer and exact bridge tests |
| Action authority | Exact digest/version/recipient, owner approval, expiry, current-state preflight, pause, stale cancellation | Replayed/tampered/unauthorized/paid-before-send tests |
| Durable worker | Transactional jobs, leases, bounded extraction retries, unknown send outcomes without blind retry | Crash recovery and uncertainty tests |
| Telegram adapter boundaries | Secret webhook, durable dedupe, polling checks, private binding, media limits, opaque callbacks | Mock transport and HTTP tests; no live bot |
| Android server boundary | Dedicated claim-only token, allowed packages, OTP exclusion, dedupe, revoke | Device intake tests; no Android hardware involved |
| Operational export / e-Invoice boundaries | Stable CSV export; draft/local identifier checks; submission fails closed | No fabricated provider-validation test |
| Batch costing | Usable inventory versus waste, exact cost allocation, explicit exclusions | PRD 100/80/20-pack fixture |
| Companion | Today/Deals/Money/Decisions/Review, forms, source details, exact approvals, error/empty/loading states, responsive navigation | Production build/typecheck; desktop/mobile browser inspection |

## Implemented but not yet verified against the real dependency

- PostgreSQL DDL/driver path and Supabase RLS policy migration. Docker's engine was unavailable/nonresponsive; SQLite concurrency results do not prove PostgreSQL behavior.
- Supabase JWT verification adapter. Browser Supabase sign-in and authenticated tenant bootstrap still need integration work.
- Gemini structured extraction/translation/transcription adapter. No credentials, consented evaluation set, critical-field quality benchmark or paid provider call was used.
- Live Telegram polling/webhook registration, actual downloads and authorized sends. Mock adapter tests are not live delivery evidence.
- Recipient invite/owner verification and exact bilateral confirmation have application paths; live identity assurance must be verified with an authorized test bot.

## Fixture or local-only

- Demo cash and payment claims are entirely fictional. No actual banking connection exists.
- Outbound actions use `simulated_sent`. Scripted replies are merchant-recorded evidence, never bank verification.
- Local filesystem storage and development auth work locally; managed private object storage and production identity rollout are separate work.
- Voice brief uses browser speech with an on-screen transcript; installed language voices vary. No provider TTS or generated recap video exists.
- Market observations are manually entered and linked to deal IDs. No continuous licensed signal feed is running.

## External connection requirements

| Capability | Exact setup needed |
|---|---|
| Telegram | BotFather development bot; server-only TELEGRAM_BOT_TOKEN / TELEGRAM_BOT_ID; staff and recipient binding; webhook secret + HTTPS domain only for webhook mode |
| Gemini | GEMINI_API_KEY, explicit GEMINI_MODEL, MODEL_PROCESSING_APPROVED=true after approved handling/retention policy; run multilingual ground-truth evaluation |
| Supabase | SUPABASE_URL/JWT audience, reviewed migrations, restricted database roles, separate auth onboarding and private Storage integration |
| Live bank | Select a provider/institution and approve consent/status semantics; implement/test provider-specific authenticated read/reversal adapter. Credentials alone are insufficient. |
| ERP / MyInvois | Choose provider/taxpayer sandbox, mappings and official document schemas; implement/test external adapter and reconciliation. Credentials alone are insufficient. |
| Android device | Build native app with notification permission UI, allowlist, Keystore token storage, bounded offline queue and device tests. Server ingestion is ready for integration. |
| Optional ML | Data rights, labeled temporal evaluation, shadow mode, drift/rollback ownership; deliberately disabled |

## Not yet implemented / required before full PRD acceptance

1. Full Telegram conversational deal/invoice/reconciliation/scenario journey, shared deal-room permissions, Mini App initData validation and robust single-poller lease management. Current bot captures evidence, exposes scoped commands and approves exact proposals; dense work happens in the companion.
2. Full multilingual UI, merchant glossary, field-level OCR/audio timestamps, calibrated extraction quality, automated correction propagation across all draft relationships, and model cost/usage limits.
3. Per-account balance reconciliation, paired internal transfers, multi-currency/FX, inventory reservations and returns, split-delivery billing, supplier statement matching and structured unit conversion.
4. Full immutable forecast snapshots across every event, structured rescue negotiation mandates/rounds and alternative generation, promise scheduling/cadence, quiet-hour configuration UI and outcome-linked plan milestones. Basic daily scenarios and approved proposals work.
5. Typed supplier-account verification/change workflows; this build has no outgoing payment-account mutation or payment initiation API.
6. Complete MyInvois UBL validation, official submission/status/cancel/replace adapter; ERP imports/mappings/conflict reconciliation; bank-specific feed adapter.
7. Native Android application and hardware testing, provider TTS/video recap rendering, reliable offline draft sync, scheduled merchant daily briefs and push notifications.
8. Production Supabase auth onboarding/private Storage; least-privilege API/worker database roles; file parser isolation/malware scanning; tenant quotas/rate limits; retention/legal hold/deletion workflows; encrypted backups and restoration tests; full incident/operations console.
9. Large-dataset performance/availability measurements, usability research, accessibility audit, multilingual benchmark and provider sandbox end-to-end validation.

Next concrete engineering sequence: PostgreSQL integration/concurrency/RLS tests → Supabase onboarding and storage → verified Telegram recipient integration and richer chat commands → immutable forecast/negotiation models → remaining inventory, currency and provider adapters. Keep the existing invariants green throughout.
