/**
 * Neteru Career Hunter — Cloudflare Workers Telegram webhook.
 * No Telegram credentials are stored in GitHub.
 * Supported now: /start, /status, /search, and job-opening URL buttons.
 */

const EXPECTED_BOT = "NeteruCareerHunterBot";
const DEFAULT_OWNER_ID = "5229720107";
const REMOTIVE_URL = "https://remotive.com/api/remote-jobs?search=servicenow&limit=100";

function sameSecret(a, b) {
  if (!a || !b || a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

async function telegram(env, method, data = {}) {
  const response = await fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/${method}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
    signal: AbortSignal.timeout(20000),
  });
  const result = await response.json().catch(() => ({}));
  if (!response.ok || !result.ok) {
    // Never log a URL containing the token.
    throw new Error(`Telegram ${method} failed: HTTP ${response.status} (${result.error_code || "unknown"})`);
  }
  return result.result;
}

function say(env, chatId, text, replyMarkup) {
  return telegram(env, "sendMessage", {
    chat_id: chatId,
    text,
    ...(replyMarkup ? { reply_markup: replyMarkup } : {}),
  });
}

async function searchJobs(env, chatId) {
  await say(env, chatId, "🔎 Шукаю віддалені вакансії ServiceNow…");
  try {
    const response = await fetch(REMOTIVE_URL, {
      headers: { "User-Agent": "NeteruCareerHunter/1.0" },
      signal: AbortSignal.timeout(15000),
    });
    if (!response.ok) throw new Error(`Remotive returned HTTP ${response.status}`);
    const results = await response.json();
    const jobs = (Array.isArray(results.jobs) ? results.jobs : [])
      .filter((job) => {
        const title = String(job.title || "").toLowerCase();
        const location = String(job.candidate_required_location || "").toLowerCase();
        const description = String(job.description || "").toLowerCase();
        const joined = `${title} ${location} ${description}`;
        return (title.includes("servicenow") || title.includes("service now")) &&
          /(developer|architect|lead|engineer|consultant)/.test(title) &&
          /(remote|anywhere|worldwide|distributed)/.test(joined) &&
          !/(us only|usa only|united states only|must reside in the us|canada only|uk only|eu only|us-based only)/.test(joined);
      })
      .slice(0, 5);
    if (!jobs.length) {
      await say(env, chatId, "На Remotive зараз немає вакансій, що пройшли фільтри. Це лише одне джерело.");
      return;
    }
    await say(env, chatId, `Знайдено ${jobs.length} вакансій у цьому пошуку. Зарплату та можливість працювати з України потрібно перевіряти окремо.`);
    for (const job of jobs) {
      const title = String(job.title || "ServiceNow").slice(0, 150);
      const company = String(job.company_name || "Unknown").slice(0, 120);
      const location = String(job.candidate_required_location || "Not specified").slice(0, 140);
      const salary = String(job.salary || "Not disclosed").slice(0, 140);
      const url = String(job.url || "");
      const replyMarkup = /^https:\/\//i.test(url) ? {
        inline_keyboard: [[{ text: "Відкрити вакансію", url }]],
      } : undefined;
      await say(env, chatId,
        `💼 ${title}\n🏢 ${company}\n🌍 ${location}\n💶 ${salary}\n⚠️ €8 000 net/міс. і доступність з України не підтверджені.`,
        replyMarkup);
    }
  } catch (error) {
    console.error("Job search failed:", error instanceof Error ? error.name : "unknown");
    try {
      await say(env, chatId, "Пошук тимчасово недоступний. Спробуй /search пізніше.");
    } catch (replyError) {
      console.error("Could not report search failure.");
    }
  }
}

async function handleUpdate(update, env) {
  const message = update?.message;
  if (!message?.from || !message?.chat) return;
  const ownerId = String(env.TELEGRAM_ALLOWED_USER_ID || DEFAULT_OWNER_ID);
  if (String(message.from.id) !== ownerId || message.chat.type !== "private") return;
  const command = String(message.text || "").trim().split(/\s+/)[0].split("@")[0].toLowerCase();
  const chatId = message.chat.id;
  if (command === "/start" || command === "/help") {
    await say(env, chatId, "✅ Neteru Career Hunter працює!\n\n/start — перевірка\n/status — стан\n/search — вакансії ServiceNow");
  } else if (command === "/status") {
    await say(env, chatId, "✅ Онлайн: Cloudflare Worker відповідає на повідомлення.\nСервіс пошуку: Remotive.\nЦіль €8 000 net/міс. поки не перевіряється автоматично.");
  } else if (command === "/search") {
    await searchJobs(env, chatId);
  } else {
    await say(env, chatId, "Доступні команди: /start, /status, /search");
  }
}

function plain(message, status = 200) {
  return new Response(message, { status, headers: { "content-type": "text/plain; charset=utf-8", "cache-control": "no-store" } });
}

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    if (url.pathname === "/" || url.pathname === "/health") {
      return plain("Neteru Career Hunter Worker is running. Telegram webhook setup is a separate step.");
    }
    if (url.pathname === "/setup" && request.method === "GET") {
      // WEBHOOK_SECRET is deliberately not saved to GitHub; paste it in Cloudflare secrets.
      if (!sameSecret(url.searchParams.get("key") || "", env.WEBHOOK_SECRET || "")) {
        return plain("Unauthorized", 403);
      }
      if (!env.TELEGRAM_BOT_TOKEN || !env.WEBHOOK_SECRET) {
        return plain("Missing Cloudflare secrets", 500);
      }
      try {
        const bot = await telegram(env, "getMe");
        if (String(bot.username || "").toLowerCase() !== EXPECTED_BOT.toLowerCase()) {
          return plain("Telegram token belongs to a different bot. No webhook configured.", 400);
        }
        await telegram(env, "setWebhook", {
          url: `${url.origin}/webhook`,
          secret_token: env.WEBHOOK_SECRET,
          allowed_updates: ["message"],
          drop_pending_updates: false,
        });
        return plain("Webhook registered for @" + EXPECTED_BOT + ". Send /start in Telegram.");
      } catch (error) {
        console.error("Webhook registration error:", error instanceof Error ? error.message : "unknown");
        return plain("Telegram API did not confirm webhook registration. Review Worker logs.", 502);
      }
    }
    if (url.pathname !== "/webhook" || request.method !== "POST") return plain("Not found", 404);
    if (!sameSecret(request.headers.get("X-Telegram-Bot-Api-Secret-Token") || "", env.WEBHOOK_SECRET || "")) {
      return plain("Unauthorized", 403);
    }
    let update;
    try {
      update = await request.json();
    } catch (_) {
      return plain("Invalid JSON", 400);
    }
    ctx.waitUntil(handleUpdate(update, env).catch((error) => {
      console.error("Telegram update failed:", error instanceof Error ? error.message : "unknown");
    }));
    return plain("OK");
  },
};
