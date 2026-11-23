"""Telegram job discovery with human-approved manual application workflow."""
import html
import logging
import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import httpx
from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

load_dotenv()
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
ALLOWED_ID = int(os.getenv('TELEGRAM_ALLOWED_USER_ID', '0'))
DB = os.getenv('DATABASE_PATH', 'job_hunter.db')
INTERVAL = max(1, int(os.getenv('SEARCH_INTERVAL_HOURS', '6')))
MIN_NET = int(os.getenv('MIN_NET_EUR', '8000'))
ROLES = ('servicenow', 'service now')
REMOTE = ('remote', 'work from anywhere', 'distributed', 'home-based')
BLOCKED = ('us only', 'usa only', 'united states only', 'must reside in the us', 'canada only', 'uk only', 'united kingdom only', 'eu only', 'european union only', 'us-based only')
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


def connect():
    c = sqlite3.connect(DB)
    c.execute("""CREATE TABLE IF NOT EXISTS jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT, source_id TEXT UNIQUE,
        title TEXT, company TEXT, location TEXT, url TEXT, description TEXT,
        salary TEXT, score INTEGER, status TEXT DEFAULT 'new',
        discovered_at TEXT, approved_at TEXT)""")
    c.commit()
    return c


def eligible(job):
    text = ' '.join(str(job.get(k, '')) for k in ('title', 'description', 'location')).lower()
    title = job['title'].lower()
    if not any(x in text for x in ROLES):
        return False
    if not any(x in title for x in ('developer', 'architect', 'lead', 'engineer', 'consultant')):
        return False
    if not any(x in text for x in REMOTE):
        return False
    if any(x in text for x in BLOCKED):
        return False
    # Generic remote labels do not prove eligibility to work from Ukraine.
    return True


def score(job):
    text = (job['title'] + ' ' + job['description']).lower()
    points = 55
    for word, value in [('senior', 8), ('architect', 10), ('technical lead', 10), ('integration', 5), ('javascript', 4), ('rest api', 4), ('itsm', 3), ('csm', 3), ('worldwide', 5), ('anywhere', 5)]:
        if word in text:
            points += value
    return min(points, 100)


async def fetch_remotive():
    async with httpx.AsyncClient(timeout=30, headers={'User-Agent': 'PersonalJobHunter/0.1'}) as client:
        response = await client.get('https://remotive.com/api/remote-jobs', params={'search': 'servicenow', 'limit': 100})
        response.raise_for_status()
        data = response.json()
    results = []
    for j in data.get('jobs', []):
        url = j.get('url', '')
        if urlparse(url).scheme not in ('http', 'https'):
            continue
        results.append({'source_id': f"remotive:{j['id']}", 'title': j.get('title', ''),
                        'company': j.get('company_name', ''), 'location': j.get('candidate_required_location', ''),
                        'url': url, 'description': re.sub('<[^>]+>', ' ', j.get('description', ''))[:12000],
                        'salary': j.get('salary') or 'Not disclosed'})
    return results


async def discover():
    jobs = await fetch_remotive()
    inserted = []
    with connect() as c:
        for job in jobs:
            if not eligible(job):
                continue
            points = score(job)
            cur = c.execute("""INSERT OR IGNORE INTO jobs
                (source_id,title,company,location,url,description,salary,score,discovered_at)
                VALUES (?,?,?,?,?,?,?,?,?)""",
                (job['source_id'], job['title'], job['company'], job['location'], job['url'],
                 job['description'], job['salary'], points, datetime.now(timezone.utc).isoformat()))
            if cur.rowcount:
                inserted.append((cur.lastrowid, job, points))
    return inserted


def job_message(j, points):
    return (f"<b>{html.escape(j['title'])}</b>\n"
            f"Company: {html.escape(j['company'])}\n"
            f"Location: {html.escape(j['location'])}\n"
            f"Salary: {html.escape(j['salary'])}\n"
            f"Match score (heuristic): {points}/100\n"
            f"Target: €{MIN_NET:,} net/month (NOT VERIFIED)\n"
            f"⚠️ Ukraine remote eligibility and net pay require verification.\n"
            f"<a href='{html.escape(j['url'], quote=True)}'>View job</a>")


async def notify(bot, rows):
    for job_id, job, points in rows[:20]:
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton('Approve', callback_data=f'approve:{job_id}'),
            InlineKeyboardButton('Reject', callback_data=f'reject:{job_id}')]])
        await bot.send_message(ALLOWED_ID, job_message(job, points), parse_mode='HTML', reply_markup=keyboard)


async def auth(update: Update):
    if not update.effective_user or update.effective_user.id != ALLOWED_ID:
        if update.effective_message:
            await update.effective_message.reply_text('Access denied.')
        return False
    return True


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await auth(update): return
    await update.message.reply_text('Job Hunter is ready. /search finds new jobs; /status shows totals; /cv sends your reviewed CV. Approving a job never sends an application automatically.')


async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await auth(update): return
    await update.message.reply_text('Searching vacancies…')
    try:
        rows = await discover()
        await update.message.reply_text(f'Found {len(rows)} new matching listings. Salary and Ukraine eligibility must be checked.')
        await notify(context.bot, rows)
    except Exception:
        log.exception('Job search failed')
        await update.message.reply_text('Search failed. Check logs or retry later.')


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await auth(update): return
    with connect() as c:
        counts = c.execute('SELECT status, COUNT(*) FROM jobs GROUP BY status').fetchall()
    await update.message.reply_text('Job statuses: ' + (', '.join(f'{s}: {n}' for s, n in counts) or 'empty'))


async def cv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await auth(update): return
    path = Path(os.getenv('CV_PATH', 'resume.docx'))
    if not path.exists():
        await update.message.reply_text('CV not found. Review cv_profile.json and run python build_cv.py first.')
        return
    with path.open('rb') as f:
        await update.message.reply_document(f, filename='resume.docx')


async def decision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await auth(update): return
    q = update.callback_query
    await q.answer()
    action, raw_id = q.data.split(':', 1)
    if action not in ('approve', 'reject') or not raw_id.isdigit(): return
    with connect() as c:
        row = c.execute('SELECT title,company,url,status FROM jobs WHERE id=?', (int(raw_id),)).fetchone()
        if not row:
            await q.message.reply_text('Job not found.')
            return
        title, company, url, current = row
        if current != 'new':
            await q.message.reply_text(f'Already processed: {current}')
            return
        state = 'approved' if action == 'approve' else 'rejected'
        c.execute('UPDATE jobs SET status=?,approved_at=? WHERE id=?',
                  (state, datetime.now(timezone.utc).isoformat() if state == 'approved' else None, int(raw_id)))
    await q.edit_message_reply_markup(reply_markup=None)
    if state == 'approved':
        await q.message.reply_text(f'Approved: {title} at {company}. Open {url} and submit your reviewed CV. This version does NOT send applications.')
    else:
        await q.message.reply_text(f'Rejected: {title} at {company}.')


async def scheduled(context: ContextTypes.DEFAULT_TYPE):
    try:
        rows = await discover()
        await notify(context.bot, rows)
    except Exception:
        log.exception('Scheduled search failed')


def main():
    if not TOKEN or not ALLOWED_ID:
        raise SystemExit('Set TELEGRAM_BOT_TOKEN and TELEGRAM_ALLOWED_USER_ID in .env')
    connect().close()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('search', search))
    app.add_handler(CommandHandler('status', status))
    app.add_handler(CommandHandler('cv', cv))
    app.add_handler(CallbackQueryHandler(decision, pattern=r'^(approve|reject):\d+$'))
    app.job_queue.run_repeating(scheduled, interval=INTERVAL * 3600, first=15)
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
