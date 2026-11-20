#!/usr/bin/env python3
"""
Fetch the last year of daily contribution counts for the profile owner and
write data/contributions.json with the raw days plus derived stats
(total, current streak, longest streak, busiest day, monthly totals),
this month's commits / pull requests / reviews / issues / new repos (and last
month's, for comparison),
plus your contributions from the last year (commits, pull requests, issues,
reviews and new repositories) bucketed by local hour of day.

Uses GitHub's GraphQL API with the token Actions provides (GITHUB_TOKEN).
Standard library only, so the workflow needs no pip install.

    PROFILE_TOKEN=... python scripts/fetch_contributions.py   # sees private repos too
    GITHUB_TOKEN=... python scripts/fetch_contributions.py    # public repos only
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
      commitContributionsByRepository(maxRepositories: 100) {
        repository { name owner { login } }
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
        nodes { authoredDate committedDate }
      }
    } } }
  }
}
"""

# Every non-commit contribution type the calendar counts carries an occurredAt
# timestamp; commits don't, so those come from each repo's git history instead.
EVENT_KINDS = ["pullRequestContributions", "issueContributions",
               "pullRequestReviewContributions", "repositoryContributions"]

EVENTS = """
query($login: String!, $after: String) {
  user(login: $login) {
    contributionsCollection {
      %s(first: 100, after: $after) {
        pageInfo { hasNextPage endCursor }
        nodes { occurredAt }
      }
    }
  }
}
"""

# Totals by contribution type for one window (used for this month and last).
MONTH_FIELDS = {"commits": "totalCommitContributions",
                "pull_requests": "totalPullRequestContributions",
                "reviews": "totalPullRequestReviewContributions",
                "issues": "totalIssueContributions",
                "repos": "totalRepositoryContributions",
                "private": "restrictedContributionsCount"}

MONTHS = """
query($login: String!, $f1: DateTime!, $t1: DateTime!, $f0: DateTime!, $t0: DateTime!) {
  user(login: $login) {
    now: contributionsCollection(from: $f1, to: $t1) { %s }
    prev: contributionsCollection(from: $f0, to: $t0) { %s }
  }
}
""" % ((" ".join(MONTH_FIELDS.values()),) * 2)

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


def local_hour(stamp):
    t = datetime.datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    return t.astimezone(datetime.timezone(datetime.timedelta(hours=TZ_OFFSET))).hour


def commit_hours(token, uid, repos, tally, seen_commits):
    """Add your commits from the last year to hours, by local hour of day (0-23)."""
    since = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=365)).strftime("%Y-%m-%dT%H:%M:%SZ")
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
                tally(n["authoredDate"], n)
                seen_commits.setdefault((r["owner"]["login"] + "/" + r["name"]).lower(), []).append(n)
            if not hist["pageInfo"]["hasNextPage"]:
                break
            after = hist["pageInfo"]["endCursor"]


def event_hours(token, tally, seen_events=None):
    """Add your pull requests, issues, reviews and new repos to hours."""
    for kind in EVENT_KINDS:
        after = None
        for _ in range(20):  # at most 2,000 of each kind
            try:
                data = gql(token, EVENTS % kind, {"login": USERNAME, "after": after})
            except Exception as e:
                print(f"skip {kind}: {e}", file=sys.stderr)
                break
            page = data["user"]["contributionsCollection"][kind]
            for n in page["nodes"]:
                tally(n["occurredAt"])
                if seen_events is not None:
                    seen_events.setdefault(kind, []).append(n["occurredAt"])
            if not page["pageInfo"]["hasNextPage"]:
                break
            after = page["pageInfo"]["endCursor"]


def contribution_hours(token, user):
    """Count your contributions from the last year by local hour of day (0-23)."""
    # Repos you committed to this year (including other people's), plus your own.
    repos, seen = [], set()
    by_repo = user["contributionsCollection"]["commitContributionsByRepository"]
    for r in [x["repository"] for x in by_repo] + user["repositories"]["nodes"]:
        key = (r["owner"]["login"].lower(), r["name"].lower())
        if key not in seen:
            seen.add(key)
            repos.append(r)
    hours, month_hours = [0] * 24, [0] * 24
    month_start = datetime.datetime.now(datetime.timezone.utc).replace(
        day=1, hour=0, minute=0, second=0, microsecond=0)  # UTC, like the calendar

    def tally(stamp, _=None):  # every contribution counts for the year; this month's also go to month_hours
        h = local_hour(stamp)
        hours[h] += 1
        if datetime.datetime.fromisoformat(stamp.replace("Z", "+00:00")) >= month_start:
            month_hours[h] += 1

    seen_commits = {}
    commit_hours(token, user["id"], repos, tally, seen_commits)
    seen_events = {}
    event_hours(token, tally, seen_events)
    explain_commit_gap(token, month_start, seen_commits)
    explain_event_gap(token, month_start, seen_events)
    return hours, month_hours


MONTH_COMMITS = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) { contributionsCollection(from: $from, to: $to) {
    commitContributionsByRepository(maxRepositories: 100) {
      repository { nameWithOwner } contributions { totalCount }
    }
  } }
}
"""


def explain_commit_gap(token, month_start, seen_commits):
    """Log, per repo (unnamed: this log is public), where GitHub's commit count
    for this month differs from the commits the by-hour chart found."""
    try:
        now = datetime.datetime.now(datetime.timezone.utc)
        rows = gql(token, MONTH_COMMITS, {"login": USERNAME, "from": month_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                                          "to": now.strftime("%Y-%m-%dT%H:%M:%SZ")}
                   )["user"]["contributionsCollection"]["commitContributionsByRepository"]
    except Exception as e:
        print(f"commit gap check skipped: {e}", file=sys.stderr)
        return
    when = lambda st: datetime.datetime.fromisoformat(st.replace("Z", "+00:00"))
    for i, r in enumerate(rows):
        nodes = seen_commits.get(r["repository"]["nameWithOwner"].lower())
        gh = r["contributions"]["totalCount"]
        by_author = sum(1 for n in nodes or [] if when(n["authoredDate"]) >= month_start)
        by_commit = sum(1 for n in nodes or [] if when(n["committedDate"]) >= month_start)
        if nodes is None or gh != by_author:
            print(f"commit gap: repo #{i+1}: github {gh}, chart {by_author} by author date, "
                  f"{by_commit} by commit date{'' if nodes is not None else ', repo not scanned'}")


EVENT_TOTALS = {"pullRequestContributions": "totalPullRequestContributions",
                "issueContributions": "totalIssueContributions",
                "pullRequestReviewContributions": "totalPullRequestReviewContributions",
                "repositoryContributions": "totalRepositoryContributions"}


def explain_event_gap(token, month_start, seen_events):
    """Log where GitHub's totals for this month differ from the events the chart found."""
    now = datetime.datetime.now(datetime.timezone.utc)
    q = "query($login: String!, $from: DateTime!, $to: DateTime!) { user(login: $login) { " \
        "contributionsCollection(from: $from, to: $to) { %s } } }" % " ".join(
            f"{k}(first: 100) {{ totalCount }} {v}" for k, v in EVENT_TOTALS.items())
    try:
        c = gql(token, q, {"login": USERNAME, "from": month_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                           "to": now.strftime("%Y-%m-%dT%H:%M:%SZ")})["user"]["contributionsCollection"]
    except Exception as e:
        print(f"event gap check skipped: {e}", file=sys.stderr)
        return
    when = lambda st: datetime.datetime.fromisoformat(st.replace("Z", "+00:00"))
    for kind, total in EVENT_TOTALS.items():
        chart = sum(1 for st in seen_events.get(kind, []) if when(st) >= month_start)
        allyear = len(seen_events.get(kind, []))
        print(f"event check: {kind}: total {c[total]}, list in month {c[kind]['totalCount']}, "
              f"chart {chart} (chart saw {allyear} this year)")


def month_bounds():
    """(this month, last month) as (YYYY-MM, start, end), in UTC like the
    contribution calendar, so the breakdown adds up to the calendar's days."""
    now = datetime.datetime.now(datetime.timezone.utc)
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    prev = (start - datetime.timedelta(days=1)).replace(day=1)
    iso = lambda t: t.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return ((start.strftime("%Y-%m"), iso(start), iso(now)),
            (prev.strftime("%Y-%m"), iso(prev), iso(start - datetime.timedelta(seconds=1))))


def month_counts(token):
    """Commits, PRs, reviews, issues and new repos for this month and last."""
    (m1, f1, t1), (m0, f0, t0) = month_bounds()
    try:
        u = gql(token, MONTHS, {"login": USERNAME, "f1": f1, "t1": t1, "f0": f0, "t0": t0})["user"]
    except Exception as e:  # the month card falls back to calendar totals
        print(f"skip month counts: {e}", file=sys.stderr)
        return None
    pick = lambda c: {k: c[v] for k, v in MONTH_FIELDS.items()}
    return {"month": m1, "counts": pick(u["now"]), "prev": {"month": m0, "counts": pick(u["prev"])}}


def sample_month():
    (m1, _, _), (m0, _, _) = month_bounds()
    return {"month": m1, "counts": {"commits": 212, "pull_requests": 18, "reviews": 9, "issues": 6, "repos": 3, "private": 17},
            "prev": {"month": m0, "counts": {"commits": 170, "pull_requests": 14, "reviews": 11, "issues": 4, "repos": 2, "private": 12}}}


def fetch(token):
    user = gql(token, CALENDAR, {"login": USERNAME})["user"]
    weeks = user["contributionsCollection"]["contributionCalendar"]["weeks"]
    days = [
        {"date": d["date"], "count": d["contributionCount"], "level": LEVELS.get(d["contributionLevel"], 0)}
        for w in weeks for d in w["contributionDays"]
    ]
    return (days, *contribution_hours(token, user))


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
    # PROFILE_TOKEN (your own token with repo access) also sees private repos;
    # the Actions GITHUB_TOKEN only sees public ones.
    personal = os.environ.get("PROFILE_TOKEN")
    token = personal or os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if "--sample" in sys.argv:
        days, hours, month = sample_days(), SAMPLE_HOURS, sample_month()
        month_hours = [round(x / 9) for x in SAMPLE_HOURS]
    elif token:
        days, hours, month_hours = fetch(token)
        month = month_counts(token)
    else:
        sys.exit("GITHUB_TOKEN not set (use --sample for demo data)")

    days.sort(key=lambda d: d["date"])
    out = {"user": USERNAME,
           "updated": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
           "sample": "--sample" in sys.argv,
           "includes_private": bool(personal) and "--sample" not in sys.argv,
           "tz_offset": TZ_OFFSET, "hours": hours, "month_hours": month_hours, "month": month,
           "stats": stats(days), "days": days}
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(out, f, indent=1)
    print(f"wrote {len(days)} days, total={out['stats']['total']}")


if __name__ == "__main__":
    main()
