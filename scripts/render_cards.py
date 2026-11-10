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
LINK_TEXT, LINK_URL = "github.com/miyxotkem", "https://github.com/miyxotkem"
TILES = [  # (file, label, colour key, big text, italic word, blurb)
    ("research", "RESEARCH", "tech", "UAV", "detection", "Real-time deep learning pipelines that find drones in live video."),
    ("build", "BUILD", "studio", "2", "systems", "UAV Detection Engine and the Cloud E-Learning Hub, both shipped."),
    ("learn", "LEARN", "learn", "UIT", "VNUHCM", "Software Engineering student in Ho Chi Minh City, Vietnam."),
]
FOOTER_LINKS = [("github", "https://github.com/miyxotkem"),
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
@keyframes shine{0%{transform:translateX(-200px) skewX(-18deg)}25%,100%{transform:translateX(360px) skewX(-18deg)}}
.u{opacity:0;animation:up .8s cubic-bezier(.2,.7,.2,1) both;transform-box:fill-box}
.i{opacity:0;animation:in 1s ease-out both}
.b{transform-box:fill-box;transform-origin:bottom;transform:scaleY(0);animation:bar .8s cubic-bezier(.2,.7,.2,1) both}
.d{opacity:0;transform-box:fill-box;transform-origin:center;animation:dot .4s ease-out both}
.beat{animation:beat 1.6s ease-in-out infinite}
.drop{opacity:0;transform-box:fill-box;transform-origin:50% 70%;animation:drop 1s cubic-bezier(.2,.8,.2,1) both}
.t{animation:type 1.6s steps(60) both}
.shine{transform:translateX(-200px);animation:shine 5s ease-in-out infinite both}
@media (prefers-reduced-motion: reduce){.u,.i,.b,.d,.drop,.t{animation:none!important;opacity:1!important;transform:none!important;clip-path:none!important}.beat{animation:none}.shine{display:none}}
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
def hero():
    h = 432
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
    return svg(W, h, "".join(b), ["serif", "serif-i", "sans", "mono"],
               f"{FIRST} {LAST}. {EYEBROW.title()}. {' '.join(BLURB)}")


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
    h = 244
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
    return svg(W, h, "".join(b), ["serif", "serif-i", "mono"],
               f"Contribution graph for the last 12 months, in {ACCENT_WORD}, refreshed daily")


# ---- activity ---------------------------------------------------------------
def activity(data):
    s = data["stats"]
    h = 352
    b = [card(W, h)]
    b.append(f'<text class="u" x="44" y="62" font-family="{MONO}" font-size="12" letter-spacing="1.8" '
             f'fill="{INK_SOFT}">THE LAST 12 MONTHS ON GITHUB</text>')
    b.append(f'<text class="u"{at(.1)} x="40" y="122" font-family="{SERIF}" font-size="66" letter-spacing="-1" '
             f'fill="{INK}">{s["total"]:,} <tspan font-style="italic">contributions</tspan></text>')

    months = s["monthly"]
    this_month = datetime.date.today().strftime("%Y-%m")
    full = [m["count"] for m in months if m["month"] != this_month] or [1]
    peak = max(full + [1])
    bx, bw, base, top = 44, 520, h - GAP - 44, 160
    slot = bw / max(len(months), 1)
    for i, m in enumerate(months):
        partial = m["month"] == this_month
        bh = max(4, min(1, m["count"] / peak) * (base - top))
        x = bx + i*slot + slot*0.1
        fill = GREY_BAR if partial else ACCENT if m["count"] == peak else INK
        b.append(f'<rect class="b"{at(.4 + i*.06)} x="{x:.1f}" y="{base-bh:.1f}" width="{slot*0.8:.1f}" '
                 f'height="{bh:.1f}" rx="4" fill="{fill}"><title>{m["count"]} in {m["month"]}</title></rect>')
        mon = datetime.date.fromisoformat(m["month"] + "-01").strftime("%b")
        b.append(f'<text class="i"{at(.8)} x="{x + slot*0.4:.1f}" y="{base+22}" text-anchor="middle" '
                 f'font-family="{MONO}" font-size="11" fill="{MUTED}">{mon}</text>')
        if fill == ACCENT:
            b.append(f'<text class="i"{at(1.3)} x="{x + slot*0.4:.1f}" y="{base-bh-9:.1f}" text-anchor="middle" '
                     f'font-family="{MONO}" font-size="11.5" fill="{ACCENT}">{m["count"]:,}</text>')

    # right column: three numbers with rules between them
    rx = 640
    cur, lng = s["current_streak"], s["longest_streak"]
    streak_sub = "current streak, and the longest" if cur and cur >= lng else f"current streak · longest {lng}"
    best = s["best_day"]
    rows = [
        (f'{cur} <tspan font-style="italic">{"day" if cur == 1 else "days"}</tspan>', streak_sub),
        (f'{s["active_days"]} <tspan fill="{MUTED}">/ {len(data["days"])}</tspan>', "days with a commit"),
        (f'{best["count"]}', "on the busiest day"),
    ]
    for i, (big, sub) in enumerate(rows):
        y = 112 + i*92
        b.append(f'<g class="u"{at(.5 + i*.15)}><text x="{rx}" y="{y}" font-family="{SERIF}" font-size="46" '
                 f'letter-spacing="-.5" fill="{INK}">{big}</text>'
                 f'<text x="{rx+1}" y="{y+28}" font-family="{SANS}" font-size="14.5" fill="{INK_SOFT}">'
                 f'{escape(sub)}</text></g>')
        if i < 2:
            b.append(f'<rect class="i"{at(.7 + i*.15)} x="{rx}" y="{y+52}" width="196" height="1" fill="{RULE}"/>')
    label = (f'{s["total"]:,} contributions in the last 12 months. {cur} day current streak, longest {lng}. '
             f'{s["active_days"]} of {len(data["days"])} days with a commit. {best["count"]} on the busiest day.')
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


# ---- section title + commits-by-hour card ------------------------------------
def title(text, italic, dark):
    fill = "#f0f0ee" if dark else INK
    body = (f'<text class="u" x="2" y="46" font-family="{SERIF}" font-size="36" fill="{fill}">{escape(text)} '
            f'<tspan font-style="italic">{escape(italic)}</tspan></text>')
    return svg(W, 64, body, ["serif", "serif-i"], f"{text} {italic}")


def hour_label(h):
    return f"{h % 12 or 12} {'am' if h < 12 else 'pm'}"


def hours_card(data):
    hours = data["hours"]
    tz = data.get("tz_offset", 7)
    total = sum(hours)
    h = 352
    b = [card(W, h)]
    tzs = f"UTC{'+' if tz >= 0 else '-'}{abs(tz)}"
    b.append(f'<text class="u" x="44" y="62" font-family="{MONO}" font-size="12" letter-spacing="1.8" '
             f'fill="{INK_SOFT}">COMMITS BY HOUR OF DAY · {tzs}</text>')

    groups = {"night": [22, 23, 0, 1, 2, 3, 4], "morning": [5, 6, 7, 8, 9, 10, 11],
              "day": [12, 13, 14, 15, 16, 17], "evening": [18, 19, 20, 21]}
    names = {"night": ("Mostly a", "night owl"), "morning": ("Mostly an", "early bird"),
             "day": ("Mostly a", "daytime coder"), "evening": ("Mostly an", "evening coder")}
    top = max(groups, key=lambda g: sum(hours[x] for x in groups[g]))
    lead, word = names[top] if total else ("Waiting for", "commits")
    b.append(f'<text class="u"{at(.1)} x="40" y="122" font-family="{SERIF}" font-size="66" letter-spacing="-1" '
             f'fill="{INK}">{lead} <tspan font-style="italic" fill="{ACCENT}">{word}</tspan></text>')

    peak_h = max(range(24), key=lambda x: hours[x])
    peak = max(hours + [1])
    bx, bw, base, ceil = 44, 548, h - GAP - 44, 160
    slot = bw / 24
    # soft band behind the night hours (10 pm to 5 am)
    for x0, x1 in ((0, 5), (22, 24)):
        b.append(f'<rect class="i" x="{bx + x0*slot:.1f}" y="{ceil-6}" width="{(x1-x0)*slot:.1f}" '
                 f'height="{base-ceil+6}" fill="{EMPTY}" opacity=".55"/>')
    b.append(f'<text class="i"{at(.3)} x="{bx + 2.5*slot:.1f}" y="{ceil+8}" text-anchor="middle" '
             f'font-family="{MONO}" font-size="10" letter-spacing="1.5" fill="{MUTED}">NIGHT</text>')
    for i, c in enumerate(hours):
        bh = max(3, c / peak * (base - ceil - 22))
        x = bx + i*slot + slot*0.12
        fill = ACCENT if i == peak_h and c else INK if c else GREY_BAR
        b.append(f'<rect class="b"{at(.35 + i*.035)} x="{x:.1f}" y="{base-bh:.1f}" width="{slot*0.76:.1f}" '
                 f'height="{bh:.1f}" rx="3" fill="{fill}"><title>{c} commits at {hour_label(i)}</title></rect>')
        if i == peak_h and c:
            b.append(f'<text class="i"{at(1.4)} x="{x + slot*0.38:.1f}" y="{base-bh-9:.1f}" text-anchor="middle" '
                     f'font-family="{MONO}" font-size="11.5" fill="{ACCENT}">{c}</text>')
    for i in (0, 6, 12, 18, 23):
        b.append(f'<text class="i"{at(.8)} x="{bx + i*slot + slot*0.5:.1f}" y="{base+22}" text-anchor="middle" '
                 f'font-family="{MONO}" font-size="11" fill="{MUTED}">{i:02d}</text>')

    rx = 640
    after6 = round(100 * sum(hours[18:]) / total) if total else 0
    rows = [
        (f'{hour_label(peak_h).split()[0]} <tspan font-style="italic">{hour_label(peak_h).split()[1]}</tspan>',
         "my busiest hour"),
        (f'{after6}<tspan fill="{MUTED}">%</tspan>', "of commits after 6 pm"),
        (f'{total:,}', "commits in the last year"),
    ]
    for i, (big, sub) in enumerate(rows):
        y = 112 + i*92
        b.append(f'<g class="u"{at(.5 + i*.15)}><text x="{rx}" y="{y}" font-family="{SERIF}" font-size="46" '
                 f'letter-spacing="-.5" fill="{INK}">{big}</text>'
                 f'<text x="{rx+1}" y="{y+28}" font-family="{SANS}" font-size="14.5" fill="{INK_SOFT}">'
                 f'{escape(sub)}</text></g>')
        if i < 2:
            b.append(f'<rect class="i"{at(.7 + i*.15)} x="{rx}" y="{y+52}" width="196" height="1" fill="{RULE}"/>')
    label = (f"Commits by hour of day ({tzs}): {lead} {word}. Busiest hour {hour_label(peak_h)}, "
             f"{after6}% after 6 pm, {total} commits in the last year.")
    return svg(W, h, "".join(b), ["serif", "serif-i", "sans", "mono"], label)


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
        img("heatmap.svg", f"Contribution graph, in {ACCENT_WORD}, refreshed daily") + "<br>",
        img("activity.svg", "Contributions in the last 12 months, by month, with streak and busiest day") + "<br>",
        "".join(img(f"{t[0]}.svg", f"{t[1]}: {t[3]} {t[4]}", third) for t in TILES) + "<br>",
        '<picture><source media="(prefers-color-scheme: dark)" srcset="./cards/title-code-dark.svg" />'
        + img("title-code-light.svg", "When I code") + "</picture><br>",
        img("hours.svg", "Commits by hour of day"),
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
    write("hero.svg", hero())
    write("heatmap.svg", heatmap(data))
    write("activity.svg", activity(data))
    for i, t in enumerate(TILES):
        write(f"{t[0]}.svg", tile(i, *t[1:]))
    write("title-code-light.svg", title("When I", "code", False))
    write("title-code-dark.svg", title("When I", "code", True))
    write("hours.svg", hours_card(data))
    for i, (t, _) in enumerate(FOOTER_LINKS):
        write(f"link-{t}.svg", link_svg(t, i == len(FOOTER_LINKS) - 1))
    readme_block(data)


if __name__ == "__main__":
    main()
