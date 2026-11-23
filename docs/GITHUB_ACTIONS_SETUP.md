# GitHub Actions setup

The workflow runs every six hours (UTC) and can also be launched manually from **Actions → AI Job Hunter → Run workflow**.

## Required secrets

Open **Settings → Secrets and variables → Actions → New repository secret**.

- `TELEGRAM_BOT_TOKEN`: the secret token from BotFather. Do not paste it in chat or commit it.
- `TELEGRAM_ALLOWED_USER_ID`: your numeric Telegram user ID, not your bot username.

Set **Settings → Actions → General → Workflow permissions** to **Read and write permissions** if state commits fail. The workflow also declares `contents: write`.

Open your bot in Telegram and send `/start`, then trigger the workflow manually. On scheduled mode, messages and approval buttons are handled only when the workflow runs, not instantly.

## Security and limitations

- The repository is currently public. `state/jobs.json` is committed to GitHub and contains job titles, links, decisions and Telegram update offset, but no resume or token. Switch the repository to private if you prefer to keep your job search history private.
- The job source is currently Remotive only. Search results may be sparse.
- The €8,000 net threshold is **not enforced** because listings typically lack verified net salary and tax details. Likewise, eligibility to work remotely from Ukraine is not guaranteed.
- Approve/reject only records a decision. **No application is submitted automatically.**
- The bot must not be running elsewhere with polling or an active webhook using the same token.
- Scheduled GitHub Actions can be delayed or paused. This is not a 24/7 bot.
- GitHub Actions has free-minute quotas depending on account and repository visibility. Review usage in GitHub billing settings.
- To generate your draft CV locally: `python build_cv.py`, then review placeholders and achievements.
