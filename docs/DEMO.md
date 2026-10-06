# Reproducible connected demonstration

All names, claims, money and responses below are synthetic. The public competition rubric in the PRD has not been revalidated against the organizer. This is a product demonstration, not a claim of eligibility, pilot impact or ranking.

## Preparation

Start the API, durable worker and companion. Choose **Explore a sample kedai**. For pristine data, point DATABASE_URL at a new isolated SQLite file and run the seed command. Do not reset an existing business ledger. Check the Demo workspace badge and Simulator receipt labels.

## Story

1. **Mixed-language evidence:** Deals → inspect the note beginning “Boss, 50 crates tomato untuk Friday…”. It includes English, Malay and Chinese. No exact due date is invented. With no model configured, this is a narrow deterministic candidate and manual review, not a claim of validated transcription.
2. **Clarify:** Open Friday tomato delivery → Review & confirm. Enter exact delivery/balance dates and confirm charges. The card says owner-recorded interpretation, not bilateral acceptance.
3. **Missing invoice:** Review → Delivered, but no issued invoice. Inspect the RM1,200 case. Validate it with a reason. On Deals, prepare an invoice for the morning greens deal and issue it on Money. The case resolves because the recorded link now exists; no extra sale is created by merely reviewing the case.
4. **Conflicting payment evidence:** Open INV-2026-008 evidence. The claim says RM8,000, including an injected bank-change instruction. The simulator has only RM3,000. No instruction from the source can alter a receiving account, permission or tool.
5. **Reconcile:** Match RM3,000 against the RM8,000 invoice. Outstanding becomes RM5,000, not zero. The unapplied-receipt case closes. Forecast uses remaining outstanding, avoiding the already allocated amount as a second expected receipt.
6. **Deal Rescue:** Decisions → add a RM6,000 cost on the critical date and a RM4,000 deposit before it. Calculate. Move the deposit after the critical date and compare. Shift a supplier invoice later and inspect the full daily table/beyond-horizon list. Nothing changes the actual invoice due date.
7. **Approve exactly:** Money → draft the RM5,000 reminder. Review displays recipient, exact words, digest, expiry and simulation label. Approve. The worker changes it to simulated_sent. This is not real Telegram delivery or a customer promise.
8. **Observed response and receipt:** Record a candidate acceptance/decline with exact text. Then Money → Record receipt → enter a new unique simulator reference and RM5,000. Allocate it to the remaining invoice. Outstanding becomes zero, and any still-pending old reminder becomes stale/canceled.
9. **Explain what happened:** Open “Where did my money go?” and compare sales with cash received. Use cash bridge for the selected dates and inspect source IDs. A receipt, promise, invoice sale, inventory purchase and owner drawing are distinct.

## Adversarial variations

- Duplicate the same source reference: no duplicate receipt.
- Try to allocate RM3,001 from the RM3,000 receipt: entire command rejected.
- Approve, then record a new receipt before worker dispatch: stale reminder suppressed.
- Use another business ID or a sales membership to request cash: denied.
- Ask for arbitrary SQL or another merchant’s data: controlled-metric clarification/denial.
- Trigger mocked transport timeout: unknown outcome remains visible, with no blind resend.

Automated tests cover these state invariants. Real bot, OCR/transcription, bank and regulatory systems need separate authorized integration evidence.
