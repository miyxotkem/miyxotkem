#!/usr/bin/env python3
"""
Render the profile README's animated SVG cards into cards/.

Theme: "MAINFRAME" - near-black panels, cyan signal colour, monospace type,
a radar that keeps sweeping for drones.

Each card is a standalone SVG shown through <img>, so it may only use what
GitHub allows there: inline CSS animation and SMIL. No scripts, no external
fonts or images. Live numbers come from data/contributions.json
(written by fetch_contributions.py).

    python scripts/render_cards.py
"""
import datetime
import json
import math
import os
from html import escape

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DATA = os.path.join(ROOT, "data", "contributions.json")
OUT = os.path.join(ROOT, "cards")

# ---- profile content (edit freely) ------------------------------------------
NAME = "THINH PHAT HO"
HANDLE = "miyxotkem"
ROLE = "Software Engineering @ UIT (VNUHCM)"
TERMINAL = [
    ("$", "./execute_profile.sh"),
    ("+", "ACCESS GRANTED. initializing developer telemetry..."),
    (">", "MISSION   software architecture x artificial intelligence"),
    (">", "RESEARCH  real-time UAV (drone) detection pipelines"),
    (">", "STACK     .NET / WPF  ·  PyTorch  ·  OpenCV  ·  AIOps"),
    (">", "RIG       Win11 + WSL2  ·  RTX / CUDA  ·  .NET 8"),
]
PROJECTS = [
    {
        "file": "project-uav",
        "code": "SYS-01",
        "title": "UAV Detection Engine",
        "kind": "Computer Vision · AIOps research",
        "blurb": "Deep learning pipeline that spots drones in live video, tuned for low latency, with AIOps monitoring on the deployed models.",
        "tags": ["PyTorch", "OpenCV", "Hugging Face"],
    },
    {
        "file": "project-elearning",
        "code": "SYS-02",
        "title": "Cloud E-Learning Hub",
        "kind": "Full-stack desktop architecture",
        "blurb": "Education management system with real-time state sync, built in C# / WPF / XAML on a Firebase cloud backend.",
        "tags": ["C#", "WPF", "Firebase"],
    },
]

# ---- tokens -----------------------------------------------------------------
BG = "#0b0f14"
PANEL = "#0f151c"
LINE = "#1d2a36"
CYAN = "#00e5ff"
BLUE = "#58a6ff"
TEXT = "#e6edf3"
MUTED = "#7d8b99"
GREEN = "#3fb950"
HEAT = ["#141c24", "#0b3d4a", "#0a6e80", "#00a9c4", "#00e5ff"]
MONO = "'JetBrains Mono','Fira Code',ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"
W = 880

CSS = f"""
text{{font-family:{MONO}}}
@keyframes fade{{from{{opacity:0}}to{{opacity:1}}}}
@keyframes rise{{from{{opacity:0;transform:translateY(10px)}}to{{opacity:1;transform:none}}}}
@keyframes pop{{0%{{opacity:0;transform:scale(.2)}}70%{{opacity:1;transform:scale(1.2)}}100%{{opacity:1;transform:none}}}}
@keyframes grow{{from{{transform:scaleY(0)}}to{{transform:scaleY(1)}}}}
@keyframes blink{{0%,49%{{opacity:1}}50%,100%{{opacity:0}}}}
@keyframes pulse{{0%,100%{{opacity:1}}50%{{opacity:.3}}}}
@keyframes scan{{0%{{transform:translateY(-40px)}}100%{{transform:translateY(var(--h,300px))}}}}
@keyframes ring{{0%{{opacity:.9;transform:scale(.3)}}100%{{opacity:0;transform:scale(2.6)}}}}
.f{{opacity:0;animation:fade .8s ease-out both}}
.r{{opacity:0;animation:rise .7s cubic-bezier(.2,.7,.2,1) both;transform-box:fill-box}}
.p{{opacity:0;transform-box:fill-box;transform-origin:center;animation:pop .35s ease-out both}}
.g{{transform-box:fill-box;transform-origin:bottom;transform:scaleY(0);animation:grow .8s cubic-bezier(.2,.7,.2,1) both}}
.cur{{animation:blink 1s step-end infinite}}
.live{{animation:pulse 1.6s ease-in-out infinite}}
.ring{{transform-box:fill-box;transform-origin:center;animation:ring 2s ease-out infinite}}
.scan{{animation:scan 5s linear infinite}}
"""


def delay(s):
    return f' style="animation-delay:{s:.2f}s"'


def svg(w, h, body, label):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
        f'role="img" aria-label="{escape(label)}"><title>{escape(label)}</title>'
        f"<style>{CSS}</style>"
        f'<defs><pattern id="grid" width="22" height="22" patternUnits="userSpaceOnUse">'
        f'<path d="M22 0H0V22" fill="none" stroke="{LINE}" stroke-width=".6" opacity=".55"/></pattern>'
        f'<linearGradient id="scanG" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0" stop-color="{CYAN}" stop-opacity="0"/>'
        f'<stop offset="1" stop-color="{CYAN}" stop-opacity=".09"/></linearGradient></defs>'
        f"{body}</svg>"
    )


def frame(w, h, title, pad=6):
    """Rounded panel with a header strip; returns (svg, content top y)."""
    return (
        f'<rect x="{pad}" y="{pad}" width="{w - 2*pad}" height="{h - 2*pad}" rx="10" fill="{BG}" stroke="{LINE}"/>'
        f'<rect x="{pad}" y="{pad}" width="{w - 2*pad}" height="{h - 2*pad}" rx="10" fill="url(#grid)"/>'
        f'<path d="M{pad+10} {pad}H{pad+70}" stroke="{CYAN}" stroke-width="2"/>'
        f'<text x="{pad+18}" y="{pad+26}" font-size="11" fill="{CYAN}" letter-spacing="1.5">{escape(title)}</text>'
    ), pad + 26


def write(name, content):
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, name), "w") as f:
        f.write(content)
    print("wrote cards/" + name)


def wrap(text, n):
    lines, cur = [], ""
    for word in text.split():
        if cur and len(cur) + 1 + len(word) > n:
            lines.append(cur)
            cur = word
        else:
            cur = f"{cur} {word}".strip()
    return lines + ([cur] if cur else [])


# ---- hero -------------------------------------------------------------------
def hero(data):
    h = 330
    b = [f'<rect x="6" y="6" width="{W-12}" height="{h-12}" rx="12" fill="{BG}" stroke="{LINE}"/>',
         f'<rect x="6" y="6" width="{W-12}" height="{h-12}" rx="12" fill="url(#grid)"/>']
    # window chrome
    b.append(f'<path d="M6 40H{W-6}" stroke="{LINE}"/>')
    for i, c in enumerate(["#ff5f56", "#ffbd2e", "#27c93f"]):
        b.append(f'<circle cx="{28 + i*18}" cy="23" r="5.5" fill="{c}" opacity=".85"/>')
    b.append(f'<text x="{W/2}" y="27" font-size="11" fill="{MUTED}" text-anchor="middle">'
             f'root@{HANDLE}-mainframe: ~</text>')
    b.append(f'<circle cx="{W-34}" cy="23" r="4" fill="{GREEN}" class="live"/>'
             f'<text x="{W-44}" y="27" font-size="10" fill="{GREEN}" text-anchor="end">ONLINE</text>')

    # name block
    b.append(f'<text x="34" y="92" font-size="38" font-weight="700" fill="{TEXT}" letter-spacing="2" class="r">'
             f'{escape(NAME)}</text>')
    b.append(f'<text x="36" y="118" font-size="13" fill="{CYAN}" class="r"{delay(.15)}>'
             f'@{HANDLE} <tspan fill="{MUTED}">//</tspan> <tspan fill="{BLUE}">{escape(ROLE)}</tspan> 🇻🇳</text>')

    # typed terminal: each line revealed by an animated clip rect
    t0, y = 0.6, 154
    for i, (sym, line) in enumerate(TERMINAL):
        col = {"$": CYAN, "+": GREEN, ">": BLUE}[sym]
        dur = max(0.35, len(line) * 0.012)
        cid = f"c{i}"
        b.append(f'<clipPath id="{cid}"><rect x="34" y="{y-13}" width="0" height="18">'
                 f'<animate attributeName="width" from="0" to="560" begin="{t0:.2f}s" dur="{dur:.2f}s" '
                 f'fill="freeze" calcMode="linear"/></rect></clipPath>')
        label, _, rest = line.partition("  ")
        body = (f'<tspan fill="{TEXT}" font-weight="700">{escape(label)}</tspan>'
                f'<tspan fill="{MUTED}">  {escape(rest)}</tspan>') if sym == ">" else \
               f'<tspan fill="{TEXT}">{escape(line)}</tspan>'
        b.append(f'<text x="36" y="{y}" font-size="12.5" clip-path="url(#{cid})" xml:space="preserve">'
                 f'<tspan fill="{col}">{sym}</tspan> {body}</text>')
        t0 += dur + 0.08
        y += 22
    # blinking cursor after the last line
    b.append(f'<g class="f"{delay(t0)}><rect x="36" y="{y-12}" width="8" height="14" fill="{CYAN}" class="cur"/></g>')

    # radar on the right
    cx, cy, R = 730, 190, 96
    b.append(f'<g class="f"{delay(.3)}>')
    for rr in (R, R*.66, R*.33):
        b.append(f'<circle cx="{cx}" cy="{cy}" r="{rr:.1f}" fill="none" stroke="{CYAN}" stroke-opacity=".25"/>')
    b.append(f'<path d="M{cx-R} {cy}H{cx+R}M{cx} {cy-R}V{cy+R}" stroke="{CYAN}" stroke-opacity=".15"/>')
    # sweep wedge
    a = math.radians(40)
    x2, y2 = cx + R*math.cos(-a), cy + R*math.sin(-a)
    b.append(f'<defs><linearGradient id="sw" x1="0" y1="0" x2="1" y2="0">'
             f'<stop offset="0" stop-color="{CYAN}" stop-opacity="0"/>'
             f'<stop offset="1" stop-color="{CYAN}" stop-opacity=".45"/></linearGradient></defs>')
    b.append(f'<g><path d="M{cx} {cy}L{cx+R} {cy}A{R} {R} 0 0 0 {x2:.1f} {y2:.1f}Z" fill="url(#sw)"/>'
             f'<path d="M{cx} {cy}L{cx+R} {cy}" stroke="{CYAN}" stroke-width="1.5"/>'
             f'<animateTransform attributeName="transform" type="rotate" from="0 {cx} {cy}" to="360 {cx} {cy}" '
             f'dur="4s" repeatCount="indefinite"/></g>')
    # targets
    for (tx, ty, lbl, d0) in [(cx+48, cy-38, "UAV-07", 0), (cx-56, cy+30, "UAV-12", 1)]:
        b.append(f'<circle cx="{tx}" cy="{ty}" r="7" fill="none" stroke="{CYAN}" class="ring" style="animation-delay:{d0}s"/>'
                 f'<circle cx="{tx}" cy="{ty}" r="3" fill="{CYAN}"/>'
                 f'<path d="M{tx-10} {ty-10}h5M{tx-10} {ty-10}v5M{tx+10} {ty+10}h-5M{tx+10} {ty+10}v-5" stroke="{CYAN}"/>'
                 f'<text x="{tx+13}" y="{ty-8}" font-size="9" fill="{CYAN}">{lbl}</text>')
    b.append(f'<circle cx="{cx}" cy="{cy}" r="3" fill="{CYAN}"/></g>')
    b.append(f'<text x="{cx}" y="{cy+R+22}" font-size="10" fill="{MUTED}" text-anchor="middle" letter-spacing="1.5">'
             f'TARGET LOCK · UAV DETECTION ACTIVE</text>')

    # footer line with live numbers
    s = data["stats"]
    b.append(f'<path d="M6 {h-40}H{W-6}" stroke="{LINE}"/>')
    b.append(f'<text x="34" y="{h-19}" font-size="11" fill="{MUTED}" class="f"{delay(t0+.2)}>'
             f'<tspan fill="{CYAN}">{s["total"]:,}</tspan> contributions this year  ·  '
             f'<tspan fill="{CYAN}">{s["current_streak"]}d</tspan> current streak  ·  '
             f'synced {escape(data["updated"])}</text>')
    # scanline
    b.append(f'<rect x="8" y="0" width="{W-16}" height="40" fill="url(#scanG)" class="scan" style="--h:{h}px"/>')
    label = f"{NAME} ({HANDLE}). {ROLE}. Software architecture meets AI: real-time UAV detection, .NET, computer vision, AIOps."
    return svg(W, h, "".join(b), label)


# ---- contribution heatmap ---------------------------------------------------
def heatmap(data):
    days = data["days"]
    h = 210
    b, top = frame(W, h, "// CONTRIBUTION_MATRIX — LAST 12 MONTHS")
    b = [b]
    b.append(f'<text x="{W-24}" y="32" font-size="11" fill="{MUTED}" text-anchor="end">'
             f'<tspan fill="{CYAN}" font-weight="700">{data["stats"]["total"]:,}</tspan> contributions</text>')

    cell, gap = 12, 3
    x0, y0 = 56, top + 32
    first = datetime.date.fromisoformat(days[0]["date"])
    offset = (first.weekday() + 1) % 7  # Sunday-first rows, like GitHub
    last_month = None
    for i, d in enumerate(days):
        idx = i + offset
        col, row = idx // 7, idx % 7
        x, y = x0 + col*(cell+gap), y0 + row*(cell+gap)
        dt = datetime.date.fromisoformat(d["date"])
        if row == 0 or i == 0:
            if dt.month != last_month and col < 52:
                b.append(f'<text x="{x}" y="{y0-8}" font-size="9.5" fill="{MUTED}">{dt.strftime("%b")}</text>')
                last_month = dt.month
        lv = d["level"]
        anim = f' class="p"{delay(0.2 + col*0.025 + row*0.01)}' if lv else ""
        b.append(f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="2.5" fill="{HEAT[lv]}"{anim}>'
                 f'<title>{d["count"]} on {d["date"]}</title></rect>')
    for row, lbl in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        b.append(f'<text x="{x0-8}" y="{y0 + row*(cell+gap) + 10}" font-size="9.5" fill="{MUTED}" text-anchor="end">{lbl}</text>')
    # legend
    lx, ly = W - 24 - 5*(cell+gap) - 34, h - 26
    b.append(f'<text x="{lx-8}" y="{ly+10}" font-size="9.5" fill="{MUTED}" text-anchor="end">less</text>')
    for i, c in enumerate(HEAT):
        b.append(f'<rect x="{lx + i*(cell+gap)}" y="{ly}" width="{cell}" height="{cell}" rx="2.5" fill="{c}"/>')
    b.append(f'<text x="{lx + 5*(cell+gap) + 4}" y="{ly+10}" font-size="9.5" fill="{MUTED}">more</text>')
    b.append(f'<text x="24" y="{ly+10}" font-size="9.5" fill="{MUTED}">synced {escape(data["updated"])}</text>')
    return svg(W, h, "".join(b), f"{HANDLE}'s contribution graph for the last 12 months, refreshed daily")


# ---- stats + monthly bars ---------------------------------------------------
def stats_card(data):
    s = data["stats"]
    h = 240
    b, top = frame(W, h, "// TELEMETRY")
    b = [b]
    best = s["best_day"]
    best_lbl = datetime.date.fromisoformat(best["date"]).strftime("%b %d") if best["date"] else "-"
    kpis = [
        (f'{s["total"]:,}', "CONTRIBUTIONS", "last 12 months"),
        (f'{s["current_streak"]}', "CURRENT STREAK", "days in a row"),
        (f'{s["longest_streak"]}', "LONGEST STREAK", "days"),
        (f'{best["count"]}', "BUSIEST DAY", best_lbl),
    ]
    for i, (num, lbl, sub) in enumerate(kpis):
        x = 24 + (i % 2) * 190
        y = top + 42 + (i // 2) * 88
        b.append(f'<g class="r"{delay(.1 + i*.12)}>'
                 f'<path d="M{x} {y-28}v62" stroke="{CYAN if i == 1 else LINE}" stroke-width="2"/>'
                 f'<text x="{x+14}" y="{y}" font-size="30" font-weight="700" fill="{TEXT}">{num}</text>'
                 f'<text x="{x+14}" y="{y+20}" font-size="10" fill="{CYAN}" letter-spacing="1.2">{lbl}</text>'
                 f'<text x="{x+14}" y="{y+34}" font-size="9.5" fill="{MUTED}">{escape(sub)}</text></g>')
    if s["current_streak"]:
        b.append(f'<circle cx="{24+190+14+len(kpis[1][0])*19+10}" cy="{top+42-10}" r="4" fill="{GREEN}" class="live"/>')

    # monthly bars
    months = s["monthly"]
    bx, bw, base = 420, 432, h - 44
    peak = max([m["count"] for m in months] + [1])
    slot = bw / max(len(months), 1)
    b.append(f'<text x="{bx}" y="{top+14}" font-size="10" fill="{MUTED}" letter-spacing="1.2">BY MONTH</text>')
    b.append(f'<path d="M{bx} {base}H{bx+bw}" stroke="{LINE}"/>')
    maxh = base - (top + 40)
    for i, m in enumerate(months):
        bh = max(2, m["count"] / peak * maxh)
        x = bx + i*slot + slot*0.18
        hot = m["count"] == peak
        b.append(f'<rect x="{x:.1f}" y="{base-bh:.1f}" width="{slot*0.64:.1f}" height="{bh:.1f}" rx="2" '
                 f'fill="{CYAN if hot else HEAT[2]}" class="g"{delay(.3 + i*.06)}>'
                 f'<title>{m["count"]} in {m["month"]}</title></rect>')
        mon = datetime.date.fromisoformat(m["month"] + "-01").strftime("%b")
        b.append(f'<text x="{x + slot*0.32:.1f}" y="{base+15}" font-size="9" fill="{MUTED}" text-anchor="middle">{mon[0]}</text>')
        if hot:
            b.append(f'<text x="{x + slot*0.32:.1f}" y="{base-bh-6:.1f}" font-size="10" fill="{CYAN}" '
                     f'text-anchor="middle" class="f"{delay(1.2)}>{m["count"]}</text>')
    label = (f'{s["total"]} contributions in the last 12 months; current streak {s["current_streak"]} days; '
             f'longest {s["longest_streak"]} days; busiest day {best["count"]} on {best_lbl}')
    return svg(W, h, "".join(b), label)


# ---- project tiles ----------------------------------------------------------
def project(p, i):
    w, h = 440, 230
    b, top = frame(w, h, f"// {p['code']}")
    b = [b]
    b.append(f'<circle cx="{w-30}" cy="28" r="4" fill="{GREEN}" class="live"/>'
             f'<text x="{w-40}" y="32" font-size="9.5" fill="{GREEN}" text-anchor="end">DEPLOYED</text>')
    b.append(f'<text x="24" y="{top+34}" font-size="20" font-weight="700" fill="{TEXT}" class="r"{delay(.1+i*.15)}>'
             f'{escape(p["title"])}</text>')
    b.append(f'<text x="24" y="{top+54}" font-size="11" fill="{CYAN}" class="r"{delay(.2+i*.15)}>{escape(p["kind"])}</text>')
    for j, ln in enumerate(wrap(p["blurb"], 58)):
        b.append(f'<text x="24" y="{top+82+j*17}" font-size="11" fill="{MUTED}" class="f"{delay(.35+i*.15+j*.08)}>'
                 f'{escape(ln)}</text>')
    x = 24
    for k, t in enumerate(p["tags"]):
        tw = len(t) * 7 + 18
        b.append(f'<g class="r"{delay(.6+i*.15+k*.1)}><rect x="{x}" y="{h-46}" width="{tw}" height="20" rx="10" '
                 f'fill="none" stroke="{CYAN}" stroke-opacity=".5"/>'
                 f'<text x="{x+tw/2}" y="{h-32}" font-size="10" fill="{CYAN}" text-anchor="middle">{escape(t)}</text></g>')
        x += tw + 8
    b.append(f'<rect x="8" y="0" width="{w-16}" height="40" fill="url(#scanG)" class="scan" '
             f'style="--h:{h}px;animation-delay:{i*2.5}s"/>')
    return svg(w, h, "".join(b), f'{p["title"]}: {p["kind"]}. {p["blurb"]}')


def main():
    with open(DATA) as f:
        data = json.load(f)
    write("hero.svg", hero(data))
    write("heatmap.svg", heatmap(data))
    write("stats.svg", stats_card(data))
    for i, p in enumerate(PROJECTS):
        write(p["file"] + ".svg", project(p, i))


if __name__ == "__main__":
    main()
