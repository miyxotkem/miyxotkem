#!/usr/bin/env python3
"""
Fetch the last year of daily contribution counts for the profile owner and
write data/contributions.json with the raw days plus derived stats
(total, current streak, longest streak, busiest day, monthly totals),
plus your commits from the last year bucketed by local hour of day.

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

TZ_OFFSET = int(os.environ.get("PROFILE_TZ_OFFSET", "7"))  # hours from UTC for the by-hour chart

CALENDAR = """
query($login: String!) {
  user(login: $login) {
    id
    contributionsCollection {
      contributionCalendar {
        weeks { contributionDays { date contributionCount contributionLevel } }
      }
    }
    repositories(first: 50, ownerAffiliations: OWNER, isFork: false,
                 orderBy: {field: PUSHED_AT, direction: DESC}) {
      nodes { name owner { login } }
    }
  }
}
"""

HISTORY = """
query($owner: String!, $name: String!, $uid: ID!, $since: GitTimestamp!, $after: String) {
  repository(owner: $owner, name: $name) {
    defaultBranchRef { target { ... on Commit {
      history(first: 100, after: $after, since: $since, author: {id: $uid}) {
        pageInfo { hasNextPage endCursor }
        nodes { authoredDate }
      }
    } } }
  }
}
"""

LEVELS = {"NONE": 0, "FIRST_QUARTILE": 1, "SECOND_QUARTILE": 2,
          "THIRD_QUARTILE": 3, "FOURTH_QUARTILE": 4}


def gql(token, query, variables):
    body = json.dumps({"query": query, "variables": variables}).encode()
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
    return payload["data"]


def commit_hours(token, uid, repos):
    """Count your commits from the last year by local hour of day (0-23)."""
    since = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=365)).strftime("%Y-%m-%dT%H:%M:%SZ")
    tz = datetime.timezone(datetime.timedelta(hours=TZ_OFFSET))
    hours = [0] * 24
    for r in repos:
        after = None
        for _ in range(10):  # at most 1,000 commits per repo
            try:
                data = gql(token, HISTORY, {"owner": r["owner"]["login"], "name": r["name"],
                                            "uid": uid, "since": since, "after": after})
            except Exception as e:  # an empty or inaccessible repo shouldn't sink the whole run
                print(f"skip {r['name']}: {e}", file=sys.stderr)
                break
            ref = (data.get("repository") or {}).get("defaultBranchRef")
            if not ref:
                break
            hist = ref["target"]["history"]
            for n in hist["nodes"]:
                t = datetime.datetime.fromisoformat(n["authoredDate"].replace("Z", "+00:00"))
                hours[t.astimezone(tz).hour] += 1
            if not hist["pageInfo"]["hasNextPage"]:
                break
            after = hist["pageInfo"]["endCursor"]
    return hours


def fetch(token):
    user = gql(token, CALENDAR, {"login": USERNAME})["user"]
    weeks = user["contributionsCollection"]["contributionCalendar"]["weeks"]
    days = [
        {"date": d["date"], "count": d["contributionCount"], "level": LEVELS.get(d["contributionLevel"], 0)}
        for w in weeks for d in w["contributionDays"]
    ]
    return days, commit_hours(token, user["id"], user["repositories"]["nodes"])


# Roughly your real shape (from the old productive-time card), for offline previews.
SAMPLE_HOURS = [18, 10, 0, 0, 0, 2, 0, 0, 1, 0, 6, 8, 25, 10, 4, 13, 9, 1, 2, 7, 10, 36, 33, 39]


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
        days, hours = sample_days(), SAMPLE_HOURS
    elif token:
        days, hours = fetch(token)
    else:
        sys.exit("GITHUB_TOKEN not set (use --sample for demo data)")

    days.sort(key=lambda d: d["date"])
    out = {"user": USERNAME,
           "updated": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
           "sample": "--sample" in sys.argv,
           "tz_offset": TZ_OFFSET, "hours": hours,
           "stats": stats(days), "days": days}
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(out, f, indent=1)
    print(f"wrote {len(days)} days, total={out['stats']['total']}")


if __name__ == "__main__":
    main()
