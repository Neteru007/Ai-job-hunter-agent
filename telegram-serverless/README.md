# Telegram Serverless (Neteru Career Hunter)

This is the alternative to the old GitHub Actions polling bot, which could not reliably reach Telegram Bot API in November 2026.

## Current status

Source code is prepared but **has not been deployed** to Telegram. Committing this file to GitHub does not activate the Telegram bot.

## Enable using BotFather on mobile

1. Open @BotFather and select **Neteru Career Hunter Bot**.
2. Choose **Serverless** and enable it (if requested).
3. Open **Handlers**, create or edit the **message** handler.
4. Paste the contents of [handlers/message.js](handlers/message.js), and **Save** (deploy).
5. Open @NeteruCareerHunterBot and send `/start`, `/status`, then `/search`.

Telegram officially documents this workflow: https://core.telegram.org/bots/serverless#on-the-go-with-botfather

The handler only responds to the authorized Telegram owner ID and private chats.

## Commands

- `/start` or `/help`: confirmation and available commands.
- `/status`: confirm native handler is running.
- `/search`: fetch up to 5 ServiceNow remote jobs from Remotive. Salary and availability from Ukraine are unverified.

There is no job approval persistence, automatic applications, or background delivery in this early version. Those require a database and additional handlers once `/start` is verified.

The old scheduled GitHub Actions Telegram polling workflow was disabled to avoid conflicts with Telegram Serverless's webhook. It is still available as a manual workflow for debugging.

## Local deployment (optional)

Telegram's CLI requires a **separate CLI Access token** under @BotFather -> your bot -> Serverless -> CLI Access. Do not commit it to GitHub.

```sh
cd telegram-serverless
npx tgcloud init
npx tgcloud login
npx tgcloud push
```
