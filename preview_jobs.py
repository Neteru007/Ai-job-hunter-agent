"""Create a readable GitHub Actions summary even when Telegram Bot API is down."""
import asyncio
import os
from datetime import datetime, timezone
from urllib.parse import urlparse

from bot import eligible, fetch_remotive, score


def cell(value):
    """Escape table cells to keep workflow summaries readable."""
    return str(value or "—").replace("|", r"\|").replace("\n", " ").replace("\r", " ")


async def main():
    lines = [
        "# ServiceNow remote jobs — preview",
        "",
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "Source: Remotive. **Remote eligibility from Ukraine and €8,000 net/month are NOT verified.**",
        "The score is a keyword heuristic, not an assessment of salary or hiring eligibility.",
        "",
    ]
    try:
        all_jobs = await fetch_remotive()
        matching = sorted((j for j in all_jobs if eligible(j)),
                          key=lambda j: score(j), reverse=True)
        lines.append(f"Remote ServiceNow matches in this source: **{len(matching)}**")
        lines.append("")
        if matching:
            lines.extend([
                "| Vacancy | Company | Location | Published salary | Match score |",
                "|---|---|---|---|---:|",
            ])
            for j in matching[:20]:
                url = j["url"]
                if urlparse(url).scheme not in ("http", "https"):
                    continue
                lines.append(
                    f"| [{cell(j['title'])}]({url}) | {cell(j['company'])} | "
                    f"{cell(j['location'])} | {cell(j['salary'])} | {score(j)}/100 |"
                )
        else:
            lines.append("No matches from Remotive on this run. This does not mean no jobs exist elsewhere.")
        print(f"Remotive returned {len(all_jobs)} items; {len(matching)} passed the ServiceNow remote filters.")
    except Exception as exc:
        lines.append(f"Remotive check unavailable: {type(exc).__name__}. No vacancy results were verified.")
        print("Vacancy source unavailable:", type(exc).__name__)
        raise
    finally:
        summary = os.environ.get("GITHUB_STEP_SUMMARY")
        if summary:
            with open(summary, "a", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")
        else:
            print("\n".join(lines))


if __name__ == "__main__":
    asyncio.run(main())
