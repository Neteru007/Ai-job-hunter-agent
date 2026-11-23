"""One-shot GitHub Actions runner for Telegram job discovery.

No always-on polling. State is committed to the repository by the workflow.
Never stores credentials or CV contents in state.
"""
import asyncio
import html
import json
import logging
import os
from pathlib import Path

import httpx
from dotenv import load_dotenv
from bot import fetch_remotive, eligible, score, MIN_NET

load_dotenv()
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
USER_ID = int(os.environ.get("TELEGRAM_ALLOWED_USER_ID", "0"))
STATE_PATH = Path("state/jobs.json")
BASE = f"https://api.telegram.org/bot{TOKEN}"
log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def read_state():
    if not STATE_PATH.exists():
        return {"seen": {}, "decisions": {}, "offset": 0, "bootstrapped": False}
    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    return {"seen": state.get("seen", {}), "decisions": state.get("decisions", {}),
            "offset": int(state.get("offset", 0)), "bootstrapped": bool(state.get("bootstrapped", False))}


def save_state(state):
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


async def api(client, method, payload):
    """Retry Telegram rate limits and transient failures without exposing the token."""
    for attempt in range(6):
        try:
            resp = await client.post(f"{BASE}/{method}", json=payload)
            if resp.status_code == 429:
                try:
                    info = resp.json()
                    wait = int(info.get("parameters", {}).get("retry_after", 0))
                except (ValueError, TypeError):
                    wait = 0
                if not wait:
                    wait = min(2 ** (attempt + 1), 60)
                if attempt == 5:
                    raise RuntimeError(f"Telegram rate limit persisted for {method} after retries")
                log.warning("Telegram rate limit on %s; waiting %s seconds", method, wait)
                await asyncio.sleep(min(wait + 1, 120))
                continue
            if resp.status_code in (500, 502, 503, 504):
                if attempt == 5:
                    raise RuntimeError(f"Telegram temporarily unavailable for {method}")
                await asyncio.sleep(min(2 ** (attempt + 1), 30))
                continue
            resp.raise_for_status()
            result = resp.json()
            if not result.get("ok"):
                raise RuntimeError(f"Telegram {method} failed: {result.get('description', 'unknown')}")
            return result["result"]
        except (httpx.TimeoutException, httpx.ConnectError):
            if attempt == 5:
                raise
            await asyncio.sleep(min(2 ** (attempt + 1), 30))
    raise RuntimeError(f"Telegram request {method} exhausted retries")


async def send(client, text, buttons=None):
    payload = {"chat_id": USER_ID, "text": text, "parse_mode": "HTML",
               "disable_web_page_preview": True}
    if buttons:
        payload["reply_markup"] = {"inline_keyboard": buttons}
    await api(client, "sendMessage", payload)


async def handle_updates(client, state):
    updates = await api(client, "getUpdates", {"offset": state["offset"], "timeout": 0, "limit": 100})
    for update in updates:
        uid = update["update_id"]
        state["offset"] = max(state["offset"], uid + 1)
        cb = update.get("callback_query")
        if cb:
            await api(client, "answerCallbackQuery", {"callback_query_id": cb["id"]})
            if cb.get("from", {}).get("id") != USER_ID:
                continue
            data = cb.get("data", "")
            if ":" not in data:
                continue
            action, key = data.split(":", 1)
            if action not in ("approve", "reject") or key not in state["seen"]:
                continue
            if key in state["decisions"]:
                await send(client, "Already decided: " + html.escape(state["decisions"][key]))
                continue
            state["decisions"][key] = "approved" if action == "approve" else "rejected"
            msg = cb.get("message", {})
            if msg.get("chat", {}).get("id") == USER_ID and msg.get("message_id"):
                await api(client, "editMessageReplyMarkup", {
                    "chat_id": USER_ID, "message_id": msg["message_id"],
                    "reply_markup": {"inline_keyboard": []}})
            if action == "approve":
                url = state["seen"][key]["url"]
                await send(client, f"Approved for manual application: <a href='{html.escape(url, quote=True)}'>Open job</a>. No CV has been sent.")
            else:
                await send(client, "Vacancy rejected.")
            continue
        message = update.get("message", {})
        if message.get("from", {}).get("id") != USER_ID:
            continue
        command = (message.get("text") or "").split(" ")[0].split("@")[0]
        if command == "/start":
            await send(client, "Job Hunter scheduled mode active. /status shows counts; /search requests an immediate search during the next scheduled run. Buttons are processed at the next run.")
        elif command == "/status":
            await send(client, f"Tracked: {len(state['seen'])}; approved: {sum(v == 'approved' for v in state['decisions'].values())}; rejected: {sum(v == 'rejected' for v in state['decisions'].values())}.")
        elif command == "/search":
            await send(client, "Searching now…")
        elif command == "/cv":
            await send(client, "CV creation is available locally with python build_cv.py. A reviewed CV is not yet stored or sent by this workflow.")


async def run():
    if not TOKEN or not USER_ID:
        raise SystemExit("Set TELEGRAM_BOT_TOKEN and TELEGRAM_ALLOWED_USER_ID as Actions secrets.")
    state = read_state()
    async with httpx.AsyncClient(timeout=35) as client:
        # Announce only once, and persist immediately so failed searches do not resend it.
        if not state["bootstrapped"]:
            await send(client, "🤖 AI Job Hunter підключено! Перевіряю команди та шукаю вакансії ServiceNow. Це тестове повідомлення.")
            state["bootstrapped"] = True
            save_state(state)
        # getUpdates returns 409 if a webhook is active; avoid the extra getWebhookInfo call.
        await handle_updates(client, state)
        try:
            jobs = await fetch_remotive()
        except Exception:
            save_state(state)
            raise
        sent = 0
        for job in jobs:
            if not eligible(job):
                continue
            key = job["source_id"]
            if key in state["seen"]:
                continue
            # Cap the number of messages; remaining listings will be checked next run.
            if sent >= 15:
                break
            title = html.escape(job["title"])
            company = html.escape(job["company"])
            location = html.escape(job["location"])
            salary = html.escape(job["salary"])
            url = html.escape(job["url"], quote=True)
            points = score(job)
            text = (f"<b>{title}</b>\n{company} · {location}\nSalary: {salary}\n"
                    f"Match estimate: {points}/100\nTarget: €{MIN_NET:,} net/month (unverified)\n"
                    f"⚠️ Confirm Ukraine eligibility and net pay.\n<a href='{url}'>View vacancy</a>")
            # Telegram callback_data is limited to 64 bytes; Remotive IDs are short.
            if len(key.encode("utf-8")) > 55:
                continue
            buttons = [[{"text": "Approve", "callback_data": f"approve:{key}"},
                        {"text": "Reject", "callback_data": f"reject:{key}"}]]
            await send(client, text, buttons)
            state["seen"][key] = {"title": job["title"], "url": job["url"]}
            sent += 1
        save_state(state)
        log.info("Sent %s new jobs; tracked %s", sent, len(state["seen"]))


if __name__ == "__main__":
    asyncio.run(run())
