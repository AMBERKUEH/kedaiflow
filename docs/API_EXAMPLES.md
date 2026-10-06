# Local API examples

Interactive schemas: http://localhost:8000/docs. Saved schema: `packages/contracts/openapi.json`.

Sign in through the companion or `POST /v1/auth/login`; the response sets an HttpOnly session cookie. A valid bearer token is also accepted by the configured identity mode. `X-Business-Id` selects an active membership; it never grants access. Each mutation below requires a fresh `Idempotency-Key`, reused only when retrying the same payload.

```http
POST /v1/reconciliations
Idempotency-Key: example-allocation-001
Content-Type: application/json

{
  "receipt_id": "COPY_REAL_RECEIPT_ID",
  "expected_receipt_version": 1,
  "allocations": [{
    "invoice_id": "COPY_REAL_INVOICE_ID",
    "expected_invoice_version": 2,
    "amount_minor": 300000
  }],
  "reason": "Reviewed payer, reference and account evidence"
}
```

Starting from RM8,000, response `invoices[0].outstanding_minor` is `500000`. `unapplied_minor` reports remaining receipt credit. A stale version, excessive sum, mismatched direction or currency fails atomically.

```http
POST /v1/scenarios
Idempotency-Key: example-scenario-001
Content-Type: application/json

{
  "name": "Later supplier date",
  "start": "2026-10-07",
  "horizon": 30,
  "buffer_minor": 100000,
  "shifts": [{"invoice_id": "COPY_REAL_PAYABLE_ID", "date": "2026-10-20"}],
  "movements": [{"label": "Proposed deposit", "date": "2026-10-09", "amount_minor": 400000}]
}
```

The response includes dated movements, source basis, lowest balance, buffer breaches and beyond-horizon obligations. It persists an assumption run, not a contractual amendment. GET `/v1/records/scenarios` labels stale runs after the business revision changes.

```http
POST /v1/queries
Idempotency-Key: example-query-001
Content-Type: application/json

{"metric":"sales","start":"2026-10-01","end":"2026-10-07"}
```

Supported metric IDs: `sales`, `cash_received`, `outstanding`, `cash_bridge`. Amounts have definition/coverage/source IDs. Natural-language `question` supports a small deterministic multilingual intent registry; ambiguous/profit/raw SQL requests clarify rather than execute arbitrary SQL.

## Reviewed CSV format

```csv
transaction_id,date,amount_minor,direction,category,reference
TX-001,2026-10-07,300000,in,customer_receipt,INV-008
TX-002,2026-10-07,100000,out,owner_drawing,Owner withdrawal
```

POST `/v1/bank-imports` with `{ "account": "Operating account", "csv_text": "...", "confirm": false }` to preview, then `confirm:true` after review. Use a nonfixture business. Required headers are exact; at most 1,000 rows and 200 KB. Source transactions are deduplicated independently of upload operation keys.

## Corrections and recovery

- `/v1/allocations/{id}/reverse`: expected_version + reason; retains history.
- `/v1/receipts/{id}/reverse`: appends a compensation and reopens invoices.
- `/v1/deals/{id}/amend`: full typed terms, expected_version and reason; requires a fresh confirmation.
- `/v1/adjustments`: owner-only approved credit/write-off with reason.
- `/v1/jobs/{id}/retry`: extraction only; uncertain external sends are never blindly retried.
- `/v1/controls/pause`: stops new external action execution.
- `/v1/operations/health`: scoped owner queue/recovery counters.

## Device claim intake

Owner creates `/v1/android/devices` with a name and explicit payment-package allowlist, stores the returned claim-only token on the device in encrypted storage, and posts bounded notifications with `X-Device-Token`. The token grants no access to normal APIs. OTP/authentication messages and disallowed packages are rejected. This creates a claim only; the native Android app is not yet built.
