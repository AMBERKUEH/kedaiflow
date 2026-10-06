# KedaiFlow

**Understand the deal. Follow the money.**

A locally runnable financial companion for Malaysian merchants. Next.js / React / TypeScript frontend, FastAPI domain API, durable SQL-backed worker, exact integer-sen calculations, private evidence, and Telegram transport.

This is an initial working local implementation, **not completion of every requirement in the 61-section PRD**. Read [implementation status](docs/STATUS.md) and [requirements traceability](docs/REQUIREMENTS.md) before treating a capability as production-ready. No real bank, Telegram bot, Gemini account, ERP or MyInvois credentials were supplied. No customer was contacted, official invoice submitted, money moved, deployment made or GitHub upload performed.

## Start on Windows

Requirements: Python 3.11+, Node.js 20.9+ and npm. Run in this folder:

```powershell
.\Start-KedaiFlow.ps1
```

The launcher installs locked dependencies, creates the local SQLite schema, adds an isolated synthetic business, builds the companion app, and starts API, worker and frontend in hidden background processes.

- Companion: http://localhost:3000
- Interactive OpenAPI: http://localhost:8000/docs
- Health: http://localhost:8000/healthz
- Stop: `./Stop-KedaiFlow.ps1` (preserves business data)

Choose **Explore a sample kedai**. Demo credentials: `demo@kedaiflow.local` / `KedaiFlow-demo-2026!`. These are public, local fixture credentials, never a production identity. Register a separate business for your own records; real statement imports cannot enter the fixture business.

After the first build, `./Start-KedaiFlow.ps1 -SkipBuild` skips compilation. Rebuild after frontend changes. Logs are in `.local/`; `.env`, private media, databases and dependencies are ignored by Git.

## Start manually

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
.\.venv\Scripts\python.exe -m scripts.migrate
.\.venv\Scripts\python.exe -m services.api.seed
.\.venv\Scripts\python.exe -m uvicorn services.api.main:app --host 127.0.0.1 --port 8000
```

In a second terminal:

```powershell
.\.venv\Scripts\python.exe -m services.api.worker
```

In a third terminal:

```powershell
cd apps\companion
npm.cmd ci
npm.cmd run build
npm.cmd start
```

macOS/Linux: use `python3 -m venv .venv`, `.venv/bin/python`, and `npm` for equivalent commands. This path has not been tested on those operating systems.

## Workflows you can try

1. **Deals:** inspect mixed-language evidence, fill missing dates, confirm an exact version, record a delivery, prepare and issue an internal invoice.
2. **Money:** match the RM3,000 simulator receipt to INV-2026-008. RM8,000 becomes RM5,000 outstanding. The RM8,000 payment claim cannot settle it. Record additional receipts, promises, payables or merchant-attested cash; view source details.
3. **Review:** inspect delivered-but-unbilled, overdue, duplicate-bill and unapplied-receipt cases. Review a case with a reason. Draft, inspect and approve an exact reminder. The worker reports `simulated_sent`, not actual delivery.
4. **Decisions:** compare dated deposits, new-order costs and shifted supplier/receipt dates over 7/30/90 days. Deferred obligations remain visible. Plans do not modify contracts.
5. **Explain my cash:** choose controlled sales, receipts, current outstanding or cash-bridge metrics. Inspect their source IDs and definitions. Profit questions request more information.
6. **Your own business:** register, add opening cash and a date, create counterparties, and import the documented CSV through preview and confirmation. Imported records remain explicitly unverified by a bank.
7. **Additional tools:** batch costing, source-linked market observations, scoped staff membership, operational CSV export, e-Invoice draft, private Telegram pairing and audit history.

The sample you see may already have the RM3,000 allocation and a simulated approved reminder because the browser smoke test exercised it. The fixture seed is deliberately idempotent and does not erase your work. For a pristine demonstration, point `DATABASE_URL` at a new isolated file and run seed; do not delete an existing ledger.

## Tests and contracts

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m scripts.generate_contracts
cd apps\companion
npm.cmd run typecheck
npm.cmd run build
```

See [validation evidence](docs/VALIDATION.md). OpenAPI is also saved at `packages/contracts/openapi.json`. Request examples are in [API examples](docs/API_EXAMPLES.md). Mutations require `Idempotency-Key`; role and tenant checks run on the server, with version checks on mutable records.

## PostgreSQL and deployment

`compose.yml` defines a **local-only** PostgreSQL/API/worker stack. Stop the native API/worker first, then run `docker compose up --build`; run the frontend separately. The container password is explicitly local development data. Do not deploy this compose file publicly.

`database/migrations/0001_initial.sql` is the generated PostgreSQL schema. `0002_supabase_rls.sql` is an optional Supabase policy layer: anonymous domain access and all direct browser domain writes are denied; allowed financial reads require active finance membership. Apply it only in Supabase, where `auth.uid()` exists. Server-side API permissions remain required. No public storage bucket is used.

Docker Desktop did not provide a responsive engine in the build environment, so PostgreSQL, Docker and Supabase paths are **implemented but not verified** here. SQLite transactions and concurrent reconciliation were tested. Production requires separate database roles, authenticated onboarding for Supabase, secret management, HTTPS, private managed storage, restore drills and the unresolved items in STATUS.md. The application intentionally rejects local auth/SQLite/fixture modes when `APP_ENV=production`.

## Layout

```text
apps/companion/       Merchant web UI and typed API client
services/api/        Authentication, models, domain, finance, intake and adapters
services/api/worker.py Durable SQL jobs, leases, bounded read retries, send recovery
services/api/telegram.py Polling/webhook/media/private bindings/callbacks
database/migrations/ PostgreSQL schema and optional Supabase RLS
packages/contracts/  Generated OpenAPI
fixtures/            Synthetic inputs and walkthrough
tests/               Financial, permission, transport and recovery tests
docs/                PRD, status, setup, architecture and release gates
scripts/             Migration, contract generation and verification utilities
```

## Integration setup

Copy `.env.example` to `.env` and enter secrets locally. Never commit it. [Telegram setup](docs/TELEGRAM.md) explains BotFather, pairing, polling, webhook switching, recipient verification and approval callbacks. [Architecture and decisions](docs/ARCHITECTURE.md) describes financial semantics and limitations. [Demo script](docs/DEMO.md) gives a reproducible competition story.

Source contracts consulted: [Telegram Bot API](https://core.telegram.org/bots/api), [SQLAlchemy transaction documentation](https://docs.sqlalchemy.org/en/20/orm/session_transaction.html), and [Next.js installation](https://nextjs.org/docs/app/getting-started/installation). The original PRD is retained unchanged in `docs/PRODUCT_REQUIREMENTS.md`.
