#!/usr/bin/env python3
"""
Fetch the last year of daily contribution counts for the profile owner and
write data/contributions.json with the raw days plus derived stats
(total, current streak, longest streak, busiest day, monthly totals).

Uses GitHub's GraphQL API with the token Actions provides (GITHUB_TOKEN).
Standard library only, so the workflow needs no pip install.

    GITHUB_TOKEN=... python scripts/fetch_contributions.py
    python scripts/fetch_contributions.py --sample   # offline demo data
"""
import datetime
import json
import os
import random
import sys
import urllib.request

USERNAME = os.environ.get("GH_PROFILE_USER", "miyxotkem")
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
OUT_PATH = os.path.join(ROOT, "data", "contributions.json")

QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount contributionLevel } }
      }
    }
    pinnedItems(first: 3, types: REPOSITORY) {
      nodes { ... on Repository { name description url stargazerCount primaryLanguage { name } } }
    }
    repositories(first: 20, ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC,
                 orderBy: {field: STARGAZERS, direction: DESC}) {
      nodes { name description url stargazerCount primaryLanguage { name } }
    }
  }
}
"""

LEVELS = {"NONE": 0, "FIRST_QUARTILE": 1, "SECOND_QUARTILE": 2,
          "THIRD_QUARTILE": 3, "FOURTH_QUARTILE": 4}


def fetch(token):
    body = json.dumps({"query": QUERY, "variables": {"login": USERNAME}}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={"Authorization": f"bearer {token}",
                 "Content-Type": "application/json",
                 "User-Agent": "profile-readme-cards"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.load(resp)
    if payload.get("errors"):
        raise RuntimeError(payload["errors"])
    user = payload["data"]["user"]
    weeks = user["contributionsCollection"]["contributionCalendar"]["weeks"]
    days = [
        {"date": d["date"], "count": d["contributionCount"], "level": LEVELS.get(d["contributionLevel"], 0)}
        for w in weeks for d in w["contributionDays"]
    ]
    # Pinned repos first, then most-starred public repos (skipping this profile repo).
    seen, repos = set(), []
    for r in user["pinnedItems"]["nodes"] + user["repositories"]["nodes"]:
        if not r or r["name"] in seen or r["name"].lower() == USERNAME.lower():
            continue
        seen.add(r["name"])
        repos.append({"name": r["name"], "description": r["description"] or "", "url": r["url"],
                      "stars": r["stargazerCount"],
                      "language": (r["primaryLanguage"] or {}).get("name", "")})
    return days, repos[:3]


SAMPLE_REPOS = [
    {"name": "uav-detection", "description": "Real-time drone detection in live video with a deep learning pipeline.",
     "url": f"https://github.com/{USERNAME}", "stars": 0, "language": "Python"},
    {"name": "elearning-hub", "description": "Desktop education management system with real-time Firebase sync.",
     "url": f"https://github.com/{USERNAME}", "stars": 0, "language": "C#"},
    {"name": "dotnet-lab", "description": "Experiments with .NET 8, WPF and clean desktop architecture.",
     "url": f"https://github.com/{USERNAME}", "stars": 0, "language": "C#"},
]


def sample_days():
    """Deterministic fake year, used for local previews without a token."""
    rng = random.Random(29)
    today = datetime.date.today()
    start = today - datetime.timedelta(days=364 + (today.weekday() + 1) % 7)
    days, d = [], start
    while d <= today:
        busy = 0.35 + 0.45 * (d.month in (3, 4, 5, 9, 10, 11))
        c = 0 if rng.random() > busy else rng.choice([1, 1, 2, 3, 4, 6, 9, 14])
        days.append({"date": d.isoformat(), "count": c, "level": 0})
        d += datetime.timedelta(days=1)
    for x in days:
        c = x["count"]
        x["level"] = 0 if c == 0 else 1 if c < 3 else 2 if c < 6 else 3 if c < 10 else 4
    return days


def stats(days):
    total = sum(d["count"] for d in days)

    # Current streak: today may not be over yet, so a zero today doesn't break it.
    i = len(days) - 1
    if i >= 0 and days[i]["count"] == 0:
        i -= 1
    current = 0
    while i >= 0 and days[i]["count"] > 0:
        current += 1
        i -= 1

    longest = run = 0
    for d in days:
        run = run + 1 if d["count"] > 0 else 0
        longest = max(longest, run)

    best = max(days, key=lambda d: d["count"]) if days else {"date": "", "count": 0}
    active = sum(1 for d in days if d["count"] > 0)

    months = {}
    for d in days:
        months[d["date"][:7]] = months.get(d["date"][:7], 0) + d["count"]
    monthly = [{"month": k, "count": v} for k, v in sorted(months.items())][-12:]

    return {"total": total, "current_streak": current, "longest_streak": longest,
            "best_day": {"date": best["date"], "count": best["count"]},
            "active_days": active, "monthly": monthly}


def main():
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if "--sample" in sys.argv:
        days, repos = sample_days(), SAMPLE_REPOS
    elif token:
        days, repos = fetch(token)
    else:
        sys.exit("GITHUB_TOKEN not set (use --sample for demo data)")

    days.sort(key=lambda d: d["date"])
    out = {"user": USERNAME,
           "updated": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
           "sample": "--sample" in sys.argv,
           "stats": stats(days), "repos": repos, "days": days}
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(out, f, indent=1)
    print(f"wrote {len(days)} days, total={out['stats']['total']}")


if __name__ == "__main__":
    main()
