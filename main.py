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
    # v1.7: 8 regions — ASIA-PACIFIC split EAST/SOUTH (3+3, verified by
    # city: Seoul/Hong Kong/Shanghai = East; Mumbai/Kathmandu/India =
    # South) and the UK split out of EUROPE (London/Liverpool/Top Gear are
    # unambiguously British; EUROPE keeps Kyiv/Brussels/ECB/Lille).
    # Totals still 35 (EAST 3 + SOUTH 3 + ME 5 + AM 9 + OC 3 + UK 3 +
    # EUROPE 4 + WORLD 5). v1.6 colours desaturated ~15% toward grey.
    ("EAST ASIA", 3, (58, 96, 135)),
    ("SOUTH ASIA", 3, (122, 88, 130)),
    ("MIDDLE EAST", 5, (171, 91, 45)),
    ("AMERICAS", 9, (123, 58, 53)),
    ("OCEANIA", 3, (55, 113, 111)),
    ("UK", 3, (158, 120, 50)),
    ("EUROPE", 4, (101, 113, 68)),
    ("WORLD", 5, (80, 79, 75)),
]
# v1.7: topic fields — the same 35 stories regrouped by subject (main-story
# fields are explicit in STORY-LIST.md kickers; ALSO items classified by
# subject: A1/A2/A4 ECONOMY, A3/A8/A9 CONFLICT, A5/A6/A7/A15/A16/A18
# SOCIETY, A10/A14 WORLD, A11/A17/A22 DISASTER, A12/A13/A19/A21 SPORT,
# A20 CULTURE). TRADE 1 + CONFLICT 5 + ECONOMY 6 + DISASTER 5 + SOCIETY 9
# + SPORT 5 + CULTURE 2 + WORLD 2 = 35.
FIELDS = [
    ("TRADE", 1), ("CONFLICT", 5), ("ECONOMY", 6), ("DISASTER", 5),
    ("SOCIETY", 9), ("SPORT", 5), ("CULTURE", 2), ("WORLD", 2),
]
# v1.7: chip backgrounds = region colour darkened x0.78 so white bold text
# keeps >=4:1 contrast (the plain bar colours are too light for the 8px
# chip label, esp. UK gold). ALSO numbers use these too.
CHIP_COLORS = {name: tuple(int(c * 0.78) for c in col)
               for (name, _, col) in REGION_COLORS}
# v1.6: balloon red, desaturated (was the largest saturated red block)
BALLOON_RED = (158, 46, 42)
BALLOON_DK = (128, 40, 36)
# v1.6: dark dot-matrix map — sea dark, land as region-coloured dots
# v1.8: MIDDLE EAST dot colour (warm orange, distinct from AMERICAS
# salmon and SOUTH ASIA purple); the map now colours it by lat/lon box
# (see draw_map) instead of leaving Arabia/Iran in SOUTH ASIA.
MAP_SEA = (36, 40, 48)
MAP_DOTS = {
    "AMERICAS": (198, 110, 96),
    "WORLD": (168, 162, 150),
    "EUROPE": (158, 172, 104),
    "EAST ASIA": (112, 158, 208),
    "SOUTH ASIA": (158, 124, 166),
    "MIDDLE EAST": (198, 124, 66),
    "UK": (200, 160, 90),
    "OCEANIA": (96, 178, 172),
}


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
        "deck": ("India 25%, Japan 15%, China & Vietnam 20% in some reports. "
                 "EU rejects the premise; Brazil calls it unacceptable; Asia "
                 "rebounds as levies look milder."),
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
     "vehicles charred; toll is preliminary. (AP)", "flame"),
    (5, "KYIV · CONFLICT", "REPORTED", "Ukraine hits 5 jets; Kyiv struck",
     "Savasleyka airbase hit — 3 MiG-31s, 2 Su-34s. Russia hits Kyiv "
     "shopping centre; 2 Samara refineries struck. (BBC)", "jet"),
    (6, "NEW YORK · ECONOMY", "REPORTED", "Nasdaq plunges, then recovers",
     "Wed close −0.6% at 23,586 after −4.6% intraday dive; Nasdaq-100 "
     "briefly −20% off record. Nvidia −3.9%. (AP, CNBC)", "chart"),
    (7, "LONDON · SOCIETY", "OFFICIAL", "Tube strike halts London",
     "RMT walkout from noon Thu to noon Fri; no Piccadilly or Circle all "
     "day, no service at all after 21:00. (TfL)", "train"),
    (8, "BRUSSELS · ECONOMY", "REPORTED", "EU fights over €45bn Ukraine loan",
     "Leaders meet Thu over a €1.58tn budget and Kyiv’s 2027 gap; deal "
     "aimed for 17–18 Dec. (Reuters, AP)", "flag"),
    (9, "MUMBAI · SOCIETY", "OFFICIAL", "India marks 18 years since 26/11",
     "166 killed in 2008; Mumbai on high alert as tributes are paid. "
     "Jaishankar: zero tolerance on terror. (IANS)", "candle"),
    (10, "GENEVA · SPORT", "OFFICIAL", "Gukesh–Sindarov: Game 3 today",
     "World title match level 1–1 after two draws. Sindarov has White; "
     "first to 7.5 points takes the $2.5m crown. (FIDE)", "chess"),
    (11, "SEOUL · ECONOMY", "OFFICIAL", "Bank of Korea lifts rate to 3.25%",
     "Up 25bp, the highest in two years; 2027 growth forecast raised to "
     "4.1%. (Yonhap, CNBC)", "bank"),
    (12, "HONG KONG · SOCIETY", "REPORTED",
     "Hong Kong marks year since fire killed 168",
     "Tai Po’s Wang Fuk Court, one year on. No official memorial; "
     "families still await full answers. (Japan Times, BBC)", "memorial"),
    (13, "KATHMANDU · DISASTER", "REPORTED",
     "Nepal: 213 Indians presumed dead",
     "Kathmandu begins declaring flood-missing Indians dead; embassy asks "
     "families to come forward. (The Hindu)", "flood"),
]

# v1.7: two-line coloured chips INSIDE each card's scene — (number, label,
# region). Number 13px bold, label 9px bold (v1.8: was 12/8px); both facts
# already in that card's deck/headline (STORY-LIST.md). Chip colour = the
# story's region (darkened, see CHIP_COLORS); the v1.6 black full-width
# band is gone.
# Regions: S4 ME, S5 EUROPE, S6 AMERICAS, S7 UK, S8 EUROPE, S9 SOUTH ASIA,
# S10 WORLD, S11 EAST ASIA, S12 EAST ASIA, S13 SOUTH ASIA.
CHIPS = {
    4: ("31", "DEAD", "MIDDLE EAST"),
    5: ("5", "JETS DOWNED", "EUROPE"),
    6: ("−4.6%", "THEN RECOVERED", "AMERICAS"),
    7: ("TUBE", "HALTED", "UK"),
    8: ("€45BN", "LOAN", "EUROPE"),
    9: ("18 YEARS", "SINCE 26/11", "SOUTH ASIA"),
    10: ("GAME 3", "1–1", "WORLD"),
    11: ("3.25%", "RATE", "EAST ASIA"),
    12: ("168", "DEAD", "EAST ASIA"),
    13: ("213", "PRESUMED DEAD", "SOUTH ASIA"),
}

# v1.8: per-card chip corner — default top-left (4,2). S13 goes
# top-right (99,2): the enlarged chip would otherwise cover the
# back-peak snow cap, which sits top-centre-left in the flood scene.
# 99 is the flush maximum: chip width 88px, scene width 187px, so the
# chip ends exactly at the scene's right edge (the page's right margin —
# S13 is the last column, no card to its right).
CHIP_POS = {13: (99, 2)}

# v1.7: (text, region, outlet) — region from the STORY-LIST.md tag
# (EU bucket split UK/EUROPE as in REGION_COLORS: Liverpool + Top Gear are
# British, Lille/Bayern + ECB stay EUROPE); outlet = first-listed source
# for that item in RESEARCH.md (all 22 verified there).
ALSO = [
    ("Asia rebounds: Nikkei +1.6% as tariffs look milder; Shanghai −2.1%", "EAST ASIA", "CNBC"),
    ("Brent $94.61 (+3.5%); WTI $83.68 (+2%) as Gulf fears lift oil", "WORLD", "Reuters"),
    ("Trump, Rutte urge Russia not to widen the war (Mar-a-Lago talks)", "AMERICAS", "Reuters"),
    ("ECB: Pablo Hernandez de Cos set to succeed Lagarde", "EUROPE", "Rapporteur"),
    ("Abrego Garcia reaches Spain after a 20-month US legal fight", "AMERICAS", "Euronews"),
    ("Brazil withdraws ambassador to Argentina for good", "AMERICAS", "MercoPress"),
    ("Hasina return dispute: India separates return from extradition", "SOUTH ASIA", "The Hindu"),
    ("ISIL suicide attack kills 2 in Hasakah, Syria", "MIDDLE EAST", "Al Jazeera"),
    ("Somalia: foreign troops withdraw; Uganda steps up anti-al-Shabaab fight", "MIDDLE EAST", "BBC"),
    ("Australia projected to miss its 2035 emissions target", "OCEANIA", "Guardian"),
    ("Flinders Island fire destroys at least 6 homes", "OCEANIA", "Guardian"),
    ("Liverpool beat Club Brugge 3–0 in the Champions League", "UK", "BBC"),
    ("Lille beat Bayern 2–1, ending their unbeaten run", "EUROPE", "BBC"),
    ("Rare lakes found beneath the Red Sea", "WORLD", "ScienceDaily"),
    ("Canadian astronaut welcomes a baby girl from orbit", "WORLD", "BBC"),
    ("Pig-kidney patient marks one year off dialysis", "AMERICAS", "CBC"),
    ("Famine risk falls in Baidoa, Somalia — but hunger persists", "MIDDLE EAST", "AllAfrica"),
    ("US Army calls Iowa 5-ton blast a 'huge success'", "AMERICAS", "BBC"),
    ("Kurtley Beale returns to the Wallabies after five years", "OCEANIA", "ABC"),
    ("Gordon Ramsay to host revived Top Gear", "UK", "BBC"),
    ("U-17 World Cup: Egypt 4–1 Panama; Uganda 6–0 New Caledonia", "WORLD", "Africanews"),
    ("King tides flood the California coast as storms hit Thanksgiving travel", "AMERICAS", "Guardian"),
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


def draw_chip(cv, x, y, num, lab, region):
    """v1.8 two-line coloured chip inside a scene: number 13px bold over
    label 9px bold, white on the story's darkened region colour, 1px paper
    border. 23px tall. v1.7 was 12/8px (21px) — the numbers were ~2.5px
    at thumbnail. Returns the chip width."""
    col = CHIP_COLORS[region]
    w = max(int(text_width(num, 13, True)),
            int(text_width(lab, 9, True))) + 10
    cv.fill_rect(x, y, w, 23, col)
    cv.rect(x, y, w, 23, PAPER, 1)
    draw_text(cv, x + 5, y + 12, num, 13, True, (255, 255, 255))
    draw_text(cv, x + 5, y + 21, lab, 9, True, (255, 255, 255))
    return w


# ---- schematic scenes for the three leads (drawn in code, flat vector)
def scene_tariffs(cv, x, y, w, h):
    # v1.5: clean chart panel as the focus — the container ship crowded the
    # chart and told the wrong story, so it is dropped; 3 proportional bars
    # (India 25 red, Japan 15 gold, China 20 blue) carry the tariff story
    cv.fill_rect(x, y, w, h, (238, 232, 216))
    cv.fill_rect(x, y + h - 16, w, 16, (214, 226, 236))
    base = y + h - 16
    # v1.9: 4 bars — Vietnam 20% added (RESEARCH.md: "China and Vietnam
    # 20%"; the deck now says "China & Vietnam 20%"). Narrower bars
    # (34/18) so all four fit; the v1.8 3-bar chart left the hero's
    # top-right empty and carried one fewer verified number than the
    # top entries' heroes.
    bars = [("INDIA", 25, RED), ("JAPAN", 15, GOLD), ("CHINA", 20, BLUE),
            ("VIETNAM", 20, BLUE)]
    bw, gap = 34, 18
    bx = x + 118 + (200 - (4 * bw + 3 * gap)) // 2
    for i, (lab, val, col) in enumerate(bars):
        bh = int(val * 1.28)
        xx = bx + i * (bw + gap)
        cv.fill_rect(xx, base - bh, bw, bh, col)
        cv.rect(xx, base - bh, bw, bh, INK, 1)
        draw_text(cv, xx + bw // 2, base - bh - 4, "%d%%" % val, 11, True,
                  INK, "c")
        draw_text(cv, xx + bw // 2, base + 12, lab, 8, True, INK, "c")
    cv.fill_rect(bx - 8, y + 20, 3, base - y - 20, INK)  # vertical axis
    cv.fill_rect(x, base, w, 3, INK)  # baseline
    cv.fill_rect(x + 4, y + 4, 96, 15, INK)
    draw_text(cv, x + 8, y + 15, "USTR PROPOSAL", 9, True, (255, 255, 255))


def scene_refinery(cv, x, y, w, h):
    # dusk bands
    cv.fill_rect(x, y, w, 26, (226, 148, 74))
    cv.fill_rect(x, y + 26, w, 26, (198, 96, 52))
    cv.fill_rect(x, y + 52, w, h - 52, (74, 48, 52))
    # v1.5: clearer structures — distillation tower (left), storage tanks
    # (mid), flare stack with flame (right), second stack, connecting pipe,
    # and TWO rising smoke columns (v1.4 lesson: vertical, narrow dark
    # root, widening and paling upward, no whole discs, no horizontal blob)
    # smoke plume A over the mid vent stack, drifting left — v1.5 fix:
    # lumpy rx (6,8,6,9,7,10,8) so the silhouette edge waves instead of
    # reading as a straight grey bar; wider max rx for a billowing column
    # v1.9: plume A shifted +12px right (with its vent stack) — the
    # v1.8 plume's left sliver (x+136..148) hid behind the "4 DRONES
    # DOWNED" chip's right edge (ends x+146); now clears it by 2px
    # and still clears the BRENT chip's left edge (x+170) by 2px.
    for (sx, sy, rx, ry, col) in [(162, 44, 6, 4, (98, 94, 88)),
                                  (160, 38, 8, 5, (104, 100, 94)),
                                  (162, 32, 6, 5, (112, 108, 102)),
                                  (159, 26, 9, 5, (120, 116, 110)),
                                  (161, 20, 7, 5, (128, 124, 118)),
                                  (158, 14, 10, 5, (138, 134, 128)),
                                  (159, 8, 8, 4, (148, 144, 138)),
                                  (157, 4, 7, 3, (156, 152, 146))]:
        cv.fill_ellipse(x + sx, y + sy, rx, ry, col)
    # smoke plume B over the second stack, drifting right
    for (sx, sy, rx, ry, col) in [(264, 30, 6, 4, (98, 94, 88)),
                                  (266, 24, 8, 4, (106, 102, 96)),
                                  (264, 18, 6, 5, (114, 110, 104)),
                                  (267, 12, 9, 5, (124, 120, 114)),
                                  (265, 6, 8, 4, (134, 130, 124))]:
        cv.fill_ellipse(x + sx, y + sy, rx, ry, col)
    # distillation tower with platforms — v1.9: top at y+20 (was y+16):
    # the v1.8 tower's top 3px hid behind the "550,000 BPD" chip
    # (chip bottom y+19, tower top y+16); invisible (both near-black)
    # but a real overlap, now 1px clear.
    cv.fill_rect(x + 18, y + 20, 14, h - 20, (38, 34, 36))
    for py in (26, 36, 46):
        cv.fill_rect(x + 14, y + py, 22, 2, (120, 116, 110))
    # mid vent stack — v1.9: moved +12px with plume A (see above)
    cv.fill_rect(x + 160, y + 44, 5, h - 44, (38, 34, 36))
    # storage tanks with highlight bands
    cv.fill_circle(x + 88, y + h - 14, 13, (52, 46, 48))
    cv.fill_circle(x + 116, y + h - 12, 11, (52, 46, 48))
    cv.fill_rect(x + 81, y + h - 22, 14, 2, (120, 116, 110))
    cv.fill_rect(x + 110, y + h - 20, 12, 2, (120, 116, 110))
    # flare stack + flame
    cv.fill_rect(x + 206, y + 20, 8, h - 20, (38, 34, 36))
    fx, fy = x + 210, y + 20
    cv.fill_poly([(fx - 6, fy), (fx, fy - 14), (fx + 6, fy)], (232, 120, 30))
    cv.fill_poly([(fx - 3, fy), (fx, fy - 8), (fx + 3, fy)], (250, 205, 80))
    # second stack (feeds plume B)
    cv.fill_rect(x + 260, y + 30, 8, h - 30, (38, 34, 36))
    # connecting pipe, tower -> tanks
    cv.fill_rect(x + 32, y + h - 24, 44, 3, (38, 34, 36))
    cv.fill_rect(x + 4, y + 4, 104, 15, INK)
    draw_text(cv, x + 8, y + 15, "550,000 BPD", 9, True, (255, 255, 255))
    # v1.6: visible in-scene data — Brent move (mid band, right of the vent
    # stack; the first placement at y+6 hid the flare flame, so it sits
    # below it now) and drones downed (mid band, between tower and tanks);
    # both facts are already in this lead's deck, now visible without
    # reading the deck
    cv.fill_rect(x + 170, y + 24, 88, 15, INK)
    draw_text(cv, x + 174, y + 35, "BRENT +3.5%", 9, True, (255, 255, 255))
    cv.fill_rect(x + 40, y + 26, 106, 15, INK)
    draw_text(cv, x + 44, y + 37, "4 DRONES DOWNED", 9, True,
              (255, 255, 255))


def scene_parade(cv, x, y, w, h):
    # storm sky bands
    cv.fill_rect(x, y, w, 30, (96, 104, 116))
    cv.fill_rect(x, y + 30, w, 26, (72, 80, 92))
    cv.fill_rect(x, y + 56, w, h - 56, (52, 58, 66))
    # wind-driven rain, slanted hard sideways
    for rx in range(14, w, 26):
        for ry in range(6, 52, 14):
            cv.line(x + rx, y + ry, x + rx - 9, y + ry + 6, (200, 206, 214))
    # wind streaks — v1.7: thicker (2 -> 3px) and longer, the wind reads
    for (sx, sy, ln) in [(120, 12, 80), (220, 22, 80), (30, 46, 70)]:
        cv.fill_rect(x + sx, y + sy, ln, 3, (220, 226, 232))
    # Manhattan skyline, low background only (not the main motif)
    heights = [16, 24, 18, 28, 14, 22, 26, 18, 20, 14]
    bx = x + 8
    for i, hh in enumerate(heights):
        cv.fill_rect(bx + i * 30, y + h - hh, 24, hh, (26, 24, 20))
        for wy in range(5, hh - 4, 10):
            cv.fill_rect(bx + i * 30 + 5, y + h - hh + wy, 3, 4,
                         (250, 205, 80))
    # big balloon, tilted by the wind (top leaning right) — the parade
    # motif. v1.5 fix: rounder (rx 40, ry 26) — the first version was so
    # flat (48x20) it read as a leaf/disc, not a balloon.
    # v1.6: shrunk (rx 30, ry 20) and desaturated — it was the largest
    # saturated red block in the hero and read as decoration, not data
    # v1.7: centre moved right (170 -> 185) so the new red label bar at the
    # left does not cut into the balloon's lower-left edge
    bcx, bcy = x + 185, y + 30
    t = 0.28
    ct, st = _cos(t), _sin(t)
    pts = []
    for k in range(28):
        a = k * 2 * 3.14159265 / 28.0
        ca, sa = _cos(a), _sin(a)
        px = bcx + 30 * ca * ct - 20 * sa * st
        py = bcy + 30 * ca * st + 20 * sa * ct
        pts.append((int(round(px)), int(round(py))))
    cv.fill_poly(pts, BALLOON_RED)
    # darker fold band across the balloon belly
    pts2 = []
    for k in range(28):
        a = k * 2 * 3.14159265 / 28.0
        ca, sa = _cos(a), _sin(a)
        px = bcx + 4 + 21 * ca * ct - 7 * sa * st
        py = bcy + 10 + 21 * ca * st + 7 * sa * ct
        pts2.append((int(round(px)), int(round(py))))
    cv.fill_poly(pts2, BALLOON_DK)
    # v1.8: balloon volume — a pale sheen on the upper-left + two panel
    # seams following the tilt. The v1.7 balloon was a flat red oval; the
    # top entries' hero scenes carry layered detail, and the sheen is the
    # cheapest way to give the balloon depth without new facts.
    cv.fill_ellipse(bcx - 12, bcy - 10, 9, 5, (205, 105, 92))
    stroke3(cv, [(bcx - 10, bcy - 17), (bcx - 12, bcy),
                 (bcx - 10, bcy + 17)], BALLOON_DK)
    stroke3(cv, [(bcx + 8, bcy - 16), (bcx + 10, bcy + 1),
                 (bcx + 8, bcy + 17)], BALLOON_DK)
    # ropes trailing down-left from the balloon (kept inside the scene box)
    cv.line(bcx - 20, bcy + 13, bcx - 32, bcy + 30, (26, 24, 20))
    cv.line(bcx + 14, bcy + 14, bcx + 5, bcy + 32, (26, 24, 20))
    # confetti blown sideways
    for (ccx, ccy, col) in [(230, 10, GOLD), (250, 16, (250, 205, 80)),
                            (280, 12, BLUE), (300, 20, (248, 244, 233)),
                            (270, 30, GOLD), (300, 34, (250, 205, 80)),
                            (240, 40, RED), (130, 44, GOLD),
                            (100, 50, RED), (290, 46, BLUE)]:
        cv.fill_rect(x + ccx, y + ccy, 5, 2, col)
    # parade float (platform + flags) bottom right
    cv.fill_rect(x + 238, y + h - 12, 64, 8, (26, 24, 20))
    cv.fill_rect(x + 244, y + h - 26, 3, 14, (26, 24, 20))
    cv.fill_poly([(x + 247, y + h - 26), (x + 259, y + h - 23),
                  (x + 247, y + h - 20)], RED)
    cv.fill_rect(x + 286, y + h - 26, 3, 14, (26, 24, 20))
    cv.fill_poly([(x + 289, y + h - 26), (x + 301, y + h - 23),
                  (x + 289, y + h - 20)], GOLD)
    # v1.6: the old small "100TH · SAT 08:30" chip becomes visible data —
    # a big "100TH" badge + "SAT 08:30" on the sky, and a "GUSTS 60 MPH"
    # chip top-right (both facts already in this lead's deck)
    draw_text(cv, x + 8, y + 28, "100TH", 22, True, (255, 255, 255))
    cv.fill_rect(x + w - 96, y + 4, 92, 15, INK)
    draw_text(cv, x + w - 92, y + 15, "GUSTS 60 MPH", 9, True,
              (255, 255, 255))
    # v1.7: red in-scene label bar (tidy-meteor's "RAS TANURA HIT" trick) —
    # the postponement + the new time in one bar; "SAT 08:30" moves here
    # from its old spot (same words, same facts). Drawn after the ropes so
    # it sits cleanly on top; the balloon's left edge is behind it.
    bar_txt = "PARADE POSTPONED — SAT 08:30"
    bw = int(text_width(bar_txt, 9, True)) + 12
    cv.fill_rect(x + 8, y + 32, bw, 14, RED)
    draw_text(cv, x + 14, y + 43, bar_txt, 9, True, (255, 255, 255))


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
        # v1.5: road fuel tanker with fire + smoke on a highway
        cv.fill_rect(x, cy + 13, w, 6, (38, 34, 36))  # road band
        cv.fill_rect(x, cy + 15, w, 1, (248, 244, 233))  # centre line
        # smoke puffs rising from the flame (inside the box)
        cv.fill_ellipse(cx - 31, cy - 12, 3, 2, (120, 116, 110))
        cv.fill_ellipse(cx - 30, cy - 15, 3, 2, (140, 136, 130))
        cv.fill_ellipse(cx - 28, cy - 17, 2, 1, (158, 154, 148))
        # flame over the tank (smaller than v1.2 so the smoke fits above)
        cv.fill_poly([(cx - 40, cy + 1), (cx - 36, cy - 8), (cx - 32, cy - 4),
                      (cx - 28, cy - 10), (cx - 22, cy + 1)], (232, 120, 30))
        cv.fill_poly([(cx - 35, cy + 1), (cx - 32, cy - 5), (cx - 28, cy + 1)],
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
        # v1.8: speed lines shifted +2px — the taller v1.8 chip's bottom
        # edge grazed the top line's top edge
        for sy in (cy - 4, cy + 3, cy + 10):
            cv.fill_rect(cx - 72, sy - 1, 16, 3, (38, 42, 48))
        # strike burst ON the jet (the Kyiv strike) — v1.9: centre moved
        # from the nose tip (cx+64) to the fuselage (cx+8): the v1.8
        # burst sat past the nose and read as the jet firing forward,
        # not being hit. The gold cockpit (cx+24) stays clear of it.
        bx, by = cx + 8, cy + 1
        burst = []
        for k in range(12):
            a = k * 3.14159265 / 6.0
            r = 9 if k % 2 == 0 else 4
            burst.append((bx + int(round(r * _cos(a))),
                          by + int(round(r * _sin(a)))))
        cv.fill_poly(burst, (232, 120, 30))
        cv.fill_circle(bx, by, 3, (250, 205, 80))
    elif key == "chart":
        # v1.5: axes + bars + a line that PLUNGES then RECOVERS (V / dip and
        # rise) — v1.2 only rose, which was wrong for the Nasdaq story.
        # v1.8: the whole chart sits 10px lower (cy+10) — the v1.7 chip
        # covered the Y-axis top and the V-line's first (dip) point; the
        # axis top now clears the chip bottom by 2px, and the baseline
        # still sits 7px above the scene floor.
        cy = cy + 10
        cv.fill_rect(cx - 70, cy - 13, 3, 26, INK)
        cv.fill_rect(cx - 70, cy + 10, 140, 3, INK)
        cv.fill_rect(cx - 58, cy - 4, 12, 14, BLUE)
        cv.fill_rect(cx - 40, cy + 5, 12, 5, GOLD)
        cv.fill_rect(cx - 22, cy - 6, 12, 16, BLUE)
        pts = [(cx - 58, cy - 12), (cx - 36, cy + 6), (cx - 14, cy - 4),
               (cx + 8, cy - 12), (cx + 36, cy - 16)]
        stroke3(cv, pts, RED)
        cv.fill_poly([(cx + 38, cy - 17), (cx + 26, cy - 15), (cx + 34, cy - 7)],
                     RED)
    elif key == "train":
        # v1.5: subway front view + London Underground roundel (left) and a
        # closed crossing barrier (right) — the strike halting service
        # roundel: paper ring, red disc, blue bar (shapes, no text)
        # v1.8: centre cy-2 -> cy+5 — the v1.7 chip clipped the ring's top
        # (4px; 6px with the taller v1.8 chip); the ring top now clears
        # the chip bottom by 1px and its base still clears the track line
        ry = cy + 5
        cv.fill_circle(cx - 56, ry, 9, (248, 244, 233))
        cv.fill_circle(cx - 56, ry, 6, RED)
        cv.fill_rect(cx - 68, ry - 2, 24, 4, BLUE)
        # train body
        cv.fill_rect(cx - 26, cy - 14, 52, 28, (248, 244, 233))
        cv.rect(cx - 26, cy - 14, 52, 28, INK, 3)
        cv.fill_rect(cx - 20, cy - 9, 16, 9, BLUE)
        cv.fill_rect(cx + 4, cy - 9, 16, 9, BLUE)
        cv.fill_rect(cx - 1, cy - 9, 3, 9, INK)
        cv.fill_rect(cx - 20, cy + 2, 40, 3, GOLD)
        cv.fill_circle(cx - 16, cy + 9, 3, GOLD)
        cv.fill_circle(cx + 16, cy + 9, 3, GOLD)
        cv.fill_rect(cx - 34, cy + 16, 68, 3, INK)
        # closed barrier across the track, right of the train
        cv.fill_rect(cx + 40, cy + 6, 3, 10, INK)
        cv.fill_rect(cx + 66, cy + 6, 3, 10, INK)
        for i in range(5):
            col = (248, 244, 233) if i % 2 == 0 else INK
            cv.fill_rect(cx + 43 + i * 5, cy + 8, 5, 4, col)
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
        # balance scale (loan negotiation) right of the document
        cv.fill_rect(cx + 52, cy - 10, 3, 22, INK)
        cv.fill_rect(cx + 38, cy - 10, 30, 3, INK)
        cv.fill_rect(cx + 48, cy + 12, 8, 3, INK)
        cv.line(cx + 38, cy - 7, cx + 40, cy - 1, INK)
        cv.line(cx + 68, cy - 7, cx + 66, cy - 1, INK)
        cv.fill_poly([(cx + 36, cy - 1), (cx + 44, cy - 1), (cx + 40, cy + 5)],
                     GOLD)
        cv.fill_poly([(cx + 62, cy - 1), (cx + 70, cy - 1), (cx + 66, cy + 5)],
                     GOLD)
    elif key == "candle":
        # v1.5: solemn memorial wreath with REAL leaf shapes (v1.2 leaves
        # were 2px dots that read as beads) + flame, Mumbai
        for k in range(12):
            a = k * 30.0 * 3.14159265 / 180.0
            lx = cx + int(round(13 * _cos(a)))
            ly = cy + 2 + int(round(13 * _sin(a)))
            # leaf: pointed diamond, long axis tangent to the ring
            tx, ty = -_sin(a), _cos(a)
            rx, ry = _cos(a), _sin(a)
            cv.fill_poly([(int(round(lx + tx * 4)), int(round(ly + ty * 4))),
                          (int(round(lx + rx * 2)), int(round(ly + ry * 2))),
                          (int(round(lx - tx * 4)), int(round(ly - ty * 4))),
                          (int(round(lx - rx * 2)), int(round(ly - ry * 2)))],
                         GOLD)
        for k in range(6):
            a = (15.0 + k * 60.0) * 3.14159265 / 180.0
            cv.fill_circle(cx + int(round(13 * _cos(a))),
                           cy + 2 + int(round(13 * _sin(a))), 1, RED)
        cv.fill_poly([(cx - 6, cy - 2), (cx - 3, cy - 13), (cx, cy - 6),
                      (cx + 3, cy - 16), (cx + 7, cy - 2)], (232, 120, 30))
        cv.fill_poly([(cx - 3, cy - 2), (cx, cy - 8), (cx + 3, cy - 2)],
                     (250, 205, 80))
    elif key == "memorial":
        # v1.5: high-rise on fire + "168" toll plaque (memorial, distinct
        # from the Mumbai wreath); keeps the v1.1 "168" plaque text
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
        # v1.5: fire on the second tower's roof (the Hong Kong fire) —
        # the v1.2 warning triangle is removed (awkward/confusing symbol)
        cv.fill_poly([(cx + 3, cy - 6), (cx + 6, cy - 16), (cx + 9, cy - 11),
                      (cx + 12, cy - 18), (cx + 15, cy - 6)], (232, 120, 30))
        cv.fill_poly([(cx + 6, cy - 6), (cx + 8, cy - 12), (cx + 10, cy - 6)],
                     (250, 205, 80))
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
        # chessboard 3x3 at the right (the world title match)
        cv.rect(cx + 32, cy - 12, 26, 26, INK, 2)
        for r in range(3):
            for c in range(3):
                col = INK if (r + c) % 2 == 0 else (248, 244, 233)
                cv.fill_rect(cx + 34 + c * 8, cy - 10 + r * 8, 8, 8, col)
    elif key == "bank":
        # classical bank (ink, high contrast) + red rising-rate arrow
        cv.fill_poly([(cx - 34, cy - 4), (cx - 6, cy - 15), (cx + 22, cy - 4)],
                     INK)
        cv.fill_rect(cx - 32, cy - 4, 52, 3, INK)
        for colx in (cx - 30, cx - 18, cx - 6, cx + 6):
            cv.fill_rect(colx, cy, 5, 11, INK)
        cv.fill_rect(cx - 34, cy + 11, 56, 3, INK)
        cv.fill_rect(cx - 36, cy + 14, 60, 3, INK)
        # v1.5: stepped rising-rate line right of the bank (the rate hike)
        stroke3(cv, [(cx + 30, cy + 6), (cx + 30, cy - 2), (cx + 42, cy - 2),
                     (cx + 42, cy - 10), (cx + 54, cy - 10)], RED)
        cv.fill_poly([(cx + 62, cy - 10), (cx + 52, cy - 15),
                      (cx + 52, cy - 5)], RED)
    elif key == "flood":
        # v1.9: whole motif +2px down — the v1.8 front peak's snow apex
        # (917,596) touched the S13 chip's paper bottom border row
        # (y=596); same colour so invisible, but a real touch. Now the
        # apex sits at y=598, 1px clear of the chip.
        cy = cy + 2
        # v1.5: layered mountain terrain (three ridges) + rescue cross —
        # the front ridge makes the disaster terrain read, not just triangles
        cv.fill_poly([(cx - 52, cy + 14), (cx - 14, cy - 14), (cx + 18, cy + 14)],
                     SLATE)
        cv.fill_poly([(cx - 14, cy - 14), (cx - 19, cy - 6), (cx - 9, cy - 6)],
                     (248, 244, 233))
        cv.fill_poly([(cx - 16, cy + 14), (cx + 12, cy - 6), (cx + 38, cy + 14)],
                     INK)
        cv.fill_poly([(cx + 12, cy - 6), (cx + 7, cy), (cx + 17, cy)],
                     (248, 244, 233))
        cv.fill_poly([(cx - 52, cy + 14), (cx - 30, cy + 4), (cx - 8, cy + 14),
                      (cx + 12, cy + 8), (cx + 30, cy + 14)], (72, 66, 60))
        cv.fill_circle(cx + 44, cy + 6, 9, (255, 255, 255))
        cv.fill_rect(cx + 43, cy - 1, 3, 14, RED)
        cv.fill_rect(cx + 37, cy + 5, 14, 3, RED)


def blit_scaled(cv, src, x, y, w, h):
    """Copy src canvas scaled to (w, h) at (x, y) with a box-average
    downsample — flat vector art stays crisp, no nearest-neighbour crunch.
    Used v1.6 to shrink the v1.5 spot icons so the data chip fits."""
    sw, sh = src.w, src.h
    for yy in range(h):
        y0 = yy * sh // h
        y1 = max(y0 + 1, (yy + 1) * sh // h)
        for xx in range(w):
            x0 = xx * sw // w
            x1 = max(x0 + 1, (xx + 1) * sw // w)
            r = g = b = n = 0
            for sy in range(y0, y1):
                base = (sy * sw + x0) * 3
                for sx in range(x0, x1):
                    i = base + (sx - x0) * 3
                    r += src.px[i]
                    g += src.px[i + 1]
                    b += src.px[i + 2]
                    n += 1
            cv.set_px(x + xx, y + yy, (r // n, g // n, b // n))


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
    # v1.6: dark dot-matrix — land as region-coloured dots on a dark sea
    # (the v1.5 beige land was the lowest-contrast element on the page;
    # the top entries use a dark map). Pins numbered 1-13 unchanged.
    cv.fill_rect(x, y, w, h, MAP_SEA)
    cv.rect(x, y, w, h, INK, 1)

    def proj(lon, lat):
        px = x + (lon + 168.0) / 358.0 * w
        py = y + (78.0 - lat) / 136.0 * h
        return (px, py)

    # continent -> region colour (North+South America = AMERICAS, Africa =
    # WORLD except Egypt = MIDDLE EAST, Europe = UK / EUROPE by lat/lon
    # box, Asia = MIDDLE EAST / SOUTH ASIA / EAST ASIA by lat/lon box,
    # Australia = OCEANIA).
    # v1.8: the v1.7 pure-longitude splits were schematic-wrong — Ireland
    # and Iberia read UK-gold (both are EU members, so EUROPE green is
    # correct there) and Arabia/Iran/Central Asia read SOUTH ASIA purple.
    # v1.9: ME/SA boundary lon 63 (was 66/60 — the overlap zone
    # lon 60..66, lat 12..38, i.e. western Pakistan/Balochistan,
    # read MIDDLE EAST orange; the Iran/Pakistan border is ~lon 63,
    # so lon <63 stays ME, lon >=63 is SOUTH ASIA).
    # Box rules now: UK = Great Britain (lon -6..2, lat >= 50) or
    # Northern Ireland (lon -8..-5, lat 54..55.5); MIDDLE EAST =
    # lon 26..63, lat 12..42 (Turkey south, Levant, Arabia, Iraq, Iran);
    # SOUTH ASIA = lon 63..100, lat 5..38 (Pakistan, India, Nepal,
    # Bangladesh, Sri Lanka); the rest of Asia = EAST ASIA. Pins are
    # still placed by exact lon/lat and fall on the right side —
    # Mumbai/Kathmandu west, Seoul/Hong Kong east; London west, Kyiv/
    # Brussels east.
    map_regions = ["AMERICAS", "AMERICAS", "WORLD", "EUROPE", "ASIA",
                   "OCEANIA"]
    polys = [[proj(lon, lat) for (lon, lat) in cont] for cont in CONTINENTS]

    def inside(px, py, poly):
        n = len(poly)
        ok = False
        for i in range(n):
            x0, y0 = poly[i]
            x1, y1 = poly[(i + 1) % n]
            if (y0 > py) != (y1 > py):
                xin = x0 + (py - y0) * (x1 - x0) / (y1 - y0)
                if px < xin:
                    ok = not ok
        return ok

    for gy in range(y + 3, y + h - 2, 6):
        for gx in range(x + 3, x + w - 2, 6):
            for ci, poly in enumerate(polys):
                if inside(gx, gy, poly):
                    reg = map_regions[ci]
                    lon = (gx - x) / float(w) * 358.0 - 168.0
                    lat = 78.0 - (gy - y) / float(h) * 136.0
                    if ci == 2:  # Africa: Egypt reads MIDDLE EAST
                        if 25 <= lon <= 36 and 22 <= lat <= 32:
                            reg = "MIDDLE EAST"
                    elif ci == 3:  # Europe: UK / EUROPE by lat/lon box
                        reg = "UK" if (lat >= 50 and -6 <= lon < 2) or \
                            (54 <= lat <= 55.5 and -8 <= lon <= -5) \
                            else "EUROPE"
                    elif ci == 4:  # Asia: MIDDLE EAST / SOUTH / EAST
                        if 26 <= lon <= 63 and 12 <= lat <= 42:
                            reg = "MIDDLE EAST"
                        elif 63 <= lon <= 100 and 5 <= lat < 38:
                            reg = "SOUTH ASIA"
                        else:
                            reg = "EAST ASIA"
                    cv.fill_circle(gx, gy, 2, MAP_DOTS[reg])
                    break
    for (num, lon, lat, dx, dy) in PINS:
        px, py = proj(lon, lat)
        lx, ly = int(px + dx), int(py + dy)
        cv.line(int(px), int(py), lx, ly, RED)
        cv.fill_circle(int(px), int(py), 2, (255, 255, 255))
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
    draw_text(cv, MX + CW, y + 11, "35 STORIES · 8 REGIONS · THURSDAY 26 NOVEMBER 2026",
              11, True, INK, "r")
    y += 13
    cv.hline(MX, y, CW, RULE, 2)
    y += 6
    # masthead
    draw_text(cv, MX + CW // 2, y + 44, "Thursday 26 November 2026", 52, True,
              INK, "c")
    y += 51
    # red deck line: the three leads in one line
    draw_text(cv, MX + CW // 2, y + 12,
              "US proposes tariffs on 14 partners · Houthis claim Ras Tanura "
              "refinery hit · Macy’s 100th parade postponed",
              13, True, RED, "c")
    y += 16
    cv.hline(MX, y, CW, RULE, 1)
    y += 5
    # stat strip: 6 callouts — v1.7: values 22 -> 32px (top-10 median
    # 32-35px; ours were the smallest stat numbers in the set)
    sw = CW // 6
    for i, (val, lab) in enumerate(STATS):
        bx = MX + i * sw
        if i:
            cv.vline(bx, y + 6, 44, (200, 192, 172), 1)
        draw_text(cv, bx + sw // 2, y + 31, val, 32, True, RED_DK, "c")
        draw_text(cv, bx + sw // 2, y + 46, lab, 9, True, INK_SOFT, "c")
    y += 52
    cv.hline(MX, y, CW, RULE, 1)
    y += 4
    # region bar: segments proportional to story counts (must total 35) —
    # v1.7: 8 segments; the last takes the remainder so rounding never
    # overshoots the 976px content width by a pixel
    total = sum(c for (_, c, _) in REGION_COLORS)
    assert total == 35, total
    rx = MX
    for si, (name, count, col) in enumerate(REGION_COLORS):
        seg = int(round(CW * count / 35.0)) if si < len(REGION_COLORS) - 1 \
            else MX + CW - rx
        cv.fill_rect(rx, y, seg, 20, col)
        draw_text(cv, rx + seg // 2, y + 14, "%s %d" % (name, count), 10,
                  True, (255, 255, 255), "c")
        rx += seg
    y += 20
    # v1.7: FIELDS strip — the same 35 stories by topic (see FIELDS above),
    # the taxonomy strip the top entries carry (hwang-steven 21 fields,
    # tidy-meteor 20 fields + 8 stats). One thin PAPER_DIM band.
    cv.fill_rect(MX, y, CW, 16, PAPER_DIM)
    fields_txt = "FIELDS   " + "  ·  ".join("%s %d" % (n, c)
                                            for (n, c) in FIELDS)
    draw_text(cv, MX + CW // 2, y + 12, fields_txt, 9, True, INK, "c")
    y += 18
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
        SCENES[lead["scene"]](cv, lx, y + 16, lw, 64)
        hy = y + 16 + 64 + 6
        lines = wrap_text(lead["head"], 20, True, lw)
        draw_lines(cv, lx, hy, lines, 20, 21, True, INK)
        dy = hy + 21 * len(lines) + 2
        dlines = wrap_text(lead["deck"], 11, False, lw)
        draw_lines(cv, lx, dy, dlines, 11, 12, False, INK_SOFT)
        my = dy + 12 * len(dlines) + 8
        draw_text(cv, lx, my, lead["meta"], 9, False, INK_SOFT)
    y = lead_top + 16 + 64 + 6 + 2 * 21 + 2 + 3 * 12 + 8 + 5
    cv.hline(MX, y, CW, (200, 192, 172), 1)
    y += 6
    # ---- small cards: 5 across x 2 rows
    # v1.7: each card is a mini-scene — the v1.5 illustration is drawn
    # natively into a 187x60 scene box (same absolute motif size as v1.5,
    # centred, edges crisp, no scaling), with the two-line coloured chip
    # INSIDE the scene's top-left corner (the v1.6 black full-width band is
    # gone). Kicker/headline/deck keep the v1.6 geometry below the scene.
    cardw = (CW - 4 * 10) // 5
    cardh = 144
    for row in range(2):
        for col in range(5):
            idx = row * 5 + col
            num, kick, pill, head, deck, icon = SMALL[idx]
            cx0 = MX + col * (cardw + 10)
            cy0 = y + row * (cardh + 4)
            draw_icon(cv, cx0, cy0, cardw, 60, icon)
            cn, cl, creg = CHIPS[num]
            cdx, cdy = CHIP_POS.get(num, (4, 2))
            draw_chip(cv, cx0 + cdx, cy0 + cdy, cn, cl, creg)
            draw_text(cv, cx0, cy0 + 68, "%d · %s" % (num, kick), 9, True,
                      RED_DK)
            pw = draw_pill(cv, cx0 + cardw - 58, cy0 + 60, pill)
            hlines = wrap_text(head, 14, True, cardw)
            draw_lines(cv, cx0, cy0 + 76, hlines, 14, 15, True, INK)
            dlines = wrap_text(deck, 11, False, cardw)
            draw_lines(cv, cx0, cy0 + 76 + 15 * len(hlines) + 2, dlines,
                       11, 12, False, INK_SOFT)
    y += 2 * cardh + 4
    cv.hline(MX, y, CW, (200, 192, 172), 1)
    y += 6
    # ---- map LEFT + ALSO list RIGHT
    mapw = 300
    maph = 166
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
        for ri, (item, reg, outlet) in enumerate(col_items):
            n = ci * 8 + ri + 1 if ci < 2 else 16 + ri + 1
            yy = y + 18 + ri * 20
            # v1.7: number in the story's region colour (darkened, so the
            # gold UK number still reads on cream) + verified outlet at
            # the end of the item — every ALSO item has one (RESEARCH.md)
            draw_text(cv, cxx, yy + 10, "%d." % n, 10, True,
                      CHIP_COLORS[reg])
            text = item + " (%s)" % outlet
            lines = wrap_text(text, 10, False, colw - 18)
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
    # v1.6: the 12 DATE CHECK items as flowing prose (same items, same
    # words, same order — only the grid layout is gone), the shape the top
    # entries use. Measured: 3 lines at 9px (2 lines is not reachable at a
    # readable size: 707 chars need ~2,900px at 9px vs 960px available).
    # Frees ~29px vs the grid — that funds the card chips + 11px decks.
    dc_prose = "  ·  ".join("%d. %s" % (i + 1, it)
                            for i, it in enumerate(DATE_CHECK))
    plines = wrap_text(dc_prose, 9, False, CW - 16)
    draw_lines(cv, MX + 8, dc_y, plines, 9, 10, False, INK)
    dc_y += 10 * len(plines) + 4
    # MORE row: +50% word spacing (space 2.0 -> 3.0px at 8px), leading 10 -> 11,
    # max width 960 -> 944 so no line ends near the right border; the 2px
    # saved in the gap above keeps the page bottom margin unchanged.
    mlines = wrap_text(MORE_CHECKED, 8, False, CW - 32, space_extra=1.0)
    draw_lines(cv, MX + 8, dc_y, mlines, 8, 10, False, INK_SOFT,
               space_extra=1.0)
    dc_bottom = dc_y + 10 * len(mlines) + 6
    cv.rect(MX, dc_top, CW, dc_bottom - dc_top, RED, 2)
    y = dc_bottom + 4  # v1.7: 5 -> 4 (vertical budget for the FIELDS strip)
    # ---- footer
    draw_text(cv, MX, y + 9,
              "OFFICIAL = authority’s own figure or act · REPORTED = press "
              "report · CLAIM = one side’s account. Drawn from verified "
              "reporting; every story first reported or developing Thu 26 Nov "
              "2026 unless dated in DATE CHECK.", 9, False, INK_SOFT)
    y += 11
    draw_text(cv, MX, y + 9,
              "Sources: Reuters, AP, BBC, CNN, Yonhap, TfL, FIDE, The Hindu, "
              "Guardian, Africanews", 9, False, INK_SOFT)
    y += 11
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
