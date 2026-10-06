# Validation evidence — 7 October 2026

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
