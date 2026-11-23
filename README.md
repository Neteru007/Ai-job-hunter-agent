# AI Job Hunter Telegram Agent — starter MVP

## Implemented
- Private Telegram bot with allowlisted user ID
- Recurring job discovery (Remotive public API), deduplication in SQLite
- ServiceNow keyword filtering and heuristic fit score
- Approval / rejection per vacancy, persisted in SQLite
- English editable CV generator from JSON profile
- Commands: `/start`, `/search`, `/status`, `/cv`

## Important limitations
- **No application is sent automatically.** Approval records the decision and provides a link for manual submission.
- Search uses one public source (Remotive), which may return very few ServiceNow vacancies.
- Salary is not reliably converted to €8,000 net. Ukraine remote eligibility cannot be verified by keywords.
- CV is a draft with placeholders. Review before use.

## Setup
1. Install Python 3.11+.
2. Run `python -m venv .venv`, activate it and run `pip install -r requirements.txt`.
3. Copy `.env.example` to `.env` and set `TELEGRAM_BOT_TOKEN` and `TELEGRAM_ALLOWED_USER_ID`.
4. Complete `cv_profile.json` with verified experience and achievements, then run `python build_cv.py`.
5. Run `python bot.py` and send `/start` and `/search` to your Telegram bot.

## Planned
Additional ATS sources, verified net salary and location eligibility, AI matching, tailored CV and cover letters, human-approved application submission adapters, receipts, and response tracking.

## Security
Never commit `.env` or credentials. Approvals are per vacancy; no bulk approval.
