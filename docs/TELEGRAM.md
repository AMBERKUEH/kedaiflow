# Telegram connection guide

No bot credentials were provided. Transport was tested with fake adapters and webhook integration tests. No live Telegram message has been sent.

## Create and identify a development bot

1. Use Telegram's verified [BotFather](https://core.telegram.org/bots/features#botfather) and `/newbot`.
2. Save the issued token in the ignored `.env` as `TELEGRAM_BOT_TOKEN`. Do not paste it in ordinary chat.
3. Run `python -m services.api.telegram identity` in the configured environment. It prints only numeric bot ID and username. Put the ID in `TELEGRAM_BOT_ID`.
4. Use a development bot separate from any production bot. External commercial actions remain simulation/draft unless explicitly changed and authorized.

## Authenticated staff binding

Sign in to KedaiFlow → Review → Connect Telegram privately → generate one-use code. Send `/bind CODE` privately to the bot within five minutes. The code references the authenticated user/business, not a display name. The worker verifies membership and consumes it once. Staff role checks still apply. A code is sensitive; do not share it with someone else.

## Local polling

Set `TELEGRAM_MODE=polling`. With API/database initialized:

```text
python -m services.api.telegram poll
python -m services.api.worker
```

Use separate terminals. Polling refuses if a webhook exists. Run one poller per bot; Telegram conflicts must be resolved by stopping the extra process. Updates are stored before advancing offsets; replays are scoped by numeric bot ID and update ID. Pending updates survive a poller restart.

Send a text or supported small media file. The bot stores it privately and returns an evidence ID. Review extracted terms in the companion. `/money` returns only the authenticated finance user's current outstanding total. `/review ACTION_ID` previews exact action content and creates a short-lived opaque approval callback. Callback checks actor, private chat, tenant, role, expiry, payload digest, current invoice state and prior consumption.

## Recipient binding and terms confirmation

Recipient binding is a two-step API workflow, documented in OpenAPI:

1. Owner calls `POST /v1/counterparties/{id}/telegram-invite` with an idempotency key. Manually share the returned `/connect TOKEN` with the intended recipient.
2. Recipient sends that command in their own private bot chat.
3. Owner lists `GET /v1/channels/telegram/recipient-invites`, independently verifies the identity/chat, then calls `POST .../{invite_id}/confirm` with `expected_version`, `observed_chat_id` and a reason.
4. Binding changes increment the counterparty version and invalidate pending actions.

An approved recipient can ask `/deal DEAL_ID` for **their own** confirmed shared terms. `/confirm DEAL_ID VERSION` records their acceptance of that exact version. Arbitrary responses or thumbs-up are not interpreted as acceptance. No cash forecast or unrelated invoice is exposed to that recipient. The commercial assurance is that the owner verified this Telegram identity, not a government identity check.

## HTTPS webhook deployment

Deployment is not authorized or performed in this session. When separately approved:

1. Configure a persistent HTTPS backend, secrets, private storage and worker.
2. Stop polling. Set `TELEGRAM_MODE=webhook`, `APP_BASE_URL=https://your-approved-backend`, and a random `TELEGRAM_WEBHOOK_SECRET` generated locally.
3. Run `python -m services.api.telegram set-webhook`. The adapter retains pending updates.
4. Run `python -m services.api.telegram webhook-info`; it prints only configuration status and pending count.
5. Test an authorized private development chat. Inspect durable intake and worker results before enabling any real action mode.

Webhook route: `POST /v1/channels/telegram/webhook`. It checks the secret header, caps payload at 256 KB, validates an integer update ID, commits the inbox row and then returns success. Database failure must not be treated as acknowledgement.

To return to polling: stop webhook intake/dispatch deliberately, run `delete-webhook` (retains pending updates), set polling mode, verify no webhook exists, then start one poller. Never use both delivery modes simultaneously.

## External actions and unknown outcomes

`ACTION_MODE=draft` disables sending. `simulation` works only in fixture businesses and labels the outcome `simulated_sent`. `connected` requires configured bot credentials, a verified recipient binding and current owner approval. It honors configured business quiet hours. Do not turn on connected commercial sending without separate user authorization.

Timeout/5xx/transport ambiguity becomes `outcome_unknown`. Telegram does not provide universal idempotent send reconciliation; never blindly replay an uncertain send. Inspect the recipient conversation through an authorized operator, record evidence and create a fresh approval only when safe. API acceptance means Telegram accepted the message, not that someone read it or agreed.

Group modes are denied by default. The full shared deal-room interface and Mini App initData flow remain future work. The supplied reference ZIP was not available; this implementation was built independently from the PRD and official Bot API.
