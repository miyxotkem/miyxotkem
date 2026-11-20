#!/usr/bin/env python3
"""
Render the profile README's animated SVG cards into cards/, and refresh the
card block in README.md.

Look: warm paper cards, ink text, one accent colour per tile, Instrument Serif
headlines with italic accents, Geist body text, Geist Mono labels.

Every card is a standalone SVG shown through <img>, so it may only use what
GitHub allows there: inline CSS animations, SMIL, and fonts embedded as data
URIs (no scripts, no external requests). Fonts in fonts/ are SIL OFL.

Live numbers come from data/contributions.json (fetch_contributions.py);
the ASCII picture comes from data/portrait.txt (make_ascii.py).

    python scripts/render_cards.py
"""
import base64
import calendar
import datetime
import json
import os
import re
import statistics
from html import escape

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DATA = os.path.join(ROOT, "data", "contributions.json")
PORTRAIT = os.path.join(ROOT, "data", "portrait.txt")
OUT = os.path.join(ROOT, "cards")
FONTS = os.path.join(ROOT, "fonts")
README = os.path.join(ROOT, "README.md")

# ---- your content (edit freely) ---------------------------------------------
FIRST, LAST = "Thinh Phat", "Ho"
EYEBROW = "SOFTWARE ENGINEERING @ UIT"
BLURB = ["I build computer vision systems that spot drones,",
         "and the .NET software that ships them."]
LINK_TEXT, LINK_URL = "thinhphatho.pages.dev", "https://thinhphatho.pages.dev/"
TILES = [  # (file, label, colour key, big text, italic word, blurb)
    ("paper", "PAPER", "learn", "ISWTA", "2026", "LogTransAD: Transformer-based log anomaly detection for cloud systems. Accepted at IEEE."),
    ("research", "RESEARCH", "tech", "UAV", "detection", "Real-time deep learning pipelines that find drones in live video."),
    ("build", "BUILD", "studio", "2", "systems", "UAV Detection Engine and the Cloud E-Learning Hub, both shipped."),
]
FOOTER_LINKS = [("portfolio", "https://thinhphatho.pages.dev/"),
                ("github", "https://github.com/miyxotkem"),
                ("facebook", "https://www.facebook.com/miyxotkem.ne"),
                ("instagram", "https://www.instagram.com/fettuccinecarbonaraghhh"),
                ("resume", "https://github.com/miyxotkem/miyxotkem/blob/main/resume.pdf"),
                ("email", "mailto:hothinhphat06@gmail.com")]

# ---- tokens -----------------------------------------------------------------
# Two palettes. Every card is drawn once per theme (name.svg, name-dark.svg) and
# the README picks one with <picture>, which follows the viewer's GitHub theme.
THEMES = {
    "light": dict(
        PAPER="#f5f3ec",       # warm paper
        EMPTY="#e6e1d6",
        INK="#141413",
        INK_SOFT="#3d3a35",
        MUTED="#75706a",
        RULE="#ddd7ca",
        GREY_BAR="#cdc6b8",
        COLORS={"tech": "#d97757", "studio": "#1f1e1d", "learn": "#e3b04b"},  # orange, ink, mustard
        TILE_INK={"tech": "#ffffff", "studio": "#ffffff", "learn": "#141413"},
        REVIEW="#ddd5c7",      # waffle: reviews in sand
        ISSUE="#9c4428",       # waffle: issues in burnt orange
        SHADES=["#e6e1d6", "#ecc9b9", "#e5ab92", "#df8f6f", "#d97757", "#a24f33"],  # heatmap, light to dark
    ),
    "dark": dict(
        PAPER="#1c1b19",       # warm charcoal, a step above GitHub's dark page
        EMPTY="#2c2a26",
        INK="#f2efe6",
        INK_SOFT="#c9c3b6",
        MUTED="#8f897e",
        RULE="#35322d",
        GREY_BAR="#4a463f",
        COLORS={"tech": "#d97757", "studio": "#f0ede4", "learn": "#e3b04b"},  # the ink tile turns to paper
        TILE_INK={"tech": "#ffffff", "studio": "#141413", "learn": "#141413"},
        REVIEW="#5c564c",
        ISSUE="#f2b59a",
        SHADES=["#2c2a26", "#55332a", "#7f4431", "#ad583b", "#d97757", "#f2a585"],  # dim to bright
    ),
}
THEME = "light"
ACCENT_WORD = "orange"


def use_theme(name):
    """Point the module-level colour tokens at one palette."""
    global THEME, ACCENT, WAFFLE_TYPES
    THEME = name
    globals().update(THEMES[name])
    ACCENT = COLORS["tech"]
    WAFFLE_TYPES = waffle_types()


W = 880
GAP = 12          # space under each card, baked in so the README stays gapless
TILE_W = W / 3

SERIF = "'Instrument Serif', Georgia, serif"
SANS = "Geist, system-ui, -apple-system, sans-serif"
MONO = "'Geist Mono', ui-monospace, SFMono-Regular, Menlo, monospace"
FONT_FILES = {
    "serif": ("Instrument Serif", "normal", 400, "instrument-serif-latin-400-normal.woff"),
    "serif-i": ("Instrument Serif", "italic", 400, "instrument-serif-latin-400-italic.woff"),
    "sans": ("Geist", "normal", 400, "geist-sans-latin-400-normal.woff"),
    "sans-b": ("Geist", "normal", 600, "geist-sans-latin-600-normal.woff"),
    "mono": ("Geist Mono", "normal", 400, "geist-mono-latin-400-normal.woff"),
}

CSS = """
@keyframes up{from{opacity:0;transform:translateY(14px)}to{opacity:1;transform:none}}
@keyframes in{from{opacity:0}to{opacity:1}}
@keyframes bar{from{transform:scaleY(0)}to{transform:scaleY(1)}}
@keyframes dot{0%{opacity:0;transform:scale(.4)}60%{opacity:1;transform:scale(1.12)}100%{opacity:1;transform:none}}
@keyframes beat{0%,100%{opacity:1}50%{opacity:.3}}
@keyframes drop{0%{opacity:0;transform:translateY(70px) rotate(-6deg) scale(.8)}60%{opacity:1;transform:translateY(-6px) rotate(1.5deg)}100%{opacity:1;transform:none}}
@keyframes type{from{clip-path:inset(0 100% 0 0)}to{clip-path:inset(0 0 0 0)}}
@keyframes draw{from{stroke-dashoffset:1}to{stroke-dashoffset:0}}
@keyframes shine{0%{transform:translateX(-200px) skewX(-18deg)}25%,100%{transform:translateX(360px) skewX(-18deg)}}
.u{opacity:0;animation:up .8s cubic-bezier(.2,.7,.2,1) both;transform-box:fill-box}
.i{opacity:0;animation:in 1s ease-out both}
.b{transform-box:fill-box;transform-origin:bottom;transform:scaleY(0);animation:bar .8s cubic-bezier(.2,.7,.2,1) both}
.d{opacity:0;transform-box:fill-box;transform-origin:center;animation:dot .4s ease-out both}
.beat{animation:beat 1.6s ease-in-out infinite}
.drop{opacity:0;transform-box:fill-box;transform-origin:50% 70%;animation:drop 1s cubic-bezier(.2,.8,.2,1) both}
.t{animation:type 1.6s steps(60) both}
.draw{stroke-dasharray:1;stroke-dashoffset:1;animation:draw 1.4s cubic-bezier(.4,0,.2,1) both}
.shine{transform:translateX(-200px);animation:shine 5s ease-in-out infinite both}
@media (prefers-reduced-motion: reduce){.u,.i,.b,.d,.drop,.t,.draw{animation:none!important;opacity:1!important;transform:none!important;clip-path:none!important;stroke-dashoffset:0!important}.beat{animation:none}.shine{display:none}}
"""

_font_cache = {}


def font_css(keys):
    out = []
    for k in keys:
        fam, style, weight, fn = FONT_FILES[k]
        if fn not in _font_cache:
            with open(os.path.join(FONTS, fn), "rb") as f:
                _font_cache[fn] = base64.b64encode(f.read()).decode()
        out.append(f"@font-face{{font-family:'{fam}';font-style:{style};font-weight:{weight};"
                   f"src:url(data:font/woff;base64,{_font_cache[fn]}) format('woff')}}")
    return "".join(out)


def svg(w, h, body, fonts, label):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:.3f}" height="{h}" viewBox="0 0 {w:.3f} {h}" '
            f'role="img" aria-label="{escape(label)}"><title>{escape(label)}</title>'
            f"<style>{font_css(fonts)}{CSS}</style>{body}</svg>")


def write(name, content):
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, name), "w") as f:
        f.write(content)
    print(f"wrote cards/{name} ({len(content)//1024} KB)")


def at(s):
    return f' style="animation-delay:{s:.2f}s"'


def wrap(text, n):
    lines, cur = [], ""
    for w in text.split():
        if cur and len(cur) + 1 + len(w) > n:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    return lines + ([cur] if cur else [])


def card(w, h, fill=None):
    return f'<rect width="{w:.3f}" height="{h - GAP}" rx="14" fill="{fill or PAPER}"/>'


def eyebrow(x, y, text, color=None, delay=0):
    color = color or ACCENT
    return (f'<g class="u"{at(delay)}><rect x="{x}" y="{y-9}" width="8" height="8" rx="1.5" fill="{color}"/>'
            f'<text x="{x+18}" y="{y}" font-family="{MONO}" font-size="12" letter-spacing="1.8" fill="{INK_SOFT}">'
            f"{escape(text)}</text></g>")


# ---- hero -------------------------------------------------------------------
def hero(data):
    h = 486
    b = [card(W, h)]
    b.append(eyebrow(48, 64, EYEBROW))
    b.append(f'<text class="u"{at(.15)} x="44" y="190" font-family="{SERIF}" font-size="104" '
             f'letter-spacing="-2" fill="{INK}">{escape(FIRST)}</text>')
    b.append(f'<text class="u"{at(.3)} x="52" y="292" font-family="{SERIF}" font-style="italic" font-size="116" '
             f'letter-spacing="-2" fill="{INK}">{escape(LAST)}</text>')
    for i, ln in enumerate(BLURB):
        b.append(f'<text class="u"{at(.5 + i*.08)} x="50" y="{336 + i*27}" font-family="{SANS}" font-size="18" '
                 f'fill="{INK_SOFT}">{escape(ln)}</text>')
    b.append(f'<g class="u"{at(.75)}><text x="50" y="{394}" font-family="{MONO}" font-size="13.5" fill="{INK}">'
             f'{escape(LINK_TEXT)}</text><text x="{50 + len(LINK_TEXT)*8.2 + 16}" y="394" font-family="{SANS}" '
             f'font-size="15" fill="{ACCENT}">↗</text></g>')

    # ASCII picture, typed in line by line on the right
    if os.path.exists(PORTRAIT):
        rows = open(PORTRAIT).read().rstrip("\n").split("\n")
        cols = max(len(r) for r in rows)
        box_x, box_w, box_top, box_h = 470, 386, 36, 360
        fs = min(box_w / (cols * 0.6), box_h / (len(rows) * 1.12))
        lh = fs * 1.12
        y0 = box_top + (box_h - lh * len(rows)) / 2 + fs
        x0 = box_x + (box_w - cols * fs * 0.6) / 2
        b.append(f'<g font-family="{MONO}" font-size="{fs:.2f}" fill="{INK}">')
        cw = fs * 0.6
        for i, r in enumerate(rows):
            # Position each run of non-space characters exactly, so spacing never collapses.
            for m in re.finditer(r"\S+(?: \S+)*", r):
                run = m.group(0)
                b.append(f'<text class="t"{at(.4 + i*.035)} x="{x0 + m.start()*cw:.1f}" y="{y0 + i*lh:.1f}" '
                         f'textLength="{len(run)*cw:.1f}" lengthAdjust="spacingAndGlyphs" '
                         f'xml:space="preserve">{escape(run)}</text>')
        b.append("</g>")
    status, status_label = status_row(data, h)
    b += status
    return svg(W, h, "".join(b), ["serif", "serif-i", "sans", "mono"],
               f"{FIRST} {LAST}. {EYEBROW.title()}. {' '.join(BLURB)} {status_label}")


KIND_WORD = {"commit": "commit", "pr": "pull request", "review": "review",
             "issue": "issue", "repo": "new repo"}


def status_row(data, h):
    """The hero's last line: the latest contribution of any kind, and the streak."""
    y = h - GAP - 34
    b = [f'<rect class="i"{at(.9)} x="48" y="{y-30}" width="{W-96}" height="1" fill="{RULE}"/>']
    latest = data.get("latest")
    label = ""
    if latest:
        tz = datetime.timezone(datetime.timedelta(hours=data.get("tz_offset", 7)))
        t = datetime.datetime.fromisoformat(latest["at"].replace("Z", "+00:00"))
        upd = datetime.datetime.strptime(data["updated"], "%Y-%m-%d %H:%M UTC").replace(tzinfo=datetime.timezone.utc)
        fresh = upd - t < datetime.timedelta(hours=24)
        lt = t.astimezone(tz)
        when = f"{lt.strftime('%a %-d %b')}, {lt.strftime('%-I:%M')} {'am' if lt.hour < 12 else 'pm'}"
        what = KIND_WORD.get(latest.get("kind", "commit"), "contribution")
        where = latest["repo"] or "a private repo"
        b.append(f'<circle class="{"beat" if fresh else ""}" cx="56" cy="{y-5}" r="5" fill="{"#3fb950" if fresh else GREY_BAR}"/>')
        b.append(f'<text class="u"{at(1)} x="72" y="{y}" font-family="{SANS}" font-size="15" fill="{INK}">'
                 f'{"Shipping lately" if fresh else "Last seen"} <tspan fill="{MUTED}">·</tspan> '
                 f'<tspan fill="{INK_SOFT}">last {what} {escape(when)} in </tspan>'
                 f'<tspan font-family="{MONO}" font-size="13" fill="{INK}">{escape(where)}</tspan></text>')
        label = f"Last {what} {when} in {where}."
    cur = data["stats"]["current_streak"]
    if cur:
        b.append(f'<text class="u"{at(1.1)} x="{W-48}" y="{y}" text-anchor="end" font-family="{MONO}" font-size="12" '
                 f'letter-spacing="1.5" fill="{ACCENT}">{cur}-DAY STREAK</text>')
        label += f" {cur}-day streak."
    return b, label


# ---- heatmap ----------------------------------------------------------------
def level_of(count, cuts):
    if count == 0:
        return 0
    for i, c in enumerate(cuts):
        if count <= c:
            return i + 1
    return 5


def year_days(data):
    """This calendar year, 1 January to 31 December: the days so far with their
    counts, then the days still to come with a count of None."""
    known = {d["date"]: d["count"] for d in data["days"]}
    today = datetime.date.fromisoformat(data["days"][-1]["date"])
    day = datetime.date(today.year, 1, 1)
    out = []
    while day.year == today.year:
        out.append({"date": day.isoformat(), "count": known.get(day.isoformat(), 0) if day <= today else None})
        day += datetime.timedelta(days=1)
    return out, today


def heatmap(data):
    days, today = year_days(data)
    past = [d for d in days if d["count"] is not None]
    h = 356
    b = [card(W, h)]
    b.append(f'<text class="u" x="48" y="72" font-family="{SERIF}" font-size="40" fill="{INK}">Every day, '
             f'<tspan font-style="italic" fill="{ACCENT}">in {ACCENT_WORD}</tspan></text>')

    nz = sorted(d["count"] for d in past if d["count"])
    cuts = [nz[int(len(nz) * q)] for q in (.2, .45, .7, .9)] if nz else [1, 2, 3, 4]

    off = (datetime.date(today.year, 1, 1).weekday() + 1) % 7  # rows run Sunday to Saturday
    ncols = (len(days) + off + 6) // 7
    x0, y0 = 48, 96
    step = (W - 96) / ncols
    cell = step * 0.82
    for i, d in enumerate(days):
        col, row = divmod(i + off, 7)
        x, y = x0 + col*step, y0 + row*step
        if d["count"] is None:  # still to come: an outline, so December has its place
            b.append(f'<rect class="i"{at(.9)} x="{x+.5:.1f}" y="{y+.5:.1f}" width="{cell-1:.1f}" height="{cell-1:.1f}" '
                     f'rx="3" fill="none" stroke="{EMPTY}" stroke-width="1"/>')
            continue
        lv = level_of(d["count"], cuts)
        b.append(f'<rect class="d"{at(.25 + col*.018 + row*.012)} x="{x:.1f}" y="{y:.1f}" width="{cell:.1f}" '
                 f'height="{cell:.1f}" rx="3" fill="{SHADES[lv]}"><title>{d["count"]} on {d["date"]}</title></rect>')
    # a month label over the column holding each month's first day
    for m in range(1, 13):
        first = datetime.date(today.year, m, 1)
        col = ((first - datetime.date(today.year, 1, 1)).days + off) // 7
        b.append(f'<text class="i"{at(1)} x="{x0 + col*step:.1f}" y="{y0 + 7*step + 18:.1f}" font-family="{MONO}" '
                 f'font-size="11" fill="{ACCENT if m == today.month else MUTED}">{first.strftime("%b")}</text>')
    # the legend sits top right, in line with the title
    lx = W - 48 - 6*14 - 34
    b.append(f'<g class="i"{at(.2)}><text x="{lx-8}" y="68" text-anchor="end" font-family="{MONO}" '
             f'font-size="11" fill="{MUTED}">less</text>')
    for i, c in enumerate(SHADES):
        b.append(f'<rect x="{lx + i*14}" y="59" width="10" height="10" rx="2" fill="{c}"/>')
    b.append(f'<text x="{lx + 6*14 + 2}" y="68" font-family="{MONO}" font-size="11" fill="{MUTED}">more</text></g>')

    # the year in four numbers, under the grid
    total = sum(d["count"] for d in past)
    active = sum(1 for d in past if d["count"])
    best = max(past, key=lambda d: d["count"])
    best_when = datetime.date.fromisoformat(best["date"]).strftime("%-d %b")
    lng = run = 0
    for d in past:
        run = run + 1 if d["count"] else 0
        lng = max(lng, run)
    cur = data["stats"]["current_streak"]
    stats_row = [(f'{total:,}', f"contributions in {today.year}"),
                 (f'{active}<tspan fill="{MUTED}" font-size="26"> / {len(past)}</tspan>', "days with a contribution"),
                 (f'{best["count"]}', f"on the busiest day, {best_when}"),
                 (f'{lng}<tspan font-style="italic" font-size="30"> {"day" if lng == 1 else "days"}</tspan>',
                  "longest streak" + (", still going" if cur and cur >= lng else ""))]
    ry = y0 + 7*step + 44
    b.append(f'<rect class="i"{at(1.1)} x="48" y="{ry:.1f}" width="{W-96}" height="1" fill="{RULE}"/>')
    cw = (W - 96) / 4
    for i, (big, sub) in enumerate(stats_row):
        x = 48 + i*cw
        b.append(f'<g class="u"{at(1.2 + i*.1)}><text x="{x:.1f}" y="{ry + 52:.1f}" font-family="{SERIF}" font-size="40" '
                 f'letter-spacing="-.5" fill="{INK}">{big}</text><text x="{x+1:.1f}" y="{ry + 74:.1f}" '
                 f'font-family="{SANS}" font-size="13.5" fill="{INK_SOFT}">{escape(sub)}</text></g>')
    label = (f"Contribution graph for {today.year}, January to December, in {ACCENT_WORD}. "
             f"{total:,} contributions, {active} of {len(past)} days so far with a contribution, "
             f"{best['count']} on the busiest day ({best_when}), longest streak {lng} days.")
    return svg(W, h, "".join(b), ["serif", "serif-i", "sans", "mono"], label)

# ---- this month ---------------------------------------------------------------
MONTH_KINDS = [("commits", "commit", "commits"), ("pull_requests", "pull request", "pull requests"),
               ("reviews", "review", "reviews"), ("issues", "issue", "issues"),
               ("repos", "new repo", "new repos"), ("other", "other", "other")]


def month_card(data):
    import calendar
    days = data["days"]
    ref = datetime.date.fromisoformat(days[-1]["date"])
    ym = ref.strftime("%Y-%m")
    mdays = {d["date"]: d["count"] for d in days if d["date"].startswith(ym)}
    total = sum(mdays.values())
    ndays = calendar.monthrange(ref.year, ref.month)[1]
    mname = ref.strftime("%B")
    m = data.get("month") or {}
    counts = dict(m["counts"]) if m.get("month") == ym else None
    prev = dict((m.get("prev") or {}).get("counts") or {}) if counts else None
    pname = datetime.date.fromisoformat(m["prev"]["month"] + "-01").strftime("%b") if prev else ""
    monthly = {x["month"]: x["count"] for x in data["stats"]["monthly"]}

    def with_other(c, cal_total):
        # The calendar total is the one every card shows; whatever GitHub
        # doesn't break down by type (private repos it hides, or anything the
        # five types miss) goes in "other", so the columns always add up to it.
        known = sum(c.get(k, 0) for k, _, _ in MONTH_KINDS[:5])
        c["other"] = max(0, (cal_total if cal_total is not None else known) - known)
        return c
    if counts:
        counts = with_other(counts, total)
    if prev:
        prev = with_other(prev, monthly.get(m["prev"]["month"]))

    h = 272
    b = [card(W, h)]
    b.append(f'<text class="u" x="44" y="62" font-family="{MONO}" font-size="12" letter-spacing="1.8" '
             f'fill="{INK_SOFT}">CONTRIBUTIONS THIS MONTH</text>')
    b.append(f'<text class="u"{at(.05)} x="{W-44}" y="62" text-anchor="end" font-family="{MONO}" font-size="12" '
             f'letter-spacing="1.8" fill="{MUTED}">DAY {ref.day} OF {ndays}</text>')
    b.append(f'<text class="u"{at(.1)} x="40" y="122" font-family="{SERIF}" font-size="66" letter-spacing="-1" '
             f'fill="{INK}">{total:,} <tspan font-style="italic" fill="{ACCENT}">in {mname}</tspan></text>')
    prev_total = next((x["count"] for x in data["stats"]["monthly"]
                       if x["month"] == (ref.replace(day=1) - datetime.timedelta(days=1)).strftime("%Y-%m")), None)
    if prev_total is not None:
        pm = (ref.replace(day=1) - datetime.timedelta(days=1)).strftime("%B")
        b.append(f'<text class="u"{at(.2)} x="{W-44}" y="116" text-anchor="end" font-family="{SANS}" '
                 f'font-size="14.5" fill="{INK_SOFT}">{prev_total:,} in all of {pm}</text>')

    # one bar per day of the month; days still to come are faint stubs
    bx, bw, base, ceil = 44, W - 88, 226, 164
    slot = bw / ndays
    peak_day = max(mdays, key=lambda k: mdays[k]) if total else None
    peak = max(list(mdays.values()) + [1])
    for i in range(ndays):
        date = f"{ym}-{i+1:02d}"
        x = bx + i*slot + slot*0.15
        if date not in mdays:
            b.append(f'<rect class="i"{at(.4 + i*.02)} x="{x:.1f}" y="{base-3}" width="{slot*0.7:.1f}" height="3" '
                     f'rx="1.5" fill="{EMPTY}"/>')
            continue
        c = mdays[date]
        bh = max(3, c / peak * (base - ceil))
        fill = ACCENT if date == peak_day else INK if c else GREY_BAR
        b.append(f'<rect class="b"{at(.4 + i*.02)} x="{x:.1f}" y="{base-bh:.1f}" width="{slot*0.7:.1f}" '
                 f'height="{bh:.1f}" rx="2.5" fill="{fill}"><title>{c} on {date}</title></rect>')
        if date == peak_day:
            b.append(f'<text class="i"{at(1.2)} x="{x + slot*0.35:.1f}" y="{base-bh-8:.1f}" text-anchor="middle" '
                     f'font-family="{MONO}" font-size="11.5" fill="{ACCENT}">{c}</text>')
    for d in sorted({1, 10, 20, ndays}):
        b.append(f'<text class="i"{at(.8)} x="{bx + (d-1)*slot + slot*0.5:.1f}" y="{base+20}" text-anchor="middle" '
                 f'font-family="{MONO}" font-size="11" fill="{MUTED}">{d}</text>')
    # the breakdown by type lives in the waffle card right below

    label = f"{total} contributions in {mname} so far (day {ref.day} of {ndays})."
    return svg(W, h, "".join(b), ["serif", "serif-i", "sans", "mono"], label)


# ---- this month, one square per contribution --------------------------------------
# Commits carry the accent orange; the other kinds use the rest of the brand
# colours, and new repos are yellow stars so they read by shape too.
def waffle_types():
    return {"commit": ("commit", "commits", ACCENT, "commits"),
            "pr": ("pull request", "pull requests", INK, "pull_requests"),
            "review": ("review", "reviews", REVIEW, "reviews"),
            "issue": ("issue", "issues", ISSUE, "issues"),
            "repo": ("new repo", "new repos", COLORS["learn"], "repos"),  # drawn as a star
            "other": ("other", "other", "none", None)}  # drawn as an outline: time unknown


def star(cx, cy, r, fill, extra=""):
    """A five-pointed star centred on (cx, cy) with outer radius r."""
    import math
    pts = []
    for i in range(10):
        rad = r if i % 2 == 0 else r * 0.45
        a = -math.pi / 2 + i * math.pi / 5
        pts.append(f"{cx + rad*math.cos(a):.1f},{cy + rad*math.sin(a):.1f}")
    return f'<polygon points="{" ".join(pts)}" fill="{fill}" stroke-linejoin="round"{extra}/>'


def waffle_card(data):
    """This month as one square per contribution, coloured by type, in the order
    they happened (top to bottom, then left to right)."""
    days = data["days"]
    ref = datetime.date.fromisoformat(days[-1]["date"])
    ym = ref.strftime("%Y-%m")
    total = sum(d["count"] for d in days if d["date"].startswith(ym))
    ev = [e for e in data.get("month_events") or [] if e[0][:7] == ym or True]
    ev = ev[:total] + [[None, "other"]] * max(0, total - len(ev))  # counted by GitHub, time unknown
    tz = datetime.timezone(datetime.timedelta(hours=data.get("tz_offset", 7)))
    m = data.get("month") or {}
    prev = (m.get("prev") or {}).get("counts") if m.get("month") == ym else None
    pname = datetime.date.fromisoformat(m["prev"]["month"] + "-01").strftime("%b") if prev else ""

    h = 360
    b = [card(W, h)]
    b.append(f'<text class="u" x="44" y="62" font-family="{MONO}" font-size="12" letter-spacing="1.8" '
             f'fill="{INK_SOFT}">ONE SQUARE PER CONTRIBUTION, IN ORDER</text>')
    rows, x0, y0 = 7, 44, 88
    cols = max(1, (len(ev) + rows - 1) // rows)
    pitch = min(19, (W - 88) / cols)
    sz = pitch * 0.8
    last_day = None
    for i, (st, k) in enumerate(ev):
        c, r = divmod(i, rows)
        x, y = x0 + c*pitch, y0 + r*pitch
        one = WAFFLE_TYPES[k][0]
        tip = one
        if st:
            lt = datetime.datetime.fromisoformat(st.replace("Z", "+00:00")).astimezone(tz)
            tip += f" · {lt.strftime('%-d %b, %H:%M')}"
            if lt.day != last_day:
                if last_day is None or lt.day % 5 == 0:
                    b.append(f'<rect class="i"{at(.8)} x="{x:.1f}" y="{y0 + rows*pitch + 2:.1f}" width="1" height="8" '
                             f'fill="{MUTED}"/><text class="i"{at(.8)} x="{x+3:.1f}" y="{y0 + rows*pitch + 20:.1f}" '
                             f'font-family="{MONO}" font-size="10.5" fill="{MUTED}">{lt.day}</text>')
                last_day = lt.day
        if k == "repo":  # new repos are stars
            b.append(f'<g class="d"{at(.1 + c*.025)}><title>{escape(tip)}</title>'
                     f'{star(x + sz/2, y + sz/2 + .6, sz*0.62, WAFFLE_TYPES[k][2])}</g>')
            continue
        outline = f' stroke="{GREY_BAR}" stroke-dasharray="2 2"' if k == "other" else ""
        b.append(f'<rect class="d"{at(.1 + c*.025)} x="{x:.1f}" y="{y:.1f}" width="{sz:.1f}" height="{sz:.1f}" '
                 f'rx="3" fill="{WAFFLE_TYPES[k][2]}"{outline}><title>{escape(tip)}</title></rect>')
    if not ev:
        b.append(f'<text x="44" y="150" font-family="{SERIF}" font-style="italic" font-size="36" fill="{MUTED}">'
                 f'Nothing yet this month</text>')

    counts = {}
    for _, k in ev:
        counts[k] = counts.get(k, 0) + 1
    keys = [k for k in WAFFLE_TYPES if counts.get(k)]
    colw = (W - 88) / max(1, len(keys))
    yl = h - GAP - 64
    for i, k in enumerate(keys):
        one, many, col, field = WAFFLE_TYPES[k]
        n = counts[k]
        cx = 44 + i*colw
        swatch = f' stroke="{GREY_BAR}" stroke-dasharray="2 2"' if k == "other" else ""
        mark = (star(cx + 5, yl - 4.5, 7, col) if k == "repo" else
                f'<rect x="{cx:.1f}" y="{yl-10}" width="10" height="10" rx="2" fill="{col}"{swatch}/>')
        b.append(f'<g class="u"{at(.8 + i*.08)}>{mark}'
                 f'<text x="{cx+18:.1f}" y="{yl}" font-family="{SANS}" font-size="14.5" fill="{INK_SOFT}">'
                 f'{escape(one if n == 1 else many)}</text>'
                 f'<text x="{cx:.1f}" y="{yl+34}" font-family="{SERIF}" font-size="32" fill="{INK}">{n:,}</text>')
        if prev is not None and field:
            p = prev.get(field, 0)
            up = n > p
            b.append(f'<text x="{cx + 14 + len(f"{n:,}")*15:.1f}" y="{yl+33}" font-family="{MONO}" font-size="11" '
                     f'fill="{ACCENT if up else MUTED}">{"↑ " if up else ""}{pname} {p:,}</text>')
        b.append("</g>")
    label = (f"This month, one square per contribution in the order they happened: "
             + ", ".join(f"{counts[k]} {WAFFLE_TYPES[k][0] if counts[k] == 1 else WAFFLE_TYPES[k][1]}" for k in keys) + ".")
    return svg(W, h, "".join(b), ["serif", "serif-i", "sans", "mono"], label)


# ---- the rise: month by month, with the running total -------------------------
# Monthly bars (the quiet months grey, the months since the turn in orange, a
# dashed line for the usual month) under the running
# total as a share of the year, which turns orange where most of the year began.
def rise_card(data):
    # The bars run January to December of this year, with the months to come left
    # empty. "Usual" and "last month" look back over the 11 months before this
    # one, so they still mean something in January.
    ref = datetime.date.fromisoformat(data["days"][-1]["date"])
    counts = [0] * ref.month
    for d in data["days"]:
        if d["date"][:4] == str(ref.year):
            counts[int(d["date"][5:7]) - 1] += d["count"]
    year = sum(counts) or 1
    recent = [m["count"] for m in data["stats"]["monthly"][:-1]]
    cur, prev = counts[-1], recent[-1]
    usual = statistics.median(recent) or 1
    record = cur > max(recent)
    mname = ref.strftime("%B")
    pname = datetime.date.fromisoformat(data["stats"]["monthly"][-2]["month"] + "-01").strftime("%B")
    # the turn: the latest month that more than half the year came after
    turn = next(i for i in range(len(counts) - 1, -1, -1) if sum(counts[i:]) >= year * .5)
    turn_name = datetime.date(ref.year, turn + 1, 1).strftime("%B")
    since = round(100 * sum(counts[turn:]) / year)

    h = 452
    b = [card(W, h)]
    b.append(eyebrow(48, 64, f"{ref.year} MONTH BY MONTH · AND THE RUNNING TOTAL"))
    lead, ital = (f"{mname},", "my biggest yet") if record else (f"{mname} so far,", "climbing")
    b.append(f'<text class="u"{at(.1)} x="40" y="120" font-family="{SERIF}" font-size="56" letter-spacing="-1" '
             f'fill="{INK}">{lead} <tspan font-style="italic" fill="{ACCENT}">{ital}</tspan></text>')

    bx, bw, base, top = 44, 552, h - GAP - 48, 176
    slot = bw / 12
    peak = max(counts)
    Y = lambda v: base - v / peak * (base - top) * .42  # bars keep to the lower part; the line rises above them
    b.append(f'<rect x="{bx}" y="{base}" width="{bw}" height="1" fill="{RULE}"/>')
    for i, c in enumerate(counts):
        x, w = bx + i*slot + slot*.14, slot*.72
        last = i == len(counts) - 1
        fill = ACCENT if last else SHADES[2] if i >= turn else GREY_BAR
        bh = max(3, base - Y(c))
        b.append(f'<rect class="b"{at(.3 + i*.05)} x="{x:.1f}" y="{base-bh:.1f}" width="{w:.1f}" height="{bh:.1f}" '
                 f'rx="4" fill="{fill}"><title>{c} in {datetime.date(ref.year, i + 1, 1):%B}</title></rect>')
        if i >= len(counts) - 2:
            b.append(f'<text class="i"{at(1)} x="{x + w/2:.1f}" y="{base-bh+18:.1f}" text-anchor="middle" '
                     f'font-family="{MONO}" font-size="11.5" fill="{PAPER if last else INK}">{c}</text>')
        mon = datetime.date(ref.year, i + 1, 1).strftime("%b")
        b.append(f'<text class="i"{at(.8)} x="{x + w/2:.1f}" y="{base+20}" text-anchor="middle" font-family="{MONO}" '
                 f'font-size="11" fill="{ACCENT if last else MUTED}">{mon}</text>')
    for i in range(len(counts), 12):  # months still to come: an empty place on the axis
        x, w = bx + i*slot + slot*.14, slot*.72
        b.append(f'<rect class="i"{at(.9)} x="{x:.1f}" y="{base-3}" width="{w:.1f}" height="3" rx="1.5" fill="{EMPTY}"/>'
                 f'<text class="i"{at(.8)} x="{x + w/2:.1f}" y="{base+20}" text-anchor="middle" font-family="{MONO}" '
                 f'font-size="11" fill="{MUTED}" opacity=".5">{datetime.date(ref.year, i + 1, 1):%b}</text>')
    b.append(f'<path class="i"{at(1.1)} d="M{bx},{Y(usual):.1f} H{bx + turn*slot:.1f}" stroke="{MUTED}" '
             f'stroke-width="1.2" stroke-dasharray="3 4"/><text class="i"{at(1.2)} x="{bx}" y="{Y(usual)-8:.1f}" '
             f'font-family="{MONO}" font-size="10.5" fill="{MUTED}">USUAL MONTH · {usual:g}</text>')

    # the running total, as a share of the year, on its own 0-100% scale: a point at the end of each month
    ltop = top
    L = lambda share: base - share * (base - ltop)
    run, pts = 0, [(bx, base)]
    for i, c in enumerate(counts):
        run += c
        pts.append((bx + (i + 1)*slot, L(run / year)))
    fmt = lambda ps: " ".join(f"{x:.1f},{y:.1f}" for x, y in ps)
    quiet, climb = pts[:turn + 1], pts[turn:]
    b.append(f'<defs><linearGradient id="rg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{ACCENT}" '
             f'stop-opacity=".30"/><stop offset="1" stop-color="{ACCENT}" stop-opacity="0"/></linearGradient></defs>')
    b.append(f'<polygon class="i"{at(2.2)} points="{climb[0][0]:.1f},{base} {fmt(climb)} {climb[-1][0]:.1f},{base}" '
             f'fill="url(#rg)"/>')
    b.append(f'<polyline class="draw"{at(1.3)} pathLength="1" points="{fmt(quiet)}" fill="none" stroke="{INK}" '
             f'stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>')
    b.append(f'<polyline class="draw"{at(2.0)} pathLength="1" points="{fmt(climb)}" fill="none" stroke="{ACCENT}" '
             f'stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/>')
    tx, ty = pts[turn]
    before = round(100 * sum(counts[:turn]) / year)
    for (x, y), txt, anchor, dx, dy in (((tx, ty), f"{before}% by 1 {turn_name[:3]}", "end", -10, -8),
                                        (pts[-1], "100%", "end", -10, -6)):
        b.append(f'<circle class="d"{at(2.4)} cx="{x:.1f}" cy="{y:.1f}" r="5" fill="{ACCENT}" stroke="{PAPER}" '
                 f'stroke-width="2"/><text class="i"{at(2.5)} x="{x+dx:.1f}" y="{y+dy:.1f}" text-anchor="{anchor}" '
                 f'font-family="{MONO}" font-size="11" fill="{ACCENT}">{txt}</text>')
    # a tiny key for the line
    b.append(f'<g class="i"{at(2.5)}><path d="M{bx},{ltop - 18} h9" stroke="{INK}" stroke-width="2"/><path d="M{bx + 9},{ltop - 18} h9" stroke="{ACCENT}" stroke-width="2.5"/>'
             f'<text x="{bx + 24}" y="{ltop - 14}" font-family="{MONO}" font-size="10.5" fill="{MUTED}">'
             f'RUNNING TOTAL</text></g>')

    rows = [(f'{cur/usual:.0f}<tspan font-style="italic">×</tspan>', f"my usual month ({usual:g})"),
            (f'{since}<tspan fill="{MUTED}">%</tspan>', f"of my year came since 1 {turn_name}"),
            (f'+{round(100*(cur-prev)/prev)}<tspan fill="{MUTED}">%</tspan>', f"on all of {pname}, already")]
    for i, (big, sub) in enumerate(rows):
        y = 124 + i*118
        b.append(f'<g class="u"{at(.5 + i*.15)}><text x="640" y="{y}" font-family="{SERIF}" font-size="44" '
                 f'letter-spacing="-.5" fill="{INK}">{big}</text><text x="641" y="{y+25}" font-family="{SANS}" '
                 f'font-size="14.5" fill="{INK_SOFT}">{escape(sub)}</text></g>')
        if i < 2:
            b.append(f'<rect class="i"{at(.7 + i*.15)} x="640" y="{y+60}" width="196" height="1" fill="{RULE}"/>')
    label = (f"Contributions by month, with the running total. {mname}: {cur} so far, {cur/usual:.0f} times my usual "
             f"month of {usual:g}; {since}% of the past year came since 1 {turn_name}.")
    return svg(W, h, "".join(b), ["serif", "serif-i", "sans", "mono"], label)



# ---- tiles ------------------------------------------------------------------
def tile(i, label, key, big, word, blurb):
    h = 222
    color = COLORS[key]
    ink = TILE_INK[key]
    w = TILE_W - 8
    b = [f'<g transform="translate({4 if i else 0} 0)">',
         f'<defs><clipPath id="c{i}"><rect width="{w:.3f}" height="{h-GAP}" rx="14"/></clipPath></defs>',
         f'<g class="drop"{at(.2 + i*.18)}>',
         f'<rect width="{w:.3f}" height="{h-GAP}" rx="14" fill="{color}"/>',
         f'<g clip-path="url(#c{i})"><rect class="shine" style="animation-delay:{2 + i*1.6}s" x="0" y="-20" '
         f'width="60" height="{h+40}" fill="#ffffff" opacity=".16"/></g>',
         f'<text x="24" y="40" font-family="{MONO}" font-size="12" letter-spacing="1.8" fill="{ink}" opacity=".85">'
         f'{escape(label)}</text>',
         f'<text x="22" y="112" font-family="{SERIF}" font-size="62" letter-spacing="-1" fill="{ink}">{escape(big)} '
         f'<tspan font-style="italic" font-size="34">{escape(word)}</tspan></text>']
    for j, ln in enumerate(wrap(blurb, 32)):
        b.append(f'<text x="24" y="{150 + j*20}" font-family="{SANS}" font-size="14" fill="{ink}" opacity=".88">'
                 f'{escape(ln)}</text>')
    b.append("</g></g>")
    return svg(TILE_W, h, "".join(b), ["serif", "serif-i", "sans", "mono"], f"{label}: {big} {word}. {blurb}")


# ---- when I work: weekday x hour ---------------------------------------------
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
PARTS = {"late nights": [22, 23, 0, 1, 2, 3, 4], "mornings": [5, 6, 7, 8, 9, 10, 11],
         "afternoons": [12, 13, 14, 15, 16, 17], "evenings": [18, 19, 20, 21]}


def hour_label(h):
    return f"{h % 12 or 12} {'am' if h < 12 else 'pm'}"


def week_grid(data):
    """7 x 24 counts (Monday first, local hours) and the span they cover.
    The year's grid comes from the fetch script; until it has run once, the
    card falls back to this month's timed contributions."""
    if data.get("week_hours"):
        return data["week_hours"], "PAST YEAR", "in the last year"
    tz = datetime.timezone(datetime.timedelta(hours=data.get("tz_offset", 7)))
    ym = data["days"][-1]["date"][:7]
    grid = [[0] * 24 for _ in range(7)]
    for stamp, _ in data.get("month_events") or []:
        t = datetime.datetime.fromisoformat(stamp.replace("Z", "+00:00")).astimezone(tz)
        if t.strftime("%Y-%m") == ym:
            grid[t.weekday()][t.hour] += 1
    mname = datetime.date.fromisoformat(ym + "-01").strftime("%B")
    return grid, mname.upper(), f"in {mname} so far"


def week_card(data):
    grid, span_tag, span = week_grid(data)
    tz = data.get("tz_offset", 7)
    tzs = f"UTC{'+' if tz >= 0 else '-'}{abs(tz)}"
    total = sum(map(sum, grid))
    h = 400
    b = [card(W, h)]
    b.append(f'<text class="u" x="44" y="62" font-family="{MONO}" font-size="12" letter-spacing="1.8" '
             f'fill="{INK_SOFT}">WHEN I WORK · {span_tag} · {tzs}</text>')

    # the headline: weekdays or weekends (per day, so 5 vs 2 is fair), and the busiest part of the day
    wk, we = sum(sum(r) for r in grid[:5]), sum(sum(r) for r in grid[5:])
    part = max(PARTS, key=lambda p: sum(r[x] for r in grid for x in PARTS[p]) / len(PARTS[p]))  # per hour
    lean = (we / 2) / (wk / 5) if wk else 9  # per weekend day vs per weekday
    if lean > 1.2:
        phrase = f"weekend {part}"
    elif lean < 1 / 1.2:
        phrase = f"{'weeknight' if part in ('evenings', 'late nights') else 'weekday'} {part}"
    else:  # close enough that neither side owns it
        phrase = f"{part}, all week"
    phrase = phrase if total else "contributions"
    lead = "Mostly" if total else "Waiting for"
    fs = min(60, 560 / (len(f"{lead} {phrase}") * 0.37))
    b.append(f'<text class="u"{at(.1)} x="40" y="122" font-family="{SERIF}" font-size="{fs:.0f}" letter-spacing="-1" '
             f'fill="{INK}">{lead} <tspan font-style="italic" fill="{ACCENT}">{phrase}</tspan></text>')

    # the grid, shaded like the heatmap, with a rule between weekdays and the weekend
    nz = sorted(c for r in grid for c in r if c)
    cuts = [nz[int(len(nz) * q)] for q in (.2, .45, .7, .9)] if nz else [1, 2, 3, 4]
    b.append(f'<text class="u"{at(.2)} x="44" y="156" font-family="{SANS}" font-size="14.5" fill="{INK_SOFT}">'
             f'Each square is an hour of the week, shaded by contributions {span}.</text>')
    gx, gy, step = 88, 184, 21.6
    cell = step * .8
    for d in range(7):
        b.append(f'<text class="i"{at(.2)} x="{gx-12}" y="{gy + d*step + cell*.75:.1f}" text-anchor="end" '
                 f'font-family="{MONO}" font-size="11" fill="{MUTED}">{WEEKDAYS[d][:3]}</text>')
        for x in range(24):
            c = grid[d][x]
            b.append(f'<rect class="d"{at(.3 + x*.025 + d*.02)} x="{gx + x*step:.1f}" y="{gy + d*step:.1f}" '
                     f'width="{cell:.1f}" height="{cell:.1f}" rx="3" fill="{SHADES[level_of(c, cuts)]}">'
                     f'<title>{c} on {WEEKDAYS[d]}s at {hour_label(x)}</title></rect>')
    b.append(f'<rect class="i"{at(.9)} x="{gx-4}" y="{gy + 5*step - step*.1:.1f}" width="{24*step:.1f}" '
             f'height="1" fill="{RULE}"/>')
    for x in (0, 6, 12, 18, 23):
        b.append(f'<text class="i"{at(.8)} x="{gx + x*step + cell/2:.1f}" y="{gy + 7*step + 16:.1f}" '
                 f'text-anchor="middle" font-family="{MONO}" font-size="11" fill="{MUTED}">{x:02d}</text>')

    # three numbers on the right, laid out like the other stat columns
    bd, bh = max(((d, x) for d in range(7) for x in range(24)), key=lambda p: grid[p[0]][p[1]])
    best_day = max(range(7), key=lambda d: sum(grid[d]))
    weekend = round(100 * we / total) if total else 0
    num, ampm = hour_label(bh).split()
    rows = [(f'{WEEKDAYS[bd][:3]} {num} <tspan font-style="italic">{ampm}</tspan>',
             f"busiest hour, {grid[bd][bh]} contributions"),
            (WEEKDAYS[best_day], "my busiest day of the week"),
            (f'{weekend}<tspan fill="{MUTED}">%</tspan>', "on weekends")]
    rx = 640
    for i, (big, sub) in enumerate(rows):
        y = 120 + i*104
        b.append(f'<g class="u"{at(.5 + i*.15)}><text x="{rx}" y="{y}" font-family="{SERIF}" font-size="44" '
                 f'letter-spacing="-.5" fill="{INK}">{big}</text><text x="{rx+1}" y="{y+25}" font-family="{SANS}" '
                 f'font-size="14.5" fill="{INK_SOFT}">{escape(sub)}</text></g>')
        if i < 2:
            b.append(f'<rect class="i"{at(.7 + i*.15)} x="{rx}" y="{y+48}" width="196" height="1" fill="{RULE}"/>')
    label = (f"When I work, by weekday and hour ({tzs}), {span}: {lead} {phrase}. "
             f"Busiest hour {WEEKDAYS[bd]} {hour_label(bh)}, busiest day {WEEKDAYS[best_day]}, "
             f"{weekend}% on weekends, {total} contributions with a known time.")
    return svg(W, h, "".join(b), ["serif", "serif-i", "sans", "mono"], label)



# ---- words from commit messages --------------------------------------------------
def words_card(data):
    words = data.get("words") or []
    h = 176
    b = [card(W, h)]
    scope = "THIS MONTH" if data.get("words_include_private") else "PUBLIC REPOS · THIS MONTH"
    b.append(f'<text class="u" x="44" y="62" font-family="{MONO}" font-size="12" letter-spacing="1.8" '
             f'fill="{INK_SOFT}">WHAT MY COMMIT MESSAGES SAY</text>')
    b.append(f'<text class="u" x="{W-44}" y="62" text-anchor="end" font-family="{MONO}" font-size="12" '
             f'letter-spacing="1.8" fill="{MUTED}">{scope}</text>')
    if not words:
        b.append(f'<text x="44" y="124" font-family="{SERIF}" font-style="italic" font-size="40" fill="{MUTED}">'
                 f'No commits yet this month</text>')
        return svg(W, h, "".join(b), ["serif-i", "mono"], "No commit messages yet this month")
    mx = words[0][1]
    x, y = 44, 124
    shown = []
    for i, (w, n) in enumerate(words):
        fs = 18 + 38 * (n / mx)
        wpx = len(w) * fs * 0.40 + 10 + len(str(n)) * 7
        if x + wpx > W - 44:
            continue  # one line only: skip a word that doesn't fit, try the next
        col = ACCENT if i == 0 else INK if n >= max(2, mx * .3) else MUTED
        style = "italic" if i % 3 == 1 else "normal"
        b.append(f'<text class="u"{at(.1 + i*.05)} x="{x:.1f}" y="{y}" font-family="{SERIF}" font-style="{style}" '
                 f'font-size="{fs:.0f}" fill="{col}">{escape(w)}<tspan font-family="{MONO}" font-size="11" '
                 f'fill="{MUTED}" dy="-{fs*.45:.0f}"> {n}</tspan></text>')
        shown.append(f"{w} ({n})")
        x += wpx + 24
    return svg(W, h, "".join(b), ["serif", "serif-i", "mono"],
               "Most used words in this month's commit messages: " + ", ".join(shown))



# ---- footer links -------------------------------------------------------------
# GitHub strips CSS from READMEs, so the links are drawn as small images in the
# accent colour (transparent background: works on light and dark GitHub alike).
def link_svg(text, last):
    fs, cw = 14, 14 * 0.6           # Geist Mono: every glyph is 0.6em wide
    w = len(text) * cw + 14 + (0 if last else 30)
    b = [f'<text x="2" y="19" font-family="{MONO}" font-size="{fs}" fill="{ACCENT}">{escape(text)}</text>',
         f'<path transform="translate({len(text)*cw + 5:.1f} 8)" d="M1 8L8 1M3 1h5v5" fill="none" '
         f'stroke="{ACCENT}" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>']
    if not last:
        b.append(f'<text x="{w - 14:.1f}" y="19" text-anchor="middle" font-family="{MONO}" font-size="{fs}" '
                 f'fill="{GREY_BAR}">/</text>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:.1f}" height="28" viewBox="0 0 {w:.1f} 28" '
            f'role="img" aria-label="{escape(text)}"><title>{escape(text)}</title>'
            f'<style>{font_css(["mono"])}</style>{"".join(b)}</svg>')


# ---- README block -------------------------------------------------------------
def card_url(name):
    """./cards/name?v=<short hash of the file>: the link changes whenever the card
    does, so GitHub and browsers fetch the new one instead of a cached copy."""
    import hashlib
    with open(os.path.join(OUT, name), "rb") as f:
        return f"./cards/{name}?v={hashlib.sha1(f.read()).hexdigest()[:8]}"


def readme_block(data):
    def img(src, alt, width="100%"):
        dark = src.replace(".svg", "-dark.svg")
        return (f'<picture><source media="(prefers-color-scheme: dark)" srcset="{card_url(dark)}" />'
                f'<img src="{card_url(src)}" width="{width}" alt="{escape(alt)}" /></picture>')
    third = "33.333%"
    lines = [
        "<!-- cards:start (generated by scripts/render_cards.py; edit the script, not this block) -->",
        '<div align="center">',
        # who I am: intro and status, then what I work on
        f'<a href="{LINK_URL}">{img("hero.svg", f"{FIRST} {LAST}. {EYEBROW.capitalize()}.")}</a><br>',
        "".join(img(f"{t[0]}.svg", f"{t[1]}: {t[3]} {t[4]}", third) for t in TILES) + "<br>",
        # the year: every day, then month by month
        img("heatmap.svg", f"Contribution graph for the year, January to December, in {ACCENT_WORD}, with the year's totals") + "<br>",
        img("rise.svg", "Contributions month by month, with the running total for the year") + "<br>",
        # this month, zooming in: day by day, when I work, by type, in words
        img("month.svg", "This month: contributions by day") + "<br>",
        img("week.svg", "When I work: contributions by weekday and hour of day") + "<br>",
        img("waffle.svg", "This month, one square per contribution, coloured by type, in order") + "<br>",
        img("words.svg", "Most used words in this month's commit messages"),
        "</div>",
        "",
        '<p align="center">',
        "".join(f'<a href="{u}"><img src="{card_url(f"link-{t}.svg")}" height="28" alt="{t}" /></a>'
                for t, u in FOOTER_LINKS),
        "</p>",
        "<!-- cards:end -->",
    ]
    block = "\n".join(lines)
    text = open(README).read()
    new = re.sub(r"<!-- cards:start.*?<!-- cards:end -->", lambda _: block, text, flags=re.S)
    if "<!-- cards:start" not in text:
        new = block + "\n\n" + text
    with open(README, "w") as f:
        f.write(new)
    print("updated README.md card block")


def main():
    with open(DATA) as f:
        data = json.load(f)
    for old in os.listdir(OUT) if os.path.isdir(OUT) else []:
        if old.endswith(".svg"):
            os.remove(os.path.join(OUT, old))
    for theme in THEMES:
        use_theme(theme)
        sfx = "" if theme == "light" else f"-{theme}"
        write(f"hero{sfx}.svg", hero(data))
        write(f"heatmap{sfx}.svg", heatmap(data))
        write(f"month{sfx}.svg", month_card(data))
        write(f"waffle{sfx}.svg", waffle_card(data))
        write(f"rise{sfx}.svg", rise_card(data))
        for i, t in enumerate(TILES):
            write(f"{t[0]}{sfx}.svg", tile(i, *t[1:]))
        write(f"week{sfx}.svg", week_card(data))
        write(f"words{sfx}.svg", words_card(data))
    # footer links have a transparent background, so one version serves both themes
    use_theme("light")
    for i, (t, _) in enumerate(FOOTER_LINKS):
        write(f"link-{t}.svg", link_svg(t, i == len(FOOTER_LINKS) - 1))
    readme_block(data)


use_theme("light")

if __name__ == "__main__":
    main()
