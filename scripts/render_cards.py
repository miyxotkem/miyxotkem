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
import datetime
import json
import os
import re
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
PAPER = "#f5f3ec"      # warm paper
EMPTY = "#e6e1d6"
INK = "#141413"
INK_SOFT = "#3d3a35"
MUTED = "#75706a"
RULE = "#ddd7ca"
GREY_BAR = "#cdc6b8"
COLORS = {"tech": "#d97757", "studio": "#1f1e1d", "learn": "#e3b04b"}  # orange, ink, mustard
ACCENT = COLORS["tech"]
ACCENT_WORD = "orange"
SHADES = [EMPTY, "#ecc9b9", "#e5ab92", "#df8f6f", "#d97757", "#a24f33"]  # heatmap, light to dark
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


def card(w, h, fill=PAPER):
    return f'<rect width="{w:.3f}" height="{h - GAP}" rx="14" fill="{fill}"/>'


def eyebrow(x, y, text, color=ACCENT, delay=0):
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


def heatmap(data):
    days = data["days"]
    s = data["stats"]
    h = 356
    b = [card(W, h)]
    b.append(f'<text class="u" x="48" y="72" font-family="{SERIF}" font-size="40" fill="{INK}">Every day, '
             f'<tspan font-style="italic" fill="{ACCENT}">in {ACCENT_WORD}</tspan></text>')
    b.append(f'<text class="u"{at(.1)} x="{W-48}" y="68" text-anchor="end" font-family="{MONO}" font-size="12" '
             f'letter-spacing="1.8" fill="{INK_SOFT}">REFRESHED DAILY</text>')

    nz = sorted(d["count"] for d in days if d["count"])
    cuts = [nz[int(len(nz) * q)] for q in (.2, .45, .7, .9)] if nz else [1, 2, 3, 4]

    first = datetime.date.fromisoformat(days[0]["date"])
    off = (first.weekday() + 1) % 7
    ncols = (len(days) + off + 6) // 7
    x0, y0 = 48, 96
    step = (W - 96) / ncols
    cell = step * 0.82
    seen = set()
    for i, d in enumerate(days):
        col, row = divmod(i + off, 7)
        x, y = x0 + col*step, y0 + row*step
        lv = level_of(d["count"], cuts)
        b.append(f'<rect class="d"{at(.25 + col*.018 + row*.012)} x="{x:.1f}" y="{y:.1f}" width="{cell:.1f}" '
                 f'height="{cell:.1f}" rx="3" fill="{SHADES[lv]}"><title>{d["count"]} on {d["date"]}</title></rect>')
        dt = datetime.date.fromisoformat(d["date"])
        if dt.day <= 7 and row == 0 and dt.month not in seen and 1 < col and x < W - 48 - 6*14 - 110:
            seen.add(dt.month)
            b.append(f'<text class="i"{at(1)} x="{x:.1f}" y="{y0 + 7*step + 18:.1f}" font-family="{MONO}" '
                     f'font-size="11" fill="{MUTED}">{dt.strftime("%b")}</text>')
    ly = y0 + 7*step + 18
    lx = W - 48 - 6*14 - 34
    b.append(f'<g class="i"{at(1.1)}><text x="{lx-8}" y="{ly:.1f}" text-anchor="end" font-family="{MONO}" '
             f'font-size="11" fill="{MUTED}">less</text>')
    for i, c in enumerate(SHADES):
        b.append(f'<rect x="{lx + i*14}" y="{ly-9:.1f}" width="10" height="10" rx="2" fill="{c}"/>')
    b.append(f'<text x="{lx + 6*14 + 2}" y="{ly:.1f}" font-family="{MONO}" font-size="11" fill="{MUTED}">more</text></g>')
    # the year in four numbers, under the grid
    best = s["best_day"]
    best_when = datetime.date.fromisoformat(best["date"]).strftime("%-d %b") if best["date"] else ""
    lng, cur = s["longest_streak"], s["current_streak"]
    stats_row = [(f'{s["total"]:,}', "contributions, last 12 months"),
                 (f'{s["active_days"]}<tspan fill="{MUTED}" font-size="26"> / {len(days)}</tspan>', "days with a contribution"),
                 (f'{best["count"]}', f"on the busiest day, {best_when}"),
                 (f'{lng}<tspan font-style="italic" font-size="30"> {"day" if lng == 1 else "days"}</tspan>',
                  "longest streak" + (", still going" if cur and cur >= lng else ""))]
    ry = ly + 26
    b.append(f'<rect class="i"{at(1.1)} x="48" y="{ry:.1f}" width="{W-96}" height="1" fill="{RULE}"/>')
    cw = (W - 96) / 4
    for i, (big, sub) in enumerate(stats_row):
        x = 48 + i*cw
        b.append(f'<g class="u"{at(1.2 + i*.1)}><text x="{x:.1f}" y="{ry + 52:.1f}" font-family="{SERIF}" font-size="40" '
                 f'letter-spacing="-.5" fill="{INK}">{big}</text><text x="{x+1:.1f}" y="{ry + 74:.1f}" '
                 f'font-family="{SANS}" font-size="13.5" fill="{INK_SOFT}">{escape(sub)}</text></g>')
    label = (f"Contribution graph for the last 12 months, in {ACCENT_WORD}, refreshed daily. "
             f"{s['total']:,} contributions, {s['active_days']} of {len(days)} days with a contribution, "
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
# colours. Checked for colour-blind separation (all pairs).
WAFFLE_TYPES = {"commit": ("commit", "commits", ACCENT, "commits"),
                "pr": ("pull request", "pull requests", INK, "pull_requests"),
                "review": ("review", "reviews", COLORS["learn"], "reviews"),
                "issue": ("issue", "issues", "#9c4428", "issues"),
                "repo": ("new repo", "new repos", "#ddd5c7", "repos"),
                "other": ("other", "other", "none", None)}  # drawn as an outline: time unknown


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
        b.append(f'<g class="u"{at(.8 + i*.08)}><rect x="{cx:.1f}" y="{yl-10}" width="10" height="10" rx="2" fill="{col}"{swatch}/>'
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


# ---- this month vs last month, as running totals ----------------------------------
def pace_card(data):
    days = data["days"]
    ref = datetime.date.fromisoformat(days[-1]["date"])
    ym = ref.strftime("%Y-%m")
    pm_date = ref.replace(day=1) - datetime.timedelta(days=1)
    pm = pm_date.strftime("%Y-%m")
    run = lambda xs: [sum(xs[:i+1]) for i in range(len(xs))]
    cur = run([d["count"] for d in days if d["date"].startswith(ym)])
    prv = run([d["count"] for d in days if d["date"].startswith(pm)])
    h = 376
    b = [card(W, h)]
    b.append(f'<text class="u" x="44" y="62" font-family="{MONO}" font-size="12" letter-spacing="1.8" '
             f'fill="{INK_SOFT}">THIS MONTH VS LAST MONTH, DAY BY DAY</text>')
    if not cur or not prv:
        return svg(W, h, "".join(b), ["mono"], "This month vs last month")
    n = len(cur)
    ahead = cur[-1] - prv[min(n, len(prv)) - 1]
    pname, cname = pm_date.strftime("%B"), ref.strftime("%b")
    word = "ahead of" if ahead >= 0 else "behind"
    b.append(f'<text class="u"{at(.1)} x="40" y="122" font-family="{SERIF}" font-size="60" letter-spacing="-1" '
             f'fill="{INK}">{abs(ahead):,} <tspan font-style="italic" fill="{ACCENT}">{word}</tspan> {pname}</text>')
    bx, bw, base, top = 96, 500, h - GAP - 52, 160
    mx = max(prv[-1], cur[-1], 1)
    # y axis: a round step so there are 3-5 gridlines, labelled on the left
    step = next(st for st in (1, 2, 5, 10, 20, 25, 50, 100, 200, 250, 500, 1000, 2000, 5000)
                if mx / st <= 4)
    top_v = -(-mx // step) * step
    X = lambda i: bx + i*bw/30
    Y = lambda v: base - v/top_v*(base-top)
    line = lambda v: "M" + " L".join(f"{X(i):.1f},{Y(c):.1f}" for i, c in enumerate(v))
    for v in range(0, top_v + 1, step):
        b.append(f'<rect class="i"{at(.2)} x="{bx}" y="{Y(v):.1f}" width="{bw}" height="1" fill="{RULE}" '
                 f'opacity="{1 if v == 0 else .6}"/><text class="i"{at(.2)} x="{bx-10}" y="{Y(v)+4:.1f}" '
                 f'text-anchor="end" font-family="{MONO}" font-size="11" fill="{MUTED}">{v:,}</text>')
    b.append(f'<text class="i"{at(.2)} transform="translate(50 {(top+base)/2:.0f}) rotate(-90)" text-anchor="middle" '
             f'font-family="{MONO}" font-size="10" letter-spacing="1.5" fill="{MUTED}">RUNNING TOTAL</text>')
    b.append(f'<text class="i"{at(.2)} x="{bx + bw/2:.0f}" y="{base+40}" text-anchor="middle" font-family="{MONO}" '
             f'font-size="10" letter-spacing="1.5" fill="{MUTED}">DAY OF THE MONTH</text>')
    # dashed, so it fades in rather than drawing (the draw animation needs a solid stroke)
    b.append(f'<path class="i"{at(.2)} d="{line(prv)}" fill="none" stroke="{MUTED}" '
             f'stroke-width="2" stroke-dasharray="5 4" opacity=".7"/>')
    b.append(f'<path class="draw"{at(.5)} pathLength="1" d="{line(cur)}" fill="none" stroke="{ACCENT}" '
             f'stroke-width="2.5" stroke-linejoin="round"/>')
    x, y = X(n-1), Y(cur[-1])
    b.append(f'<circle class="d"{at(1.5)} cx="{x:.1f}" cy="{y:.1f}" r="6" fill="{ACCENT}" stroke="{PAPER}" stroke-width="2"/>'
             f'<text class="i"{at(1.6)} x="{x-10:.1f}" y="{y-12:.1f}" text-anchor="end" font-family="{MONO}" '
             f'font-size="11.5" fill="{ACCENT}">{cname} · {cur[-1]:,}</text>')
    xp, yp = X(len(prv)-1), Y(prv[-1])
    b.append(f'<text class="i"{at(1)} x="{xp:.1f}" y="{yp-10:.1f}" text-anchor="end" font-family="{MONO}" '
             f'font-size="11.5" fill="{MUTED}">{pm_date.strftime("%b")} · {prv[-1]:,}</text>')
    for dd in (1, 10, 20, 31):
        b.append(f'<text class="i"{at(.8)} x="{X(dd-1):.1f}" y="{base+22}" text-anchor="middle" '
                 f'font-family="{MONO}" font-size="11" fill="{MUTED}">{dd}</text>')
    by_now = prv[min(n, len(prv)) - 1]
    rows = [(f'{cur[-1]:,}', f"by day {n} this month"), (f'{by_now:,}', f"by day {n} last month"),
            (f'{cur[-1]/n:.1f}', "a day on average")]
    rx = 640
    for i, (big, sub) in enumerate(rows):
        yy = 102 + i*97
        b.append(f'<g class="u"{at(.5 + i*.15)}><text x="{rx}" y="{yy}" font-family="{SERIF}" font-size="44" '
                 f'letter-spacing="-.5" fill="{INK}">{big}</text><text x="{rx+1}" y="{yy+25}" font-family="{SANS}" '
                 f'font-size="14.5" fill="{INK_SOFT}">{escape(sub)}</text></g>')
        if i < 2:
            b.append(f'<rect class="i"{at(.7 + i*.15)} x="{rx}" y="{yy+48}" width="196" height="1" fill="{RULE}"/>')
    label = (f"{abs(ahead)} contributions {word} {pname}: {cur[-1]} by day {n} this month, "
             f"{by_now} by day {n} last month, which ended at {prv[-1]}.")
    return svg(W, h, "".join(b), ["serif", "serif-i", "sans", "mono"], label)


# ---- tiles ------------------------------------------------------------------
def tile(i, label, key, big, word, blurb):
    h = 222
    color = COLORS[key]
    ink = "#ffffff" if key in ("tech", "studio") else INK
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


# ---- contributions-by-hour card ---------------------------------------------
def smooth_path(pts, floor=None):
    """Catmull-Rom curve through pts as SVG cubic beziers; control points are
    kept above floor so the curve never dips below the baseline."""
    p = f"M{pts[0][0]:.1f},{pts[0][1]:.1f}"
    for i in range(len(pts) - 1):
        p0, p1, p2, p3 = pts[max(i-1, 0)], pts[i], pts[i+1], pts[min(i+2, len(pts)-1)]
        c1 = [p1[0] + (p2[0]-p0[0])/6, p1[1] + (p2[1]-p0[1])/6]
        c2 = [p2[0] - (p3[0]-p1[0])/6, p2[1] - (p3[1]-p1[1])/6]
        if floor is not None:
            c1[1], c2[1] = min(c1[1], floor), min(c2[1], floor)
        p += f" C{c1[0]:.1f},{c1[1]:.1f} {c2[0]:.1f},{c2[1]:.1f} {p2[0]:.1f},{p2[1]:.1f}"
    return p


def hour_label(h):
    return f"{h % 12 or 12} {'am' if h < 12 else 'pm'}"


def hours_card(data, monthly=False):
    hours = data["month_hours"] if monthly else data["hours"]
    tz = data.get("tz_offset", 7)
    priv = data.get("includes_private", False)
    pub = "" if priv else "public "
    ref = datetime.date.fromisoformat(data["days"][-1]["date"])
    mname = ref.strftime("%B")
    # Bars and percentages come from contributions with a known time; the total
    # shown is the calendar's, so it matches the other cards. (GitHub counts a
    # few contributions whose time the API doesn't expose.)
    timed = sum(hours)
    if priv:
        total = (next((x["count"] for x in data["stats"]["monthly"] if x["month"] == ref.strftime("%Y-%m")), timed)
                 if monthly else data["stats"]["total"])
    else:
        total = timed
    span = f"in {mname} so far" if monthly else "in the last year"
    h = 352
    b = [card(W, h)]
    tzs = f"UTC{'+' if tz >= 0 else '-'}{abs(tz)}"
    b.append(f'<text class="u" x="44" y="62" font-family="{MONO}" font-size="12" letter-spacing="1.8" '
             f'fill="{INK_SOFT}">{pub.upper()}CONTRIBUTIONS BY HOUR OF DAY · {mname.upper() + " · " if monthly else ""}{tzs}</text>')

    groups = {"night": [22, 23, 0, 1, 2, 3, 4], "morning": [5, 6, 7, 8, 9, 10, 11],
              "day": [12, 13, 14, 15, 16, 17], "evening": [18, 19, 20, 21]}
    names = {"night": ("Mostly a", "night owl"), "morning": ("Mostly an", "early bird"),
             "day": ("Mostly a", "daytime coder"), "evening": ("Mostly an", "evening coder")}
    top = max(groups, key=lambda g: sum(hours[x] for x in groups[g]))
    lead, word = names[top] if timed else ("Waiting for", "contributions")
    b.append(f'<text class="u"{at(.1)} x="40" y="122" font-family="{SERIF}" font-size="66" letter-spacing="-1" '
             f'fill="{INK}">{lead} <tspan font-style="italic" fill="{ACCENT}">{word}</tspan></text>')

    peak_h = max(range(24), key=lambda x: hours[x])
    peak = max(hours + [1])
    bx, bw, base, ceil = 44, 548, h - GAP - 44, 160
    step = bw / 23
    # soft band behind the night hours (10 pm to 5 am)
    for x0, x1 in ((0, 5), (22, 23)):
        b.append(f'<rect class="i" x="{bx + x0*step:.1f}" y="{ceil-6}" width="{(x1-x0)*step:.1f}" '
                 f'height="{base-ceil+6}" fill="{EMPTY}" opacity=".55"/>')
    b.append(f'<text class="i"{at(.3)} x="{bx + 2.5*step:.1f}" y="{ceil+8}" text-anchor="middle" '
             f'font-family="{MONO}" font-size="10" letter-spacing="1.5" fill="{MUTED}">NIGHT</text>')
    # a smooth curve through the 24 hours, with a soft fill under it
    pts = [(bx + i*step, base - c / peak * (base - ceil - 22)) for i, c in enumerate(hours)]
    line = smooth_path(pts, floor=base)
    b.append(f'<defs><linearGradient id="hg" x1="0" y1="0" x2="0" y2="1">'
             f'<stop offset="0" stop-color="{ACCENT}" stop-opacity=".42"/>'
             f'<stop offset="1" stop-color="{ACCENT}" stop-opacity="0"/></linearGradient></defs>')
    b.append(f'<path class="i"{at(.9)} d="{line} L{pts[-1][0]:.1f},{base} L{pts[0][0]:.1f},{base}Z" fill="url(#hg)"/>')
    b.append(f'<rect x="{bx}" y="{base}" width="{bw}" height="1" fill="{RULE}"/>')
    b.append(f'<path class="draw"{at(.3)} d="{line}" pathLength="1" fill="none" stroke="{INK}" stroke-width="2" '
             f'stroke-linejoin="round" stroke-linecap="round"/>')
    for i, c in enumerate(hours):  # invisible hover targets, one per hour
        b.append(f'<rect x="{bx + (i-.5)*step:.1f}" y="{ceil}" width="{step:.1f}" height="{base-ceil}" fill="transparent">'
                 f'<title>{c} contributions at {hour_label(i)}</title></rect>')
    if hours[peak_h]:
        px, py = pts[peak_h]
        # dashed drop line from the peak to the axis, with the hour written underneath
        b.append(f'<path class="i"{at(1.3)} d="M{px:.1f},{py+7:.1f} L{px:.1f},{base}" stroke="{ACCENT}" '
                 f'stroke-width="1.5" stroke-dasharray="3 3" fill="none"/>')
        b.append(f'<text class="i"{at(1.4)} x="{px:.1f}" y="{base+22}" text-anchor="middle" font-family="{MONO}" '
                 f'font-size="11.5" fill="{ACCENT}">{hour_label(peak_h)}</text>')
        b.append(f'<circle class="d"{at(1.4)} cx="{px:.1f}" cy="{py:.1f}" r="6" fill="{ACCENT}" '
                 f'stroke="{PAPER}" stroke-width="2"/>')
        b.append(f'<text class="i"{at(1.5)} x="{px:.1f}" y="{py-14:.1f}" text-anchor="middle" '
                 f'font-family="{MONO}" font-size="11.5" fill="{ACCENT}">{hours[peak_h]}</text>')
    for i in (0, 6, 12, 18, 23):
        if hours[peak_h] and abs(i - peak_h) < 2:
            continue  # the peak's own label sits here
        b.append(f'<text class="i"{at(.8)} x="{bx + i*step:.1f}" y="{base+22}" text-anchor="middle" '
                 f'font-family="{MONO}" font-size="11" fill="{MUTED}">{i:02d}</text>')

    rx = 640
    after6 = round(100 * sum(hours[18:]) / timed) if timed else 0
    rows = [
        (f'{hour_label(peak_h).split()[0]} <tspan font-style="italic">{hour_label(peak_h).split()[1]}</tspan>',
         "my busiest hour"),
        (f'{after6}<tspan fill="{MUTED}">%</tspan>', "of contributions after 6 pm"),
        (f'{total:,}', f"in {mname} so far" if monthly else f"{pub}contributions, past year"),
    ]
    for i, (big, sub) in enumerate(rows):
        y = 102 + i*97  # number baseline; divider sits midway between rows
        b.append(f'<g class="u"{at(.5 + i*.15)}><text x="{rx}" y="{y}" font-family="{SERIF}" font-size="44" '
                 f'letter-spacing="-.5" fill="{INK}">{big}</text>'
                 f'<text x="{rx+1}" y="{y+25}" font-family="{SANS}" font-size="14.5" fill="{INK_SOFT}">'
                 f'{escape(sub)}</text></g>')
        if i < 2:
            b.append(f'<rect class="i"{at(.7 + i*.15)} x="{rx}" y="{y+48}" width="196" height="1" fill="{RULE}"/>')
    label = (f"{pub.capitalize() or 'C'}{'ontributions' if priv else 'contributions'} by hour of day ({tzs}): "
             f"{lead} {word}. Busiest hour {hour_label(peak_h)}, "
             f"{after6}% after 6 pm, {total} {pub}contributions {span}."
             + ("" if priv else " Private repos are not counted."))
    return svg(W, h, "".join(b), ["serif", "serif-i", "sans", "mono"], label)



# ---- words from commit messages --------------------------------------------------
def words_card(data):
    words = data.get("words") or []
    h = 250
    b = [card(W, h)]
    scope = "THIS MONTH" if data.get("words_include_private") else "PUBLIC REPOS · THIS MONTH"
    b.append(f'<text class="u" x="44" y="62" font-family="{MONO}" font-size="12" letter-spacing="1.8" '
             f'fill="{INK_SOFT}">WHAT MY COMMIT MESSAGES SAY</text>')
    b.append(f'<text class="u" x="{W-44}" y="62" text-anchor="end" font-family="{MONO}" font-size="12" '
             f'letter-spacing="1.8" fill="{MUTED}">{scope}</text>')
    if not words:
        b.append(f'<text x="44" y="140" font-family="{SERIF}" font-style="italic" font-size="40" fill="{MUTED}">'
                 f'No commits yet this month</text>')
        return svg(W, h, "".join(b), ["serif-i", "mono"], "No commit messages yet this month")
    mx = words[0][1]
    x, y, line = 44, 130, 0
    shown = []
    for i, (w, n) in enumerate(words):
        fs = 18 + 38 * (n / mx)
        wpx = len(w) * fs * 0.40 + 10 + len(str(n)) * 7
        if x + wpx > W - 44:
            line += 1
            x, y = 44, y + 58
            if line > 1:
                break
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
def readme_block(data):
    def img(src, alt, width="100%"):
        return f'<img src="./cards/{src}" width="{width}" alt="{escape(alt)}" />'
    third = "33.333%"
    lines = [
        "<!-- cards:start (generated by scripts/render_cards.py; edit the script, not this block) -->",
        '<div align="center">',
        f'<a href="{LINK_URL}">{img("hero.svg", f"{FIRST} {LAST}. {EYEBROW.capitalize()}.")}</a><br>',
        img("heatmap.svg", f"Contribution graph, in {ACCENT_WORD}, refreshed daily, with the year's totals") + "<br>",
        img("pace.svg", "This month vs last month, as running totals") + "<br>",
        img("month.svg", "This month: contributions by day") + "<br>",
        img("waffle.svg", "This month, one square per contribution, coloured by type, in order") + "<br>",
        img("hours.svg", "Contributions by hour of day" if data.get("includes_private")
            else "Public contributions by hour of day (private repos not counted)") + "<br>",
        img("words.svg", "Most used words in this month's commit messages") + "<br>",
        "".join(img(f"{t[0]}.svg", f"{t[1]}: {t[3]} {t[4]}", third) for t in TILES),
        "</div>",
        "",
        '<p align="center">',
        "".join(f'<a href="{u}"><img src="./cards/link-{t}.svg" height="28" alt="{t}" /></a>'
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
    write("hero.svg", hero(data))
    write("heatmap.svg", heatmap(data))
    write("month.svg", month_card(data))
    write("waffle.svg", waffle_card(data))
    write("pace.svg", pace_card(data))
    for i, t in enumerate(TILES):
        write(f"{t[0]}.svg", tile(i, *t[1:]))
    write("hours.svg", hours_card(data))
    write("words.svg", words_card(data))
    for i, (t, _) in enumerate(FOOTER_LINKS):
        write(f"link-{t}.svg", link_svg(t, i == len(FOOTER_LINKS) - 1))
    readme_block(data)


if __name__ == "__main__":
    main()
