# Validation evidence — 7 October 2026

## Live provider checks - 16 October 2026

Groq `openai/gpt-oss-20b` returned a schema-valid live extraction. ElevenLabs `scribe_v2` transcribed a short synthetic recording and returned 49 timed segments. A live handoff using the completed transcript produced the expected 20 crates, RM60 unit price (6,000 sen), null due date and English/Malay/Chinese translations. No real customer/business source was transmitted. Exactly two Groq requests and one ElevenLabs speech request were used in this check.

Credentials were migrated into ignored `.env`, removed from `.env.example` and never displayed. This supersedes earlier missing-key/live-unverified notes for these two providers only. Other integration and full-product validation limits remain unchanged. Credential-free detailed evidence is in the private `.local/connection-test-report.json`.

## Groq migration verification - 16 October 2026

**82 pytest tests passed** after replacing the language-model adapter and settings. Groq coverage verifies strict required/nullable JSON schemas, JSON-mode model selection, English/Malay/Chinese output, original-text preservation, integer money/date/quantity validation, blocked model tool calls/refusals/truncation, redacted authentication/quota/network errors, controlled image/PDF/audio routing, worker review states, no Gemini fallback and safe credential migration. Existing financial, permission, speech and recovery tests continue to pass. JUnit report: test-results.xml.

No `GROQ_API_KEY` was present in saved local files. All Groq API responses in the automated suite were mocked; no live provider quality or connectivity claim is made. The frontend code did not change in this migration.

## Additional verification — 16 October 2026

**54 pytest tests passed** after the ElevenLabs implementation, and the updated Next.js production build/TypeScript check passed. Speech-specific coverage includes multipart authentication, automatic language detection, timestamp grounding, provider failures without credential leakage, paid-request timeout/crash review, no automatic paid replay, transcript reuse after downstream failure, consent gating, manual mode, source-preserving corrections, and cross-tenant audio/status/retry rejection. JUnit results are saved in test-results.xml.

The current saved environment files do not contain an ElevenLabs key. No real speech request was made; provider connection/accuracy remain unverified. See SPEECH_TO_TEXT.md for exact local setup and a one-request live test.

## Executed

- Python 3.11.9 on Windows; locked FastAPI/SQLAlchemy dependencies.
- **33 pytest tests passed** against isolated temporary SQLite databases, real HTTP TestClient routes, concurrent threads, fake Telegram transports and real domain transactions.
- **Next.js 16.4.0 production build passed**, including TypeScript checks. Node.js 24.11.1; React 19.3.0.
- `pip check`: no broken requirements.
- `npm install / npm ci` audit: zero known vulnerabilities reported for the installed frontend dependency tree at build time. This is a package audit result, not a security certification.
- PowerShell startup launcher: created a new project-local virtual environment, installed locked Python/npm dependencies, migrated/seeded without erasing the existing fixture, launched hidden API/worker/frontend processes.
- Browser: local demo login; desktop 1440px and default narrow layout; five-tab navigation; receipt allocation; RM8,000 → RM5,000 outstanding; unmatched case resolution; RM5,000 reminder preview; exact owner approval queued for simulation; refreshed connected dashboard. Additional final browser checks are recorded in PROGRESS.md.

## Test coverage

Financial: partial and combined receipts, overpayment credit, duplicate source/key conflicts, concurrent allocation, unmatch, receipt reversal, sales/receipt distinction, internal transfer exclusion, missing opening cash, dated deposit effects, deferred obligations, cash bridge, inventory versus waste.

Permissions/actions: tenant denial, sales scope including hidden opening cash, owner-only approvals, expiry, digest tampering, replay, revoked role, pause, payment-before-send invalidation, stale scenario proposals, unknown crash recovery, recipient pairing and exact-version confirmation.

Integration boundaries: authenticated durable webhook/dedup, shared-chat privacy, opaque callback actor/chat/replay checks, safe media path, Telegram transport timeout, extraction lease recovery, claim-only Android allowlist/revocation/OTP filtering, draft e-Invoice state and disabled provider submission.

## Not executed / limitations

- PostgreSQL transactions, SQL migration execution and Supabase RLS tests: Docker engine did not respond. PostgreSQL support remains unverified; SQLite is the tested local backend.
- Live Telegram, Gemini, Supabase, bank, ERP, MyInvois and notification hardware: no configured authorized credentials/devices. No live send or provider inference was attempted.
- OCR/voice critical-field quality, accent/noise evaluation, full accessibility/merchant usability study, production backup restore, load/availability targets and real-world ML: not performed.
- One upstream TestClient/httpx deprecation warning appears; it did not fail tests.

The test count is not a claim that all PRD features or all acceptance criteria have been implemented. See REQUIREMENTS.md and STATUS.md.


## FLOW / BijakSense ? 16 October 2026

111 backend tests pass, including 29 FLOW cases. Two isolated live synthetic merchant profiles returned all five categories, multilingual Sentence Transformers/FAISS retrieval and validated Qwen selections. Next.js production build and TypeScript checks pass. See [BijakSense](BIJAKSENSE.md) for exact source coverage, limitations and reproducible evaluation commands. Browser DOM checks cover the integrated tab and evidence controls; browser screenshot capture was unavailable.

The final demo worker refresh completed with validated Qwen recommendations across five categories. Open-Meteo returned HTTP 503 on that later refresh; the previous still-fresh sourced forecast was retained with the failed refresh status displayed. No forecast was fabricated or silently relabelled as newly retrieved.
