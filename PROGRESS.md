# KedaiFlow progress

## 16 October 2026 - FLOW / BijakSense implemented

Added the requested five market modules, nine persistent SQL models, BM25 + multilingual Sentence Transformers + FAISS retrieval, merchant relevance/freshness matching, deterministic commodity/sales calculations, constrained Qwen recommendation selection, feedback/dismissal, authenticated APIs, a BijakSense tab and a separate scheduled worker. Existing capture, transcription and ledger behavior is reused. PostgreSQL migration 0003 is additive; local SQLite is verified.

Live public-source evaluations passed for synthetic grocery and construction profiles: news RSS, World Bank monthly commodity history, Open-Meteo, DOSM/public industry trends, and robots-permitted competitor announcements. Both evaluations used real 384-dimensional multilingual embeddings/FAISS and validated `qwen/qwen3.8-27b` selections. An initial Qwen 413 was fixed by bounding the evidence packet. Public prices are monthly USD benchmarks, not local supplier quotes. Unknown demand, publication dates and exact stock impacts are not invented.

Validation: **111 backend tests passed** (29 FLOW evaluations plus 82 existing tests); frontend production build/TypeScript passed. Browser DOM verification confirmed all five categories, source evidence and recommendations. Added explicit Malaysia timestamp formatting, bounded word matching and current-relevance filtering after UI review. Demo profile/watchlist is synthetic; external evidence is live. No upload or deployment.

Setup/API requirements: [docs/BIJAKSENSE.md](docs/BIJAKSENSE.md). Private live evaluation reports are under `.local/flow-evaluation/`. Commercial weather needs an Open-Meteo subscription key; existing Groq credentials already work. World Bank, DOSM and the implemented public RSS sources require no additional key. Production PostgreSQL/Docker has not been live-tested.


## 16 October 2026 - Both provider keys tested live

Moved saved Groq/ElevenLabs keys from `.env.example` into ignored `.env` and restored public placeholders. Live Groq extraction with `openai/gpt-oss-20b` succeeded. Live ElevenLabs `scribe_v2` transcription of a short Windows-generated synthetic recording succeeded with 49 timed segments. Feeding that actual transcript to Groq returned quantity 20, unit price 6,000 sen (RM60), an unknown due date, and all three translations as expected. Two small Groq requests and one speech request were used; no customer audio, real commercial action or financial record was involved. Raw synthetic outputs and a credential-free report are stored privately under `.local/`.

This establishes a successful connection and one synthetic example, not a multilingual accuracy benchmark or production readiness. Both keys remain server-side and were not printed.

## 16 October 2026 - Groq LLM migration

Replaced the Gemini runtime adapter with Groq for extraction and English/Malay/Chinese translation. Updated private/public environment settings, connector status, Docker API/worker environment, setup instructions and safe diagnostics. Default text model is `openai/gpt-oss-20b`; supported strict models use JSON Schema, other text models use validated JSON mode. Optional image extraction requires an explicit Groq vision model. Readable PDFs send locally extracted text; audio uses ElevenLabs before Groq. Original PRD provider suggestions remain preserved as source material.

Validation: **82 backend tests passed**, including strict schema, multilingual output, safe errors, partial/invalid results, no provider fallback, transcript preservation, media routing and private-key migration. The saved files have no Groq key, so live Groq verification is pending. Setup: docs/GROQ.md; diagnostics: `python -m scripts.check_llm` (no network) or `--live` for one small synthetic request after saving a key. No real provider call, GitHub upload or public deployment was performed.

## 16 October 2026 — ElevenLabs speech integration

Implemented the ElevenLabs batch transcription adapter using server-only HTTP requests and Scribe v2, automatic language detection, word timing/speaker provenance, private audio replay, reviewable/correctable transcripts with original preservation, scoped processing status and reviewed retries. The existing upload and Telegram voice paths share the same durable worker. Successful speech results are cached before downstream extraction; ambiguous paid requests and worker crashes never trigger automatic speech replay.

Added ignored private .env setup/migration and safe connection diagnostics. The saved .env.example and .env contain no ElevenLabs key as of verification; the live provider connection is **not verified**. Save ELEVENLABS_API_KEY locally, run `python -m scripts.configure_speech`, then restart API/worker. Instructions: docs/SPEECH_TO_TEXT.md. No secret has been printed or uploaded.

Validation: **54 backend tests passed**, including real upload-to-worker-to-review with a mocked speech provider, error redaction, word timestamps, unknown outcomes, cached transcript reuse, manual mode, correction history and cross-tenant audio/processing denial. Next.js production build and its TypeScript check passed. Repaired frontend dependencies after the earlier interrupted install. The launcher now uses dependency-lock stamps so ordinary restarts do not repeatedly reinstall/lock Windows native modules.

The full-product scope and remaining unrelated PRD work below are unchanged.

Status: working local application; **full PRD remains in progress**. No GitHub upload or public deployment.

Completed: connected React/FastAPI workflow, local business auth and roles, typed financial records, durable jobs, candidate extraction/manual review, versioned confirmation, invoices/payables, receipts/allocations/reversals, cases, scenarios, exact approvals, simulator execution, controlled queries, batch costing, CSV exports, Telegram boundary implementation, Android claim-only server intake, e-Invoice draft/local-check states, source and setup docs.

Verification: 33 backend tests pass; Next.js production build/typecheck pass; frontend dependency audit reports zero vulnerabilities; package integrity check passes. Local launcher tested. Browser verified partial receipt allocation and exact reminder approval. All live integrations remain unverified; PostgreSQL/Supabase execution blocked by nonresponsive Docker engine.

Remaining work and integration setup: docs/STATUS.md. Complete section traceability: docs/REQUIREMENTS.md. Competition story: docs/DEMO.md. Future work should start with PostgreSQL/RLS integration tests and production identity/storage, then the remaining conversational, inventory, currency and provider workflows.

This build intentionally uses isolated synthetic records for demonstration. Never relabel simulator events as live money or delivery. Do not erase existing financial records when restarting or reseeding.
