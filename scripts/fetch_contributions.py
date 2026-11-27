#!/usr/bin/env python3
"""
Fetch the last year of daily contribution counts for the profile owner and
write data/contributions.json with the raw days plus derived stats
(total, current streak, longest streak, busiest day, monthly totals),
this month's commits / pull requests / reviews / issues / new repos (and last
month's, for comparison),
plus your contributions from the last year (commits, pull requests, issues,
reviews and new repositories) bucketed by local hour of day.

Commits are read from every branch of every repo you can reach (your own,
collaborations, organisations, forks), not only default branches; commits
GitHub's own graph leaves out are added on top of its daily counts.

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
import re
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
        repository { name owner { login } isPrivate primaryLanguage { name } }
        contributions { totalCount }
      }
    }
    repositories(first: 50, ownerAffiliations: OWNER, isFork: false,
                 orderBy: {field: PUSHED_AT, direction: DESC}) {
      nodes { name owner { login } isPrivate primaryLanguage { name } }
    }
  }
}
"""

# Every branch of a repo, newest first, each with your commits from the last year.
BRANCHES = """
query($owner: String!, $name: String!, $uid: ID!, $since: GitTimestamp!, $after: String) {
  repository(owner: $owner, name: $name) {
    isFork
    defaultBranchRef { name }
    refs(refPrefix: "refs/heads/", first: 50, after: $after,
         orderBy: {field: TAG_COMMIT_DATE, direction: DESC}) {
      pageInfo { hasNextPage endCursor }
      nodes { name
        associatedPullRequests(states: MERGED, first: 5, orderBy: {field: UPDATED_AT, direction: DESC}) {
          nodes { mergedAt }
        }
        target { ... on Commit {
        committedDate
        history(first: 100, since: $since, author: {id: $uid}) {
          pageInfo { hasNextPage endCursor }
          nodes { oid authoredDate messageHeadline }
        }
      } } }
    }
  }
}
"""

# More of one branch's history, when a branch has over 100 of your commits.
BRANCH_HISTORY = """
query($owner: String!, $name: String!, $ref: String!, $uid: ID!, $since: GitTimestamp!, $after: String) {
  repository(owner: $owner, name: $name) {
    ref(qualifiedName: $ref) { target { ... on Commit {
      history(first: 100, after: $after, since: $since, author: {id: $uid}) {
        pageInfo { hasNextPage endCursor }
        nodes { oid authoredDate messageHeadline }
      }
    } } }
  }
}
"""

# Every repo you can push to or belong to (yours, collaborations, organisations),
# most recently pushed first. Needs your own token: it asks as "viewer".
MY_REPOS = """
query($after: String) {
  viewer {
    repositories(first: 100, after: $after,
                 affiliations: [OWNER, COLLABORATOR, ORGANIZATION_MEMBER],
                 ownerAffiliations: [OWNER, COLLABORATOR, ORGANIZATION_MEMBER],
                 orderBy: {field: PUSHED_AT, direction: DESC}) {
      pageInfo { hasNextPage endCursor }
      nodes { name owner { login } isPrivate pushedAt primaryLanguage { name } }
    }
  }
}
"""

# Other people's repos you contributed to (commits, PRs, reviews).
CONTRIBUTED = """
query($login: String!) {
  user(login: $login) {
    repositoriesContributedTo(first: 100, includeUserRepositories: true,
                              contributionTypes: [COMMIT, PULL_REQUEST, PULL_REQUEST_REVIEW, REPOSITORY]) {
      nodes { name owner { login } isPrivate pushedAt primaryLanguage { name } }
    }
  }
}
"""

# Every non-commit contribution type the calendar counts carries an occurredAt
# timestamp; commits don't, so those come from each repo's git history instead.
# Where each kind of contribution keeps its repository (for the status line).
REPO = "repository { name isPrivate }"
EVENT_REPO = {"pullRequestContributions": f"pullRequest {{ {REPO} }}",
              "issueContributions": f"issue {{ {REPO} }}",
              "pullRequestReviewContributions": REPO,
              "repositoryContributions": REPO}

EVENT_KINDS = ["pullRequestContributions", "issueContributions",
               "pullRequestReviewContributions", "repositoryContributions"]

EVENTS = """
query($login: String!, $after: String, $from: DateTime, $to: DateTime) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      %s(first: 100, after: $after) {
        pageInfo { hasNextPage endCursor }
        nodes { occurredAt %s }
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


def local_time(stamp):
    t = datetime.datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    return t.astimezone(datetime.timezone(datetime.timedelta(hours=TZ_OFFSET)))


def local_hour(stamp):
    return local_time(stamp).hour


def find_repos(token, user, personal, since):
    """Every repo worth scanning: the ones GitHub credits you with, all your own,
    collaborations and organisation repos, and repos you contributed to."""
    found = [x["repository"] for x in user["contributionsCollection"]["commitContributionsByRepository"]]
    found += user["repositories"]["nodes"]
    if personal:  # viewer queries need your own token, not the Actions one
        after = None
        for _ in range(5):  # up to 500 repos, newest pushes first
            try:
                page = gql(token, MY_REPOS, {"after": after})["viewer"]["repositories"]
            except Exception as e:
                print(f"skip repo list: {e}", file=sys.stderr)
                break
            fresh = [r for r in page["nodes"] if (r.get("pushedAt") or "") >= since]
            found += fresh
            if len(fresh) < len(page["nodes"]) or not page["pageInfo"]["hasNextPage"]:
                break
            after = page["pageInfo"]["endCursor"]
        try:
            found += gql(token, CONTRIBUTED, {"login": USERNAME})["user"]["repositoriesContributedTo"]["nodes"]
        except Exception as e:
            print(f"skip contributed repos: {e}", file=sys.stderr)
    repos, seen = [], set()
    for r in found:
        key = (r["owner"]["login"].lower(), r["name"].lower())
        if key not in seen and (r.get("pushedAt") is None or r["pushedAt"] >= since):
            seen.add(key)
            repos.append(r)
    return repos


def scan_commits(token, uid, repos, since):
    """Your commits from the last year on every branch of every repo, each
    counted once. Every sighting of a commit on a branch is recorded, then:

      * on a default branch or gh-pages (not a fork): GitHub's own graph has
        it already ("counted"), so nothing is added;
      * on any ordinary branch: it is extra and added once;
      * only on branches whose pull request was merged, and written before the
        merge: a squash or rebase copy already landed where the PR went, so it
        is dropped;
      * finally, copies made by rebasing or cherry-picking (same author time and
        message, different id) collapse into one, keeping the counted copy.
    """
    seen = {}

    def add(r, nodes, kind, merged_at):
        for n in nodes:
            c = seen.setdefault(n["oid"], {"at": n["authoredDate"], "head": n.get("messageHeadline") or "",
                                           "repo": r, "kinds": set()})
            if kind == "merged-head" and merged_at and n["authoredDate"] > merged_at:
                c["kinds"].add("plain")  # committed to the branch after its PR merged
            else:
                c["kinds"].add(kind)

    for r in repos:
        owner, name = r["owner"]["login"], r["name"]
        after = None
        for _ in range(6):  # up to 300 branches per repo
            try:
                data = gql(token, BRANCHES, {"owner": owner, "name": name, "uid": uid,
                                             "since": since, "after": after})
            except Exception as e:  # an empty or inaccessible repo shouldn't sink the whole run
                print(f"skip {name}: {e}", file=sys.stderr)
                break
            repo = data.get("repository")
            if not repo:
                break
            default = (repo.get("defaultBranchRef") or {}).get("name")
            for ref in repo["refs"]["nodes"]:
                t = ref.get("target") or {}
                if "history" not in t:
                    continue
                if (t.get("committedDate") or "") < since:
                    continue  # nothing on this branch since a year ago
                merged = [p["mergedAt"] for p in (ref.get("associatedPullRequests") or {}).get("nodes", [])
                          if p.get("mergedAt")]
                if not repo["isFork"] and ref["name"] in (default, "gh-pages"):
                    kind, merged_at = "counted", None
                elif merged:
                    kind, merged_at = "merged-head", max(merged)
                else:
                    kind, merged_at = "plain", None
                hist = t["history"]
                add(r, hist["nodes"], kind, merged_at)
                cursor = hist["pageInfo"]["endCursor"] if hist["pageInfo"]["hasNextPage"] else None
                for _ in range(10):  # a long branch: page through the rest
                    if not cursor:
                        break
                    try:
                        more = gql(token, BRANCH_HISTORY, {"owner": owner, "name": name, "uid": uid,
                                                           "ref": "refs/heads/" + ref["name"],
                                                           "since": since, "after": cursor})
                        h = more["repository"]["ref"]["target"]["history"]
                    except Exception as e:
                        print(f"skip rest of {name}@{ref['name']}: {e}", file=sys.stderr)
                        break
                    add(r, h["nodes"], kind, merged_at)
                    cursor = h["pageInfo"]["endCursor"] if h["pageInfo"]["hasNextPage"] else None
            if not repo["refs"]["pageInfo"]["hasNextPage"]:
                break
            after = repo["refs"]["pageInfo"]["endCursor"]

    # decide each commit from all its sightings
    commits, dropped_merged = {}, 0
    for oid, c in seen.items():
        if "counted" in c["kinds"]:
            c["counted"] = True
        elif "plain" in c["kinds"]:
            c["counted"] = False
        else:  # only on merged PR branches: its squash/rebase copy is counted elsewhere
            dropped_merged += 1
            continue
        commits[oid] = c

    # rebased or cherry-picked copies: same author time and message, new id
    groups = {}
    for oid, c in commits.items():
        groups.setdefault((c["at"], c["head"]), []).append(oid)
    dropped_copies = 0
    for oids in groups.values():
        if len(oids) > 1:
            keep = next((o for o in oids if commits[o]["counted"]), oids[0])
            for o in oids:
                if o != keep:
                    del commits[o]
                    dropped_copies += 1
    print(f"dropped {dropped_merged} commits from merged PR branches and {dropped_copies} rebased copies",
          file=sys.stderr)
    return commits


def local_date(stamp):
    t = datetime.datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    return t.astimezone(datetime.timezone(datetime.timedelta(hours=TZ_OFFSET))).date().isoformat()


def event_hours(token, tally, window=None, found=None):
    """Add your pull requests, issues, reviews and new repos to hours."""
    for kind in EVENT_KINDS:
        after = None
        for _ in range(20):  # at most 2,000 of each kind
            try:
                data = gql(token, EVENTS % (kind, EVENT_REPO[kind]),
                           {"login": USERNAME, "after": after, **(window or {})})
            except Exception as e:
                print(f"skip {kind}: {e}", file=sys.stderr)
                break
            page = data["user"]["contributionsCollection"][kind]
            for n in page["nodes"]:
                tally(n["occurredAt"])
                if found is not None:
                    node = n.get("pullRequest") or n.get("issue") or n
                    found.append((n["occurredAt"], kind, node.get("repository") or {}))
            if not page["pageInfo"]["hasNextPage"]:
                break
            after = page["pageInfo"]["endCursor"]


def contribution_hours(token, user, personal):
    """Count your contributions from the last year by local hour of day (0-23)."""
    since = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=365)).strftime("%Y-%m-%dT%H:%M:%SZ")
    repos = find_repos(token, user, personal, since)
    hours, month_hours = [0] * 24, [0] * 24
    week_hours = [[0] * 24 for _ in range(7)]  # Monday first, by local hour
    month_start = datetime.datetime.now(datetime.timezone.utc).replace(
        day=1, hour=0, minute=0, second=0, microsecond=0)  # UTC, like the calendar

    def tally(stamp):  # every commit counts for the year; this month's also go to month_hours
        t = local_time(stamp)
        h = t.hour
        hours[h] += 1
        week_hours[t.weekday()][h] += 1
        if datetime.datetime.fromisoformat(stamp.replace("Z", "+00:00")) >= month_start:
            month_hours[h] += 1

    own_days = {}  # every contribution from the last year, by local day

    def tally_year(stamp):
        t = local_time(stamp)
        day = t.date().isoformat()
        own_days[day] = own_days.get(day, 0) + 1
        hours[t.hour] += 1
        week_hours[t.weekday()][t.hour] += 1

    def tally_month(stamp):
        month_hours[local_hour(stamp)] += 1

    scanned = scan_commits(token, user["id"], repos, since)
    commits = []  # (repo, commit) pairs, for the words and status cards
    for c in scanned.values():
        tally(c["at"])
        day = local_date(c["at"])
        own_days[day] = own_days.get(day, 0) + 1
        commits.append((c["repo"], {"authoredDate": c["at"], "messageHeadline": c["head"]}))
    # commits GitHub's graph leaves out (other branches, forks), by local day
    extra_days = {}
    for c in scanned.values():
        if not c["counted"]:
            day = local_date(c["at"])
            extra_days[day] = extra_days.get(day, 0) + 1
    print(f"scanned {len(repos)} repos: {len(scanned)} commits, "
          f"{sum(extra_days.values())} only on other branches or forks", file=sys.stderr)
    # The default (last-year) event lists can miss items, so PRs, issues,
    # reviews and new repos are fetched one calendar month at a time.
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    now = datetime.datetime.now(datetime.timezone.utc)
    start = datetime.datetime.fromisoformat(since.replace("Z", "+00:00"))
    month_found = []
    while start < now:
        nxt = (start.replace(day=1) + datetime.timedelta(days=32)).replace(
            day=1, hour=0, minute=0, second=0, microsecond=0)
        end = min(nxt, now)
        window = {"from": start.strftime(fmt), "to": (end - datetime.timedelta(seconds=1)).strftime(fmt)}
        if start >= month_start:  # this month: by hour for the month too, and keep each event
            event_hours(token, lambda st: (tally_year(st), tally_month(st)), window, month_found)
        else:
            event_hours(token, tally_year, window)
        start = end
    # every contribution this month with its time and type, oldest first (for the waffle)
    short = {"pullRequestContributions": "pr", "issueContributions": "issue",
             "pullRequestReviewContributions": "review", "repositoryContributions": "repo"}
    when = lambda st: datetime.datetime.fromisoformat(st.replace("Z", "+00:00"))
    events = [(n["authoredDate"], "commit") for _, n in commits if when(n["authoredDate"]) >= month_start]
    events += [(st, short[k]) for st, k, _ in month_found]
    events.sort(key=lambda e: when(e[0]))
    more = extras(user, commits, month_start)
    # the latest contribution of any kind; a private repo's name is never written out
    latest = [(n["authoredDate"], "commit", r) for r, n in commits]
    latest += [(st, short[k], repo) for st, k, repo in month_found]
    if latest:
        st, k, repo = max(latest, key=lambda e: when(e[0]))
        more["latest"] = {"at": st, "kind": k,
                          "repo": None if repo.get("isPrivate", True) else repo.get("name")}
    more["month_events"] = [[when(st).strftime("%Y-%m-%dT%H:%M:%SZ"), k] for st, k in events]
    more["extra_days"] = extra_days
    more["own_days"] = own_days
    month_commits = {}  # by local month, like the days
    for c in scanned.values():
        m = local_date(c["at"])[:7]
        month_commits[m] = month_commits.get(m, 0) + 1
    more["month_commits"] = month_commits
    more["own_since"] = local_date(since)
    more["week_hours"] = week_hours
    return hours, month_hours, more


# ---- words, languages and latest commit (for the words card and the hero's status line)
# Commit messages from private repos stay out of the words card unless this is
# set, because the card is public. Set WORDS_INCLUDE_PRIVATE=1 to count them.
WORDS_INCLUDE_PRIVATE = os.environ.get("WORDS_INCLUDE_PRIVATE") == "1"
STOPWORDS = set("""a an the and or but to of for in on at by with from into onto via as is are was be been
it its this that these those some more less when then than not no yes so up down out off over under
use using used new old all any each per vs my our your their i we you he she they them me us
merge merged pull request requests branch main master skip ci wip co authored signed off
và của các cho được là với khi để một những này có không từ vào ra đã sẽ thì cũng hơn nhiều sau
trước bằng lại đến như mới trong theo nên rồi thêm bị đó lúc nào gì hay vẫn chỉ đang mà về trên dưới vì
va cua cac duoc la voi khi de mot nhung nay co khong tu vao da se thi cung hon nhieu truoc bang lai den
nhu moi nen roi them bi luc nao gi van chi dang ma ve tren duoi vi
""".split())


def words_of(headline):
    out = []
    # letters in any script (so Vietnamese words stay whole), plus + # . - inside a word
    for w in re.findall(r"[^\W\d_][\w+#.\-]*", headline.lower()):
        w = w.strip(".-")
        if len(w) >= 2 and w not in STOPWORDS and not any(ch.isdigit() for ch in w):  # skip ids like se100-2026
            out.append(w)
    return out


def extras(user, commits, month_start):
    when = lambda st: datetime.datetime.fromisoformat(st.replace("Z", "+00:00"))
    # words: this month's commit headlines
    counts = {}
    for r, n in commits:
        if when(n["authoredDate"]) < month_start or (r.get("isPrivate") and not WORDS_INCLUDE_PRIVATE):
            continue
        for w in words_of(n.get("messageHeadline") or ""):
            counts[w] = counts.get(w, 0) + 1
    words = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:16]

    # languages: each repo's main language, weighted by your commits to it this year
    langs = {}
    for x in user["contributionsCollection"]["commitContributionsByRepository"]:
        lang = (x["repository"].get("primaryLanguage") or {}).get("name")
        if lang:
            langs[lang] = langs.get(lang, 0) + x["contributions"]["totalCount"]
    languages = sorted(langs.items(), key=lambda kv: -kv[1])[:6]

    # the latest commit; a private repo's name is never written out
    latest = None
    if commits:
        r, n = max(commits, key=lambda rn: when(rn[1]["authoredDate"]))
        latest = {"at": n["authoredDate"], "repo": None if r.get("isPrivate") else r["name"]}
    return {"words": words, "words_include_private": WORDS_INCLUDE_PRIVATE,
            "languages": languages, "latest": latest}


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


def fetch(token, personal=False):
    user = gql(token, CALENDAR, {"login": USERNAME})["user"]
    weeks = user["contributionsCollection"]["contributionCalendar"]["weeks"]
    days = [
        {"date": d["date"], "count": d["contributionCount"], "level": LEVELS.get(d["contributionLevel"], 0)}
        for w in weeks for d in w["contributionDays"]
    ]
    hours, month_hours, more = contribution_hours(token, user, personal)
    own, own_since = more.pop("own_days"), more.pop("own_since")
    if not personal:
        # Without your own token the scan can't see private repos, which the
        # calendar does count: keep the calendar, plus commits it leaves out.
        for d in days:
            d["count"] += more["extra_days"].get(d["date"], 0)
        return days, hours, month_hours, more
    # With your token, every day is counted here from the scan: each commit
    # once (rebased or cherry-picked copies collapse, any branch counts) plus
    # PRs, issues, reviews and new repos, by local day. GitHub's own calendar
    # keeps counting old commit ids after a branch is rebased and pushed again,
    # so a rewritten history counted twice there. Days before the scan's
    # one-year window keep the calendar's number.
    diff = 0
    for d in days:
        if d["date"] >= own_since:
            n = own.get(d["date"], 0)
            diff += d["count"] - n
            d["count"] = n
        else:
            d["count"] += more["extra_days"].get(d["date"], 0)
    # local time can already be a day past the calendar's last day
    last = datetime.date.fromisoformat(days[-1]["date"]) if days else None
    for day in sorted(own):
        if last and day > last.isoformat():
            days.append({"date": day, "count": own[day], "level": 0})
    relevel(days)
    print(f"calendar had {diff} more than the scan over the last year", file=sys.stderr)
    return days, hours, month_hours, more


def relevel(days):
    """Quartile levels (1-4) over the active days, like GitHub's graph."""
    active = sorted(d["count"] for d in days if d["count"] > 0)
    cuts = [active[len(active) * q // 4] for q in (1, 2, 3)] if active else [0, 0, 0]
    for d in days:
        c = d["count"]
        d["level"] = 0 if c == 0 else 1 + sum(c >= x for x in cuts)


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
        more = {"words": [["fix", 42], ["add", 37], ["update", 29], ["detection", 21], ["model", 18], ["refactor", 14]],
                "words_include_private": False, "languages": [["Python", 120], ["C#", 70], ["TypeScript", 30]],
                "week_hours": [[round(x * (1.3 if d < 5 else .6) / 9) for x in SAMPLE_HOURS] for d in range(7)],
                "latest": {"at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                           "repo": "sample-repo"}}
    elif token:
        days, hours, month_hours, more = fetch(token, bool(personal))
        month = month_counts(token)
        if month and personal:  # commits from the scan, so each counts once (any branch)
            for part in (month, month["prev"]):
                part["counts"]["commits"] = more["month_commits"].get(part["month"], 0)
        elif month:  # commits only on other branches or forks count too
            extra = more.get("extra_days", {})
            for part in (month, month["prev"]):
                part["counts"]["commits"] += sum(v for k, v in extra.items() if k.startswith(part["month"]))
    else:
        sys.exit("GITHUB_TOKEN not set (use --sample for demo data)")

    days.sort(key=lambda d: d["date"])
    out = {"user": USERNAME,
           "updated": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
           "sample": "--sample" in sys.argv,
           "includes_private": bool(personal) and "--sample" not in sys.argv,
           "tz_offset": TZ_OFFSET, "hours": hours, "month_hours": month_hours, "month": month,
           **more, "stats": stats(days), "days": days}
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(out, f, indent=1)
    print(f"wrote {len(days)} days, total={out['stats']['total']}")


if __name__ == "__main__":
    main()
