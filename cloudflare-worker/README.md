# Neteru Career Hunter — Cloudflare Workers

An instant-response Telegram bot powered by Cloudflare Workers. Code lives in this folder. **Committing to GitHub does NOT deploy or activate it** until a Worker is connected and configured.

## What works in this version

- Responds to the owner's `/start` and `/status` commands
- `/search` searches Remotive for remote ServiceNow vacancies and returns up to five links
- Rejects requests from unknown Telegram user IDs and private-chat only
- Validates the Telegram webhook `secret_token` header
- Keeps the bot token out of the public GitHub repository

**Not implemented yet:** Approve/Reject state, persistent vacancies, automatic job applications, multiple job sites, automated salary checks, or scheduled notifications. No claim of €8,000 net pay or Ukraine eligibility is made.

## Install with GitHub integration

1. Log into https://dash.cloudflare.com/ and select **Workers & Pages** → **Create application** → **Import a repository** / **GitHub**.
2. Authorize GitHub and select `Neteru007/Ai-job-hunter-agent`.
3. Set **Root directory**: `cloudflare-worker`.
4. Set **Worker name**: `neteru-career-hunter-bot` (must match `wrangler.toml`).
5. Leave the build command blank (no build needed). **Deploy command**: `npx wrangler deploy`. Deploy to the free tier.
6. Open the Worker dashboard → **Settings → Variables and Secrets**.
7. Add two **encrypted secrets**:
   - `TELEGRAM_BOT_TOKEN`: the token for **@NeteruCareerHunterBot** from @BotFather.
   - `WEBHOOK_SECRET`: a new long random string (letters, digits, `_`, `-` only, e.g. 32+ characters); keep it private.
8. The owner user ID `5229720107` is already configured as `TELEGRAM_ALLOWED_USER_ID` in `wrangler.toml`; override it only if needed. Deploy after saving secrets if the dashboard requests it.
9. Open the generated Worker URL, for example `https://neteru-career-hunter-bot.<your-subdomain>.workers.dev/health`, and expect **Neteru Career Hunter Worker is running**.
10. Register webhook **once**: open `https://neteru-career-hunter-bot.<your-subdomain>.workers.dev/setup?key=<YOUR_WEBHOOK_SECRET>` in the browser. Expect **Webhook registered for @NeteruCareerHunterBot. Send /start in Telegram.**
    - The setup URL includes a secret: do not share it, screenshot it, or paste it into public chats. Clear it from browser history after use.
    - If the setup returns 502, inspect Cloudflare Worker logs; Telegram API may still be unavailable.
11. Open https://t.me/NeteruCareerHunterBot, press **Start**, or send `/start`. Then test `/status` and `/search`.

## Verify

- `/health`: confirms Worker deployment (does not verify Telegram).
- `/setup`: verifies Telegram `getMe` returns the expected bot and calls `setWebhook`.
- `/start`: confirms real Telegram message delivery.
- Check the Worker **Logs** for errors. Errors never intentionally print the bot token.

## Notes

- Leave the old GitHub Actions scheduled Telegram polling disabled to avoid Telegram webhook/getUpdates conflicts.
- Cloudflare's free plan has request limits; review current limits at https://developers.cloudflare.com/workers/platform/limits/.
- The project uses Cloudflare Workers' standard service-worker fetch interface (ES module), no npm dependencies.
- If your bot's own Telegram API backend is failing, moving hosting may not solve the underlying Telegram problem.
