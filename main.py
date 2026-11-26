#!/usr/bin/env python3
"""The Thursday Globe — news-image-20261126 entry.

Pure Python 3 standard library. Draws a classic dense broadsheet that sums
up Thursday 26 November 2026 in one 1024x1024 image and writes it to
$MAKEFUN_OUTPUT_DIR/entry.png (fallback /output/entry.png). No network, no
files read besides this program and its sibling glyphs.py, deterministic.
"""
import os
import struct
import sys
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import glyphs  # noqa: E402  (advance widths + contours, Liberation Serif)

W = 1024
H = 1024
SS = 3  # text supersampling factor

# ---- palette: faded cream broadsheet, ink near-black, muted region colours
PAPER = (248, 244, 233)
PAPER_DIM = (242, 236, 220)
INK = (26, 24, 20)
INK_SOFT = (58, 56, 50)  # v1.1: darkened from (74, 70, 60) — sub-copy contrast
# vs PAPER 8.56 -> 10.67; same glyphs/advances, so no wrap or layout moves
RED = (172, 32, 28)
RED_DK = (140, 24, 22)
RULE = (26, 24, 20)
SEA = (233, 227, 208)
LAND = (192, 178, 140)  # v1.2: darkened — land/sea contrast 1.22 -> ~1.65
LAND_LINE = (96, 84, 58)  # v1.2: darker coastline, drawn 2px in draw_map
GREEN = (42, 92, 52)
GREEN_BG = (226, 236, 222)
BLUE = (38, 74, 118)
BLUE_BG = (222, 231, 240)
CLAIM_BG = (244, 224, 220)
GOLD = (176, 132, 40)
SLATE = (52, 58, 66)

REGION_COLORS = [
    ("ASIA-PACIFIC", 6, (46, 90, 136)),
    ("MIDDLE EAST", 5, (179, 84, 30)),
    ("AMERICAS", 9, (122, 46, 40)),
    ("OCEANIA", 3, (42, 110, 108)),
    ("EUROPE", 7, (96, 110, 58)),
    ("WORLD", 5, (72, 70, 66)),
]


class Canvas:
    def __init__(self, w=W, h=H, bg=PAPER):
        self.w = w
        self.h = h
        self.px = bytearray(w * h * 3)
        self.fill_rect(0, 0, w, h, bg)

    def _idx(self, x, y):
        return (y * self.w + x) * 3

    def set_px(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = self._idx(x, y)
            self.px[i] = c[0]
            self.px[i + 1] = c[1]
            self.px[i + 2] = c[2]

    def fill_rect(self, x, y, w, h, c):
        x0 = max(0, int(x))
        y0 = max(0, int(y))
        x1 = min(self.w, int(x + w))
        y1 = min(self.h, int(y + h))
        if x1 <= x0 or y1 <= y0:
            return
        row = bytes(c) * (x1 - x0)
        for yy in range(y0, y1):
            i = self._idx(x0, yy)
            self.px[i:i + len(row)] = row

    def rect(self, x, y, w, h, c, t=1):
        self.fill_rect(x, y, w, t, c)
        self.fill_rect(x, y + h - t, w, t, c)
        self.fill_rect(x, y, t, h, c)
        self.fill_rect(x + w - t, y, t, h, c)

    def hline(self, x, y, w, c, t=1):
        self.fill_rect(x, y, w, t, c)

    def vline(self, x, y, h, c, t=1):
        self.fill_rect(x, y, t, h, c)

    def line(self, x0, y0, x1, y1, c):
        # Bresenham, 1px
        dx = abs(x1 - x0)
        dy = -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        x, y = x0, y0
        while True:
            self.set_px(x, y, c)
            if x == x1 and y == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x += sx
            if e2 <= dx:
                err += dx
                y += sy

    def fill_poly(self, pts, c):
        """Even-odd scanline fill. pts: list of (x, y), y grows downwards."""
        if len(pts) < 3:
            return
        ys = [p[1] for p in pts]
        y0 = max(0, int(min(ys)))
        y1 = min(self.h - 1, int(max(ys)) + 1)
        n = len(pts)
        for y in range(y0, y1 + 1):
            yc = y + 0.5
            xs = []
            for i in range(n):
                x0, y0e = pts[i]
                x1, y1e = pts[(i + 1) % n]
                if y0e == y1e:
                    continue
                if (yc >= min(y0e, y1e)) and (yc < max(y0e, y1e)):
                    xs.append(x0 + (yc - y0e) * (x1 - x0) / (y1e - y0e))
            if not xs:
                continue
            xs.sort()
            for k in range(0, len(xs) - 1, 2):
                xa = int(max(0, xs[k]))
                xb = int(min(self.w, xs[k + 1] + 1))
                if xb > xa:
                    self.fill_rect(xa, y, xb - xa, 1, c)

    def fill_circle(self, cx, cy, r, c):
        r = int(r)
        for dy in range(-r, r + 1):
            dx = int((r * r - dy * dy) ** 0.5)
            self.fill_rect(cx - dx, cy + dy, 2 * dx + 1, 1, c)

    def fill_ellipse(self, cx, cy, rx, ry, c):
        rx = int(rx)
        ry = int(ry)
        for dy in range(-ry, ry + 1):
            t = 1.0 - (dy * dy) / float(ry * ry)
            dx = int(rx * (t ** 0.5)) if t > 0 else 0
            self.fill_rect(cx - dx, cy + dy, 2 * dx + 1, 1, c)


def png_bytes(cv):
    """Encode the canvas as PNG. Per-row filter: None vs Sub, smaller wins."""
    raw = bytearray()
    w, h = cv.w, cv.h
    prev = bytearray(w * 3)
    for y in range(h):
        row = bytes(cv.px[y * w * 3:(y + 1) * w * 3])
        sub = bytearray(w * 3)
        for i in range(w * 3):
            left = row[i - 3] if i >= 3 else 0
            sub[i] = (row[i] - left) & 0xFF
        score_none = sum(abs(b if b < 128 else b - 256) for b in row)
        score_sub = sum(abs(b if b < 128 else b - 256) for b in sub)
        if score_sub < score_none:
            raw.append(1)
            raw.extend(sub)
        else:
            raw.append(0)
            raw.extend(row)
        prev = row

    def chunk(kind, data):
        out = struct.pack(">I", len(data)) + kind + data
        out += struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
        return out

    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
            + chunk(b"IEND", b""))


# ---- text engine: vector glyphs, SS supersampling, even-odd fill (hollow O/0/a/e/D/8)
_MASK_CACHE = {}


def _glyph_mask(ch, size, bold):
    key = (ch, size, bold)
    hit = _MASK_CACHE.get(key)
    if hit is not None:
        return hit
    table = glyphs.BOLD if bold else glyphs.REG
    entry = table.get(ch)
    if entry is None:
        entry = glyphs.REG.get("?", (1000, []))
    adv, contours = entry
    scale = size / float(glyphs.UPM) * SS
    # scale contour points into supersampled pixel space, y flipped
    polys = []
    minx = miny = None
    maxx = maxy = None
    for contour in contours:
        poly = []
        for (fx, fy) in contour:
            px = fx * scale
            py = -fy * scale
            poly.append((px, py))
            minx = px if minx is None else min(minx, px)
            maxx = px if maxx is None else max(maxx, px)
            miny = py if miny is None else min(miny, py)
            maxy = py if maxy is None else max(maxy, py)
        polys.append(poly)
    if not polys:
        res = (0, 0, b"", 0, 0, adv * size / float(glyphs.UPM))
        _MASK_CACHE[key] = res
        return res
    ox = int(minx // 1)
    oy = int(miny // 1)
    wss = int(maxx - ox) + 2
    hss = int(maxy - oy) + 2
    # binary mask at SS resolution, even-odd scanline
    mask = bytearray(wss * hss)
    # rasterize all contours together: per row, gather intersections of every
    # contour edge, sort, fill pairs (even-odd across contours = hollow counters)
    edges = []
    for poly in polys:
        n = len(poly)
        for i in range(n):
            x0, y0 = poly[i][0] - ox, poly[i][1] - oy
            x1, y1 = poly[(i + 1) % n][0] - ox, poly[(i + 1) % n][1] - oy
            if y0 != y1:
                edges.append((x0, y0, x1, y1))
    for yy in range(hss):
        yc = yy + 0.5
        xs = []
        for (x0, y0, x1, y1) in edges:
            if (yc >= min(y0, y1)) and (yc < max(y0, y1)):
                xs.append(x0 + (yc - y0) * (x1 - x0) / (y1 - y0))
        if not xs:
            continue
        xs.sort()
        for k in range(0, len(xs) - 1, 2):
            xa = max(0, int(xs[k]))
            xb = min(wss, int(xs[k + 1] + 1))
            base = yy * wss
            for xx in range(xa, xb):
                mask[base + xx] = 1
    # downsample SSxSS -> alpha 0..SS*SS per output pixel
    w = (wss + SS - 1) // SS
    h = (hss + SS - 1) // SS
    alpha = bytearray(w * h)
    for yy in range(h):
        for xx in range(w):
            s = 0
            for dy in range(SS):
                sy = yy * SS + dy
                if sy >= hss:
                    break
                base = sy * wss + xx * SS
                for dx in range(SS):
                    if xx * SS + dx < wss:
                        s += mask[base + dx]
            alpha[yy * w + xx] = s
    # dx/dy: mask origin relative to pen position and baseline, in output px
    dx = ox / float(SS)
    dy_top = oy / float(SS)  # mask top is dy_top px above the baseline
    res = (w, h, bytes(alpha), dx, dy_top, adv * size / float(glyphs.UPM))
    _MASK_CACHE[key] = res
    return res


def text_width(s, size, bold=False, space_extra=0.0):
    table = glyphs.BOLD if bold else glyphs.REG
    total = 0.0
    for ch in s:
        entry = table.get(ch) or glyphs.REG.get("?", (1000, []))
        total += entry[0] * size / float(glyphs.UPM)
        if ch == " ":
            total += space_extra
    return total


def draw_text(cv, x, y_base, s, size, bold=False, color=INK, align="l",
              space_extra=0.0):
    """Draw text with baseline at y_base. align: l (left), c (centre), r."""
    if not s:
        return
    w = text_width(s, size, bold, space_extra)
    if align == "c":
        x = x - w / 2.0
    elif align == "r":
        x = x - w
    pen = x
    for ch in s:
        mw, mh, alpha, dx, dy_top, adv = _glyph_mask(ch, size, bold)
        if mw and mh:
            gx = int(round(pen + dx))
            # dy_top is negative: mask top sits |dy_top| px ABOVE the baseline
            gy = int(round(y_base + dy_top))
            for yy in range(mh):
                cy = gy + yy
                if cy < 0 or cy >= cv.h:
                    continue
                row = yy * mw
                for xx in range(mw):
                    a = alpha[row + xx]
                    if not a:
                        continue
                    cx = gx + xx
                    if cx < 0 or cx >= cv.w:
                        continue
                    i = (cy * cv.w + cx) * 3
                    inv = SS * SS - a
                    cv.px[i] = (color[0] * a + cv.px[i] * inv) // (SS * SS)
                    cv.px[i + 1] = (color[1] * a + cv.px[i + 1] * inv) // (SS * SS)
                    cv.px[i + 2] = (color[2] * a + cv.px[i + 2] * inv) // (SS * SS)
        pen += adv + (space_extra if ch == " " else 0.0)


def wrap_text(s, size, bold, maxw, space_extra=0.0):
    """Greedy word wrap. Returns list of lines; hard-splits overlong words."""
    words = s.split(" ")
    lines = []
    cur = ""
    for word in words:
        trial = word if not cur else cur + " " + word
        if text_width(trial, size, bold, space_extra) <= maxw:
            cur = trial
            continue
        if cur:
            lines.append(cur)
        # hard-split the word itself if it alone is too wide
        while text_width(word, size, bold, space_extra) > maxw:
            cut = len(word)
            while cut > 1 and text_width(word[:cut], size, bold,
                                         space_extra) > maxw:
                cut -= 1
            lines.append(word[:cut])
            word = word[cut:]
        cur = word
    if cur:
        lines.append(cur)
    return lines


def draw_lines(cv, x, y_top, lines, size, leading, bold=False, color=INK,
               align="l", maxw=None, space_extra=0.0):
    """Draw wrapped lines; y_top is the top of the first line's em box."""
    asc = int(size * 0.82) + 1
    for i, ln in enumerate(lines):
        yb = y_top + asc + i * leading
        if align == "c":
            draw_text(cv, x + (maxw or 0) / 2.0, yb, ln, size, bold, color,
                      "c", space_extra)
        elif align == "r":
            draw_text(cv, x + (maxw or 0), yb, ln, size, bold, color, "r",
                      space_extra)
        else:
            draw_text(cv, x, yb, ln, size, bold, color, "l", space_extra)
    return y_top + asc + (len(lines) - 1) * leading + int(size * 0.24)


# ---- content: STORY-LIST.md is the single source of truth (35 stories)
MX = 24            # left/right margin
CW = W - 2 * MX    # content width = 976

STATS = [
    ("−0.6%", "NASDAQ · INTRADAY −4.6%"),
    ("+1.6%", "NIKKEI · THU REBOUND"),
    ("$94.61", "BRENT · +3.5%"),
    ("31", "DEAD · CAIRO FIRE"),
    ("18TH", "ANNIV. · 26/11 MUMBAI"),
    ("€45BN", "UKRAINE LOAN"),
]

TIMELINE = [
    ("01:37 GMT", "Brent $94.71 in early Asian trade"),
    ("05:44 UTC", "EU leaders gather in Brussels"),
    ("12:00 UTC", "London Tube strike begins"),
    ("13:30 UTC", "Macy’s parade hour (08:30 ET)"),
    ("14:00 UTC", "Gukesh–Sindarov Game 3 begins"),
    ("21:00 UTC", "No Tube service in London"),
]

LEADS = [
    {
        "num": 1, "kick": "WASHINGTON · TRADE", "pill": "REPORTED",
        "head": "US proposes tariffs on 14 partners",
        "deck": ("India 25%, Japan 15%, China 20% in some reports. EU rejects "
                 "the premise; Brazil calls it unacceptable; Asia rebounds as "
                 "levies look milder."),
        "meta": "BBC, France 24, Japan Times · USTR order, Wed",
        "scene": "tariffs",
    },
    {
        "num": 2, "kick": "RAS TANURA · CONFLICT", "pill": "CLAIM",
        "head": "Houthis claim Ras Tanura refinery hit",
        "deck": ("Smoke seen by satellite over the 550,000-bpd plant. Coalition "
                 "says 4 drones downed; Jazan port struck. Brent jumps 3.5%."),
        "meta": "Reuters · claim: Houthis",
        "scene": "refinery",
    },
    {
        "num": 3, "kick": "NEW YORK · CULTURE", "pill": "OFFICIAL",
        "head": "Macy’s 100th parade postponed",
        "deck": ("First weather delay ever — the parade moves to Saturday "
                 "8:30 a.m. as a nor’easter brings gusts to 60 mph. Balloons "
                 "deflated; NBC airs a 2025 rerun."),
        "meta": "Reuters, CNN · announced Wed",
        "scene": "parade",
    },
]

# small cards: (num, kicker, pill, headline, deck, icon key)
SMALL = [
    (4, "CAIRO · DISASTER", "OFFICIAL", "Cairo tanker fire kills 31",
     "Fuel tanker overturns on the Ring Road, Wed evening; 21 hurt, 27 "
     "vehicles charred; toll is preliminary.", "flame"),
    (5, "KYIV · CONFLICT", "REPORTED", "Ukraine hits 5 jets; Kyiv struck",
     "Savasleyka airbase hit — 3 MiG-31s, 2 Su-34s. Russia hits Kyiv "
     "shopping centre; 2 Samara refineries struck.", "jet"),
    (6, "NEW YORK · ECONOMY", "REPORTED", "Nasdaq plunges, then recovers",
     "Wed close −0.6% at 23,586 after −4.6% intraday dive; Nasdaq-100 "
     "briefly −20% off record. Nvidia −3.9%.", "chart"),
    (7, "LONDON · SOCIETY", "OFFICIAL", "Tube strike halts London",
     "RMT walkout from noon Thu to noon Fri; no Piccadilly or Circle all "
     "day, no service at all after 21:00.", "train"),
    (8, "BRUSSELS · ECONOMY", "REPORTED", "EU fights over €45bn Ukraine loan",
     "Leaders meet Thu over a €1.58tn budget and Kyiv’s 2027 gap; deal "
     "aimed for 17–18 Dec.", "flag"),
    (9, "MUMBAI · SOCIETY", "OFFICIAL", "India marks 18 years since 26/11",
     "166 killed in 2008; Mumbai on high alert as tributes are paid. "
     "Jaishankar: zero tolerance on terror.", "candle"),
    (10, "GENEVA · SPORT", "OFFICIAL", "Gukesh–Sindarov: Game 3 today",
     "World title match level 1–1 after two draws. Sindarov has White; "
     "first to 7.5 points takes the $2.5m crown.", "chess"),
    (11, "SEOUL · ECONOMY", "OFFICIAL", "Bank of Korea lifts rate to 3.25%",
     "Up 25bp, the highest in two years; 2027 growth forecast raised to "
     "4.1%.", "bank"),
    (12, "HONG KONG · SOCIETY", "REPORTED",
     "Hong Kong marks year since fire killed 168",
     "Tai Po’s Wang Fuk Court, one year on. No official memorial; "
     "families still await full answers.", "memorial"),
    (13, "KATHMANDU · DISASTER", "REPORTED",
     "Nepal: 213 Indians presumed dead",
     "Kathmandu begins declaring flood-missing Indians dead; embassy asks "
     "families to come forward.", "flood"),
]

ALSO = [
    "Asia rebounds: Nikkei +1.6% as tariffs look milder; Shanghai −2.1%",
    "Brent $94.61 (+3.5%); WTI $83.68 (+2%) as Gulf fears lift oil",
    "Trump, Rutte urge Russia not to widen the war (Mar-a-Lago talks)",
    "ECB: Pablo Hernandez de Cos set to succeed Lagarde",
    "Abrego Garcia reaches Spain after a 20-month US legal fight",
    "Brazil withdraws ambassador to Argentina for good",
    "Hasina return dispute: India separates return from extradition",
    "ISIL suicide attack kills 2 in Hasakah, Syria",
    "Somalia: foreign troops withdraw; Uganda steps up anti-al-Shabaab fight",
    "Australia projected to miss its 2035 emissions target",
    "Flinders Island fire destroys at least 6 homes",
    "Liverpool beat Club Brugge 3–0 in the Champions League",
    "Lille beat Bayern 2–1, ending their unbeaten run",
    "Rare lakes found beneath the Red Sea",
    "Canadian astronaut welcomes a baby girl from orbit",
    "Pig-kidney patient marks one year off dialysis",
    "Famine risk falls in Baidoa, Somalia — but hunger persists",
    "US Army calls Iowa 5-ton blast a 'huge success'",
    "Kurtley Beale returns to the Wallabies after five years",
    "Gordon Ramsay to host revived Top Gear",
    "U-17 World Cup: Egypt 4–1 Panama; Uganda 6–0 New Caledonia",
    "King tides flood the California coast as storms hit Thanksgiving travel",
]

DATE_CHECK = [
    "Shenzhou-24 launch; first Pakistani in orbit (Wed 25 Nov)",
    "Asia sell-off: Nikkei −3.6%, Kospi −5.6%, SoftBank −16.1% (Wed 25 Nov)",
    "Solomons–Australia security treaty signed (Wed 25 Nov)",
    "Huawei guilty verdict, New York (Wed 25 Nov)",
    "UK energy cap +26% to £2,166 (Wed 25 Nov)",
    "Russia war deaths ≥490,000 leaked (Wed 25 Nov)",
    "Netanyahu judges urge bribery charge dropped (Wed 25 Nov)",
    "Gaza: Hamas security chief Abu al-Ouf killed (Wed 25 Nov)",
    "FCC clears SpaceX 1M-satellite plan (Wed 25 Nov)",
    "Miss Universe: Jennifer Barreto wins (Tue 24 Nov)",
    "Kim Jong Un vows wider tactical nukes (Wed 25 Nov)",
    "Chen Jining probe, Shanghai (Tue 24 Nov)",
]

MORE_CHECKED = (
    "+15 MORE CHECKED: Senegal AFCON title restored (CAS, Tue 24 Nov) · "
    "Canary Islands record 1,990 arrivals (Tue 24 Nov) · US “leave Iran now” "
    "alert (Tue 24 Nov) · Iraq court backs Baghdad control of Kurdish oil "
    "(Wed 25 Nov) · Cartagena: 76 hostages freed (Wed 25 Nov) · Sudan Blue "
    "Nile drone attacks kill 15 (Tue 24 Nov) · Bangladesh garment wage "
    "12,500→17,000 taka (Wed 25 Nov) · Lukoil overseas-assets deal (Wed "
    "25 Nov) · Greek workers strike (Wed 25 Nov) · Poundland collapses, "
    "11,000 jobs at risk (Wed 25 Nov) · Andy Taylor, Duran Duran guitarist, "
    "dies at 65 (Wed 25 Nov) · Hera images show Dimorphos crater (Wed "
    "25 Nov) · UNAIDS warns aid cuts may raise HIV cases (Wed 25 Nov) · "
    "Hormuz: Iran claims two tankers hit mines (Wed 25 Nov) · US core PCE "
    "3.3% tops forecast (Wed 25 Nov)"
)

# pill fg: one step darker than the shared palette constants, so the 8px
# bold badge labels (and their 1px borders) read crisper on the tints
PILL_STYLE = {
    "OFFICIAL": ((36, 80, 45), GREEN_BG),
    "REPORTED": ((32, 64, 102), BLUE_BG),
    "CLAIM": ((128, 22, 20), CLAIM_BG),
}


def draw_pill(cv, x, y, label, size=8):
    fg, bg = PILL_STYLE[label]
    w = int(text_width(label, size, True)) + 10
    cv.fill_rect(x, y, w, 13, bg)
    cv.rect(x, y, w, 13, fg, 1)
    draw_text(cv, x + 5, y + 10, label, size, True, fg)
    return w


# ---- schematic scenes for the three leads (drawn in code, flat vector)
def scene_tariffs(cv, x, y, w, h):
    cv.fill_rect(x, y, w, h, (214, 226, 236))
    cv.fill_rect(x, y + h - 16, w, 16, (58, 96, 130))  # sea band
    # container ship, left
    hx, hy = x + 16, y + h - 34
    cv.fill_poly([(hx, hy), (hx + 108, hy), (hx + 96, hy + 14),
                  (hx + 10, hy + 14)], (26, 24, 20))
    for i, cc in enumerate([(172, 32, 28), (46, 90, 136), (176, 132, 40)]):
        cv.fill_rect(hx + 14 + i * 30, hy - 20, 26, 20, cc)
        cv.rect(hx + 14 + i * 30, hy - 20, 26, 20, INK, 1)
    cv.fill_rect(hx + 96, hy - 34, 4, 34, INK)
    cv.fill_rect(hx + 88, hy - 38, 20, 4, INK)
    # tariff bars, right: India 25 / Japan 15 / China 20
    bx = x + w - 128
    base = y + h - 16
    bars = [("INDIA", 25, RED), ("JAPAN", 15, GOLD), ("CHINA", 20, BLUE)]
    for i, (lab, val, col) in enumerate(bars):
        bh = int(val * 1.9)
        xx = bx + i * 42
        cv.fill_rect(xx, base - bh, 30, bh, col)
        cv.rect(xx, base - bh, 30, bh, INK, 1)
        draw_text(cv, xx + 15, base - bh - 4, "%d%%" % val, 11, True, INK, "c")
        draw_text(cv, xx + 15, base + 12, lab, 8, True, INK, "c")
    cv.fill_rect(x + 4, y + 4, 96, 15, INK)
    draw_text(cv, x + 8, y + 15, "USTR PROPOSAL", 9, True, (255, 255, 255))


def scene_refinery(cv, x, y, w, h):
    # dusk bands
    cv.fill_rect(x, y, w, 26, (226, 148, 74))
    cv.fill_rect(x, y + 26, w, 26, (198, 96, 52))
    cv.fill_rect(x, y + 52, w, h - 52, (74, 48, 52))
    # smoke plume: small, darker, rising puffs (not balloons)
    for (sx, sy, sr, col) in [(150, 30, 10, (100, 96, 90)),
                              (166, 20, 13, (120, 116, 110)),
                              (188, 12, 16, (140, 136, 130))]:
        cv.fill_circle(x + sx, y + sy, sr, col)
    # towers and tanks
    cv.fill_rect(x + 24, y + 34, 14, h - 34, (38, 34, 36))
    cv.fill_rect(x + 44, y + 44, 12, h - 44, (38, 34, 36))
    cv.fill_rect(x + 62, y + 28, 16, h - 28, (38, 34, 36))
    cv.fill_circle(x + 120, y + h - 18, 16, (52, 46, 48))
    cv.fill_circle(x + 158, y + h - 14, 12, (52, 46, 48))
    cv.fill_rect(x + 200, y + 40, 12, h - 40, (38, 34, 36))
    cv.fill_rect(x + 216, y + 52, 40, h - 52, (38, 34, 36))
    # flame, larger so it reads over the towers
    fx, fy = x + 70, y + 28
    cv.fill_poly([(fx - 11, fy), (fx, fy - 26), (fx + 11, fy)], (232, 120, 30))
    cv.fill_poly([(fx - 6, fy), (fx, fy - 16), (fx + 6, fy)], (250, 205, 80))
    cv.fill_rect(x + 4, y + 4, 104, 15, INK)
    draw_text(cv, x + 8, y + 15, "550,000 BPD", 9, True, (255, 255, 255))


def scene_parade(cv, x, y, w, h):
    # storm sky bands
    cv.fill_rect(x, y, w, 30, (96, 104, 116))
    cv.fill_rect(x, y + 30, w, 26, (72, 80, 92))
    cv.fill_rect(x, y + 56, w, h - 56, (52, 58, 66))
    # rain dashes
    for rx in range(14, w, 26):
        for ry in range(6, 52, 14):
            cv.line(x + rx, y + ry, x + rx - 5, y + ry + 8, (200, 206, 214))
    # Manhattan skyline
    heights = [34, 52, 40, 62, 30, 48, 56, 36, 44, 28]
    bx = x + 8
    for i, hh in enumerate(heights):
        cv.fill_rect(bx + i * 30, y + h - hh, 24, hh, (26, 24, 20))
        for wy in range(6, hh - 6, 12):
            cv.fill_rect(bx + i * 30 + 5, y + h - hh + wy, 4, 5, (250, 205, 80))
    # sagging deflated balloon: round envelope + darker fold band + ropes
    cv.fill_ellipse(x + 190, y + 26, 42, 22, (172, 32, 28))
    cv.fill_ellipse(x + 190, y + 38, 30, 8, (140, 24, 22))
    cv.line(x + 158, y + 42, x + 148, y + 60, (26, 24, 20))
    cv.line(x + 222, y + 42, x + 232, y + 60, (26, 24, 20))
    cv.fill_rect(x + 4, y + 4, 118, 15, INK)
    draw_text(cv, x + 8, y + 15, "100TH · SAT 08:30", 9, True, (255, 255, 255))


SCENES = {"tariffs": scene_tariffs, "refinery": scene_refinery,
          "parade": scene_parade}


# v1.2: one consistent stroke weight (SW = 3px) for every spot icon.
# Silhouettes are filled polys; linear strokes are 3px discs along the path.
SW = 3


def stroke3(cv, pts, c):
    for i in range(len(pts) - 1):
        x0, y0 = pts[i]
        x1, y1 = pts[i + 1]
        steps = int(max(abs(x1 - x0), abs(y1 - y0))) + 1
        for s in range(steps + 1):
            t = s / float(steps)
            cv.fill_circle(int(round(x0 + (x1 - x0) * t)),
                           int(round(y0 + (y1 - y0) * t)), 1, c)


def draw_icon(cv, x, y, w, h, key):
    bg = {"flame": (58, 44, 40), "jet": (206, 220, 232),
          "chart": (238, 232, 216), "train": (176, 32, 28),
          "flag": (38, 74, 118), "candle": (52, 48, 44),
          "chess": (238, 232, 216), "bank": (226, 220, 200),
          "memorial": (52, 48, 44), "flood": (206, 220, 232)}[key]
    cv.fill_rect(x, y, w, h, bg)
    cx, cy = x + w // 2, y + h // 2
    if key == "flame":
        # tanker truck (side view, facing right) with flame over the tank
        cv.fill_poly([(cx - 40, cy + 1), (cx - 36, cy - 12), (cx - 32, cy - 5),
                      (cx - 28, cy - 16), (cx - 22, cy + 1)], (232, 120, 30))
        cv.fill_poly([(cx - 35, cy + 1), (cx - 32, cy - 7), (cx - 28, cy + 1)],
                     (250, 205, 80))
        cv.fill_rect(cx - 52, cy + 1, 54, 12, (248, 244, 233))
        cv.rect(cx - 52, cy + 1, 54, 12, INK, 3)
        cv.fill_rect(cx - 30, cy - 2, 10, 3, INK)
        cv.fill_rect(cx + 6, cy + 1, 22, 12, RED)
        cv.rect(cx + 6, cy + 1, 22, 12, INK, 3)
        cv.fill_rect(cx + 16, cy + 3, 8, 5, (248, 244, 233))
        for wx in (cx - 42, cx - 18, cx + 17):
            cv.fill_circle(wx, cy + 14, 4, INK)
            cv.fill_circle(wx, cy + 14, 2, (248, 244, 233))
    elif key == "jet":
        # fighter jet (side view, nose right) + 3px speed lines
        cv.fill_poly([(cx - 48, cy - 2), (cx + 30, cy - 4), (cx + 58, cy + 1),
                      (cx + 30, cy + 6), (cx - 48, cy + 6)], (38, 42, 48))
        cv.fill_poly([(cx - 50, cy - 2), (cx - 38, cy - 15), (cx - 28, cy - 2)],
                     (38, 42, 48))
        cv.fill_poly([(cx - 12, cy + 4), (cx - 34, cy + 16), (cx - 20, cy + 16),
                      (cx + 2, cy + 6)], (38, 42, 48))
        cv.fill_ellipse(cx + 24, cy - 2, 7, 3, (250, 205, 80))
        for sy in (cy - 6, cy + 1, cy + 8):
            cv.fill_rect(cx - 72, sy - 1, 16, 3, (38, 42, 48))
    elif key == "chart":
        # axes + rising trend line (3px) with arrowhead over three bars
        cv.fill_rect(cx - 70, cy - 13, 3, 26, INK)
        cv.fill_rect(cx - 70, cy + 10, 140, 3, INK)
        cv.fill_rect(cx - 58, cy + 2, 12, 8, BLUE)
        cv.fill_rect(cx - 40, cy - 2, 12, 12, GOLD)
        cv.fill_rect(cx - 22, cy - 6, 12, 16, BLUE)
        pts = [(cx - 58, cy - 8), (cx - 36, cy - 12), (cx - 14, cy - 9),
               (cx + 8, cy - 15), (cx + 36, cy - 17)]
        stroke3(cv, pts, RED)
        cv.fill_poly([(cx + 38, cy - 18), (cx + 26, cy - 16), (cx + 34, cy - 8)],
                     RED)
    elif key == "train":
        # subway front view: cream body, twin blue windows, gold lights, rail
        cv.fill_rect(cx - 26, cy - 14, 52, 28, (248, 244, 233))
        cv.rect(cx - 26, cy - 14, 52, 28, INK, 3)
        cv.fill_rect(cx - 20, cy - 9, 16, 9, BLUE)
        cv.fill_rect(cx + 4, cy - 9, 16, 9, BLUE)
        cv.fill_rect(cx - 1, cy - 9, 3, 9, INK)
        cv.fill_rect(cx - 20, cy + 2, 40, 3, GOLD)
        cv.fill_circle(cx - 16, cy + 9, 3, GOLD)
        cv.fill_circle(cx + 16, cy + 9, 3, GOLD)
        cv.fill_rect(cx - 34, cy + 16, 68, 3, INK)
    elif key == "flag":
        # financial document with vector euro sign (no text) + rule lines
        cv.fill_rect(cx - 28, cy - 14, 56, 28, (248, 244, 233))
        cv.rect(cx - 28, cy - 14, 56, 28, INK, 3)
        cv.fill_poly([(cx + 16, cy - 14), (cx + 28, cy - 2), (cx + 28, cy - 14)],
                     (210, 202, 182))
        stroke3(cv, [(cx + 16, cy - 14), (cx + 28, cy - 2)], INK)
        arc = []
        for k in range(25):
            a = (55.0 + k * 250.0 / 24.0) * 3.14159265 / 180.0
            arc.append((cx - 6 + int(round(11 * _cos(a))),
                        cy - 1 + int(round(11 * _sin(a)))))
        stroke3(cv, arc, RED)
        cv.fill_rect(cx - 17, cy - 5, 18, 3, RED)
        cv.fill_rect(cx - 17, cy + 2, 18, 3, RED)
        for ly in (cy - 8, cy - 3, cy + 2):
            cv.fill_rect(cx + 10, ly, 12, 3, INK)
    elif key == "candle":
        # solemn memorial wreath (gold leaves, red berries) + flame, Mumbai
        for k in range(16):
            a = (300.0 + k * 20.0) * 3.14159265 / 180.0
            lx = cx + int(round(13 * _cos(a)))
            ly = cy + 2 + int(round(13 * _sin(a)))
            cv.fill_circle(lx, ly, 2, GOLD)
            if k % 2 == 0:
                cv.fill_circle(lx, ly, 1, RED)
        cv.fill_poly([(cx - 6, cy - 2), (cx - 3, cy - 13), (cx, cy - 6),
                      (cx + 3, cy - 16), (cx + 7, cy - 2)], (232, 120, 30))
        cv.fill_poly([(cx - 3, cy - 2), (cx, cy - 8), (cx + 3, cy - 2)],
                     (250, 205, 80))
    elif key == "memorial":
        # high-rise + warning triangle; keeps the v1.1 "168" toll plaque
        cv.fill_rect(cx - 30, cy - 14, 26, 31, (238, 232, 216))
        cv.rect(cx - 30, cy - 14, 26, 31, INK, 3)
        for wy in (cy - 11, cy - 5, cy + 1):
            for wx in (cx - 27, cx - 20, cx - 13):
                cv.fill_rect(wx, wy, 3, 3, INK)
        cv.fill_rect(cx - 28, cy + 7, 22, 9, INK)
        draw_text(cv, cx - 17, cy + 15, "168", 9, True, (250, 205, 80), "c")
        cv.fill_rect(cx, cy - 6, 18, 23, (140, 128, 100))
        cv.rect(cx, cy - 6, 18, 23, INK, 2)
        for wy in (cy - 3, cy + 3, cy + 9):
            for wx in (cx + 3, cx + 10):
                cv.fill_rect(wx, wy, 3, 3, INK)
        cv.fill_poly([(cx + 14, cy - 16), (cx + 28, cy + 8), (cx, cy + 8)],
                     (250, 205, 80))
        stroke3(cv, [(cx + 14, cy - 16), (cx + 28, cy + 8), (cx, cy + 8),
                     (cx + 14, cy - 16)], INK)
        cv.fill_rect(cx + 13, cy - 8, 3, 8, INK)
        cv.fill_circle(cx + 14, cy + 3, 2, INK)
    elif key == "chess":
        # chess knight silhouette (facing right) on a gold base bar:
        # slim neck, ear spike, long muzzle, concave throat notch so the
        # head reads apart from the neck at card size
        cv.fill_poly([(cx - 18, cy + 14), (cx - 15, cy), (cx - 13, cy - 7),
                      (cx - 19, cy - 11), (cx - 12, cy - 16), (cx - 7, cy - 11),
                      (cx - 1, cy - 7), (cx + 7, cy - 4), (cx + 14, cy - 1),
                      (cx + 16, cy + 3), (cx + 11, cy + 6), (cx + 5, cy + 1),
                      (cx + 3, cy + 14)], INK)
        cv.fill_circle(cx + 7, cy - 2, 1, (248, 244, 233))
        cv.fill_rect(cx - 20, cy + 14, 40, 3, GOLD)
    elif key == "bank":
        # classical bank (ink, high contrast) + red rising-rate arrow
        cv.fill_poly([(cx - 34, cy - 4), (cx - 6, cy - 15), (cx + 22, cy - 4)],
                     INK)
        cv.fill_rect(cx - 32, cy - 4, 52, 3, INK)
        for colx in (cx - 30, cx - 18, cx - 6, cx + 6):
            cv.fill_rect(colx, cy, 5, 11, INK)
        cv.fill_rect(cx - 34, cy + 11, 56, 3, INK)
        cv.fill_rect(cx - 36, cy + 14, 60, 3, INK)
        cv.fill_rect(cx + 32, cy - 2, 3, 12, RED)
        cv.fill_poly([(cx + 28, cy - 2), (cx + 38, cy - 2), (cx + 33, cy - 10)],
                     RED)
    elif key == "flood":
        # twin mountain peaks with snow caps + rescue cross in white disc
        cv.fill_poly([(cx - 52, cy + 14), (cx - 14, cy - 14), (cx + 18, cy + 14)],
                     SLATE)
        cv.fill_poly([(cx - 14, cy - 14), (cx - 19, cy - 6), (cx - 9, cy - 6)],
                     (248, 244, 233))
        cv.fill_poly([(cx - 16, cy + 14), (cx + 12, cy - 6), (cx + 38, cy + 14)],
                     INK)
        cv.fill_poly([(cx + 12, cy - 6), (cx + 7, cy), (cx + 17, cy)],
                     (248, 244, 233))
        cv.fill_circle(cx + 44, cy + 6, 9, (255, 255, 255))
        cv.fill_rect(cx + 43, cy - 1, 3, 14, RED)
        cv.fill_rect(cx + 37, cy + 5, 14, 3, RED)


def _cos(a):
    import math
    return math.cos(a)


def _sin(a):
    import math
    return math.sin(a)


# ---- schematic world map (rough equirectangular continents, pins 1-13)
CONTINENTS = [
    # North America
    [(-168, 66), (-140, 70), (-120, 72), (-95, 80), (-80, 73), (-75, 60),
     (-65, 45), (-75, 35), (-80, 26), (-90, 21), (-97, 16), (-105, 20),
     (-117, 33), (-125, 40), (-125, 49), (-145, 60)],
    # South America
    [(-80, 10), (-60, 8), (-50, 0), (-40, -5), (-35, -8), (-40, -20),
     (-48, -28), (-58, -38), (-65, -45), (-70, -55), (-73, -40),
     (-70, -20), (-80, -5)],
    # Africa
    [(-17, 15), (-10, 30), (0, 36), (10, 37), (20, 32), (32, 31), (35, 28),
     (43, 12), (51, 11), (48, 0), (40, -10), (35, -25), (28, -33), (20, -35),
     (15, -27), (12, -18), (9, 4), (-8, 5)],
    # Europe
    [(-10, 36), (-9, 43), (-2, 48), (0, 50), (5, 53), (8, 57), (10, 59),
     (18, 56), (21, 55), (24, 58), (28, 60), (30, 62), (25, 65), (20, 70),
     (15, 70), (10, 68), (5, 60), (-5, 58), (-10, 52)],
    # Asia
    [(30, 62), (40, 68), (60, 70), (80, 73), (100, 77), (120, 73),
     (140, 72), (160, 70), (178, 66), (162, 60), (158, 52), (142, 45),
     (140, 38), (130, 33), (127, 35), (122, 30), (120, 22), (110, 20),
     (105, 10), (100, 8), (95, 15), (90, 22), (85, 20), (80, 13), (77, 8),
     (72, 20), (66, 25), (60, 25), (57, 27), (52, 28), (48, 30), (43, 29),
     (40, 32), (35, 36), (30, 36)],
    # Australia
    [(113, -22), (114, -30), (115, -35), (124, -33), (129, -32), (137, -35),
     (140, -38), (147, -39), (150, -37), (153, -27), (146, -19), (142, -11),
     (135, -12), (130, -13), (126, -14), (122, -17), (118, -20)],
]

# (num, lon, lat, label dx, label dy) — label offsets keep Europe readable
PINS = [
    (1, -77.0, 38.9, -20, -14),
    (2, 50.2, 26.6, 10, -10),
    (3, -74.0, 40.7, -14, 8),
    (4, 31.2, 30.0, 8, 10),
    (5, 30.5, 50.4, 16, -12),
    (6, -74.0, 40.7, 12, -10),
    (7, -0.1, 51.5, -22, -12),
    (8, 4.4, 50.8, 16, -16),
    (9, 72.9, 19.1, 18, -8),
    (10, 6.1, 46.2, 8, 22),
    (11, 127.0, 37.6, 10, -10),
    (12, 114.2, 22.3, 10, 8),
    (13, 85.3, 27.7, -16, 14),
]


def draw_map(cv, x, y, w, h):
    cv.fill_rect(x, y, w, h, SEA)
    cv.rect(x, y, w, h, INK, 1)

    def proj(lon, lat):
        px = x + (lon + 168.0) / 358.0 * w
        py = y + (78.0 - lat) / 136.0 * h
        return (px, py)

    for cont in CONTINENTS:
        cv.fill_poly([proj(lon, lat) for (lon, lat) in cont], LAND)
        pts = [proj(lon, lat) for (lon, lat) in cont]
        for i in range(len(pts)):
            x0, y0 = pts[i]
            x1, y1 = pts[(i + 1) % len(pts)]
            # 2px coastline: two parallel 1px strokes
            cv.line(int(x0), int(y0), int(x1), int(y1), LAND_LINE)
            cv.line(int(x0), int(y0) + 1, int(x1), int(y1) + 1, LAND_LINE)
    for (num, lon, lat, dx, dy) in PINS:
        px, py = proj(lon, lat)
        lx, ly = int(px + dx), int(py + dy)
        cv.line(int(px), int(py), lx, ly, RED_DK)
        cv.fill_circle(int(px), int(py), 2, RED_DK)
        # crisp pin: dark outer ring + white ring + red core, white number
        cv.fill_circle(lx, ly, 9, RED_DK)
        cv.fill_circle(lx, ly, 8, (255, 255, 255))
        cv.fill_circle(lx, ly, 7, RED)
        draw_text(cv, lx, ly + 3, str(num), 8, True, (255, 255, 255), "c")


# ---- layout assembly
def build():
    cv = Canvas()
    y = 8
    # top strip
    draw_text(cv, MX, y + 11, "THE WORLD IN ONE DAY", 11, True, INK)
    draw_text(cv, MX + CW, y + 11, "35 STORIES · 6 REGIONS · THURSDAY 26 NOVEMBER 2026",
              11, True, INK, "r")
    y += 14
    cv.hline(MX, y, CW, RULE, 2)
    y += 6
    # masthead
    draw_text(cv, MX + CW // 2, y + 44, "Thursday 26 November 2026", 52, True,
              INK, "c")
    y += 54
    # red deck line: the three leads in one line
    draw_text(cv, MX + CW // 2, y + 12,
              "US proposes tariffs on 14 partners · Houthis claim Ras Tanura "
              "refinery hit · Macy’s 100th parade postponed",
              13, True, RED, "c")
    y += 16
    cv.hline(MX, y, CW, RULE, 1)
    y += 5
    # stat strip: 6 callouts
    sw = CW // 6
    for i, (val, lab) in enumerate(STATS):
        bx = MX + i * sw
        if i:
            cv.vline(bx, y + 4, 40, (200, 192, 172), 1)
        draw_text(cv, bx + sw // 2, y + 22, val, 22, True, RED_DK, "c")
        draw_text(cv, bx + sw // 2, y + 37, lab, 9, True, INK_SOFT, "c")
    y += 48
    cv.hline(MX, y, CW, RULE, 1)
    y += 4
    # region bar: segments proportional to story counts (must total 35)
    total = sum(c for (_, c, _) in REGION_COLORS)
    assert total == 35, total
    rx = MX
    for (name, count, col) in REGION_COLORS:
        seg = int(round(CW * count / 35.0))
        cv.fill_rect(rx, y, seg, 20, col)
        draw_text(cv, rx + seg // 2, y + 14, "%s %d" % (name, count), 10,
                  True, (255, 255, 255), "c")
        rx += seg
    y += 22
    # timeline: THE DAY IN UTC — title at left, nodes shifted right of it
    tl_y = y + 20
    draw_text(cv, MX, tl_y + 4, "THE DAY IN UTC", 10, True, INK)
    cv.hline(MX + 150, tl_y, CW - 150, INK_SOFT, 1)
    tw = (CW - 150) // 6
    for i, (tm, lab) in enumerate(TIMELINE):
        cx = MX + 150 + tw * i + tw // 2
        cv.fill_circle(cx, tl_y, 4, RED)
        draw_text(cv, cx, tl_y - 5, tm, 11, True, RED_DK, "c")
        lines = wrap_text(lab, 9, False, tw - 14)
        draw_lines(cv, cx - (tw - 14) // 2, tl_y + 6, lines, 9, 11,
                   False, INK_SOFT, "l", tw - 14)
    y += 46
    # ---- three leads
    lw = (CW - 2 * 11) // 3
    lead_top = y
    for i, lead in enumerate(LEADS):
        lx = MX + i * (lw + 11)
        draw_text(cv, lx, y + 11, "%d · %s" % (lead["num"], lead["kick"]), 10,
                  True, RED_DK)
        pw = draw_pill(cv, lx + lw - 62, y, lead["pill"])
        SCENES[lead["scene"]](cv, lx, y + 16, lw, 70)
        hy = y + 16 + 70 + 6
        lines = wrap_text(lead["head"], 20, True, lw)
        draw_lines(cv, lx, hy, lines, 20, 21, True, INK)
        dy = hy + 21 * len(lines) + 2
        dlines = wrap_text(lead["deck"], 11, False, lw)
        draw_lines(cv, lx, dy, dlines, 11, 12, False, INK_SOFT)
        my = dy + 12 * len(dlines) + 8
        draw_text(cv, lx, my, lead["meta"], 9, False, INK_SOFT)
    y = lead_top + 16 + 70 + 6 + 2 * 21 + 2 + 3 * 12 + 8 + 10
    cv.hline(MX, y, CW, (200, 192, 172), 1)
    y += 8
    # ---- small cards: 5 across x 2 rows
    cardw = (CW - 4 * 10) // 5
    cardh = 124
    for row in range(2):
        for col in range(5):
            idx = row * 5 + col
            num, kick, pill, head, deck, icon = SMALL[idx]
            cx0 = MX + col * (cardw + 10)
            cy0 = y + row * (cardh + 6)
            draw_icon(cv, cx0, cy0, cardw, 38, icon)
            draw_text(cv, cx0, cy0 + 50, "%d · %s" % (num, kick), 9, True,
                      RED_DK)
            pw = draw_pill(cv, cx0 + cardw - 58, cy0 + 42, pill)
            hlines = wrap_text(head, 14, True, cardw)
            draw_lines(cv, cx0, cy0 + 60, hlines, 14, 15, True, INK)
            dlines = wrap_text(deck, 10, False, cardw)
            draw_lines(cv, cx0, cy0 + 60 + 15 * len(hlines) + 2, dlines,
                       10, 11, False, INK_SOFT)
    y += 2 * cardh + 6
    cv.hline(MX, y, CW, (200, 192, 172), 1)
    y += 8
    # ---- map LEFT + ALSO list RIGHT
    mapw = 300
    maph = 168
    draw_text(cv, MX, y + 11, "WHERE IT HAPPENED — STORIES 1–13", 11, True,
              INK)
    draw_map(cv, MX, y + 16, mapw, maph - 16)
    draw_text(cv, MX, y + maph + 4,
              "Pins match story numbers 1–13; colours show region.", 9,
              False, INK_SOFT)
    ax = MX + mapw + 14
    aw = CW - mapw - 14
    draw_text(cv, ax, y + 11, "ALSO ON THURSDAY 26 NOVEMBER — 22 MORE STORIES",
              11, True, INK)
    colw = (aw - 2 * 12) // 3
    for ci in range(3):
        col_items = ALSO[ci * 8:(ci + 1) * 8] if ci < 2 else ALSO[16:]
        cxx = ax + ci * (colw + 12)
        for ri, item in enumerate(col_items):
            n = ci * 8 + ri + 1 if ci < 2 else 16 + ri + 1
            yy = y + 18 + ri * 20
            draw_text(cv, cxx, yy + 10, "%d." % n, 10, True, RED_DK)
            lines = wrap_text(item, 10, False, colw - 18)
            draw_lines(cv, cxx + 18, yy, lines[:2], 10, 11, False, INK)
    y += maph + 18
    # ---- DATE CHECK, red-bordered
    dc_top = y
    cv.rect(MX, y, CW, 2, RED, 2)
    draw_text(cv, MX + 8, y + 14, "DATE CHECK", 11, True, RED)
    draw_text(cv, MX + 96, y + 14,
              "Every story above happened or was first reported or developing "
              "on Thursday 26 November 2026 (UTC). Left out as earlier news:",
              9, False, INK_SOFT)
    dc_y = y + 20
    dccolw = (CW - 16 - 3 * 12) // 4
    for ci in range(4):
        col_items = DATE_CHECK[ci * 3:(ci + 1) * 3]
        cxx = MX + 8 + ci * (dccolw + 12)
        for ri, item in enumerate(col_items):
            n = ci * 3 + ri + 1
            yy = dc_y + ri * 21
            draw_text(cv, cxx, yy + 9, "%d." % n, 9, True, RED_DK)
            lines = wrap_text(item, 9, False, dccolw - 16)
            draw_lines(cv, cxx + 14, yy, lines[:2], 9, 11, False, INK)
    dc_y += 3 * 21 + 2
    # MORE row: +50% word spacing (space 2.0 -> 3.0px at 8px), leading 10 -> 11,
    # max width 960 -> 944 so no line ends near the right border; the 2px
    # saved in the gap above keeps the page bottom margin unchanged.
    mlines = wrap_text(MORE_CHECKED, 8, False, CW - 32, space_extra=1.0)
    draw_lines(cv, MX + 8, dc_y, mlines, 8, 11, False, INK_SOFT,
               space_extra=1.0)
    dc_bottom = dc_y + 11 * len(mlines) + 6
    cv.rect(MX, dc_top, CW, dc_bottom - dc_top, RED, 2)
    y = dc_bottom + 5  # v1.1: 6 -> 5, returns the 1px the MORE leading cost
    # ---- footer
    draw_text(cv, MX, y + 9,
              "OFFICIAL = authority’s own figure or act · REPORTED = press "
              "report · CLAIM = one side’s account. Drawn from verified "
              "reporting; every story first reported or developing Thu 26 Nov "
              "2026 unless dated in DATE CHECK.", 9, False, INK_SOFT)
    y += 12
    draw_text(cv, MX, y + 9,
              "Sources: Reuters, AP, BBC, CNN, Yonhap, TfL, FIDE, The Hindu, "
              "Guardian, Africanews", 9, False, INK_SOFT)
    y += 12
    return cv, y


def main():
    cv, final_y = build()
    print("final y:", final_y, "of", H)
    outdir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(outdir, exist_ok=True)
    path = os.path.join(outdir, "entry.png")
    data = png_bytes(cv)
    with open(path, "wb") as f:
        f.write(data)
    print("wrote", path, len(data), "bytes")


if __name__ == "__main__":
    main()
