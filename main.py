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
    # v2.3: 40 stories — A23 Riyadh + A24 Kuwait (ME), A25 Bangkok (EAST),
    # A26 Paris (EUROPE), A27 Virgin strike (OCEANIA). New totals: EAST 4
    # + SOUTH 2 + ME 4 + AFRICA 4 + AM 9 + OC 4 + UK 3 + EUROPE 5 + WORLD 5
    # = 40. SOUTH ASIA 2 stays the narrow segment (49px, label at 7px).
    # v2.4: LEAD REORDER — storm promoted to L1 (+1 AMERICAS), Ras Tanura
    # demoted lead -> ALSO (still MIDDLE EAST), weakest ALSO (A14 Red Sea
    # lakes, WORLD) dropped to keep the total at 40. New totals: EAST 4
    # + SOUTH 2 + ME 4 + AFRICA 4 + AM 10 + OC 4 + UK 3 + EUROPE 5 + WORLD 4
    # = 40.
    # v2.5: Kuwait -> L3 (ME, was ALSO), Bogor -> card S9 (EAST ASIA,
    # replaces Mumbai SOUTH ASIA), +UK migration ALSO (UK), +Bissau ALSO
    # (AFRICA); Mumbai + Hong Kong stay via ALSO. New totals: EAST 5
    # + SOUTH 2 + ME 4 + AFRICA 5 + AM 10 + OC 4 + UK 4 + EUROPE 5 + WORLD 4
    # = 43.
    ("EAST ASIA", 5, (58, 96, 135)),
    ("SOUTH ASIA", 2, (122, 88, 130)),
    ("MIDDLE EAST", 4, (171, 91, 45)),
    ("AFRICA", 5, (178, 62, 104)),
    ("AMERICAS", 10, (123, 58, 53)),
    ("OCEANIA", 4, (55, 113, 111)),
    ("UK", 4, (158, 120, 50)),
    ("EUROPE", 5, (101, 113, 68)),
    ("WORLD", 4, (80, 79, 75)),
]
# v1.7: topic fields — the same 40 stories regrouped by subject (main-story
# fields are explicit in STORY-LIST.md kickers; ALSO items classified by
# subject: A1/A2/A4 ECONOMY, A3/A8/A9 CONFLICT, A5/A6/A7/A15/A16/A18
# SOCIETY, A10/A14 WORLD, A11/A17/A22 DISASTER, A12/A13/A19/A21 SPORT,
# A20 CULTURE; v2.3 adds A23/A24 CONFLICT, A25 DISASTER, A26/A27 SOCIETY).
# TRADE 1 + CONFLICT 7 + ECONOMY 6 + DISASTER 7 + SOCIETY 11 + SPORT 5 +
# CULTURE 2 + WORLD 1 = 40. v2.4: storm L1 is DISASTER (+1 vs v2.3);
# Ras Tanura lead -> ALSO stays CONFLICT; A14 (WORLD) dropped (-1).
# v2.5: TRADE 1 (L2) + CONFLICT 7 (L3 Kuwait, S5, A3, A8, A9, A22 Riyadh,
# A26 Ras Tanura) + ECONOMY 6 (S6, S8, S11, A1, A2, A4) + DISASTER 8
# (L1 storm, S4 Cairo, S9 Bogor, S13 Ebola, A11 Flinders, A17 Iowa,
# A21 king tides, A23 Bangkok) + SOCIETY 12 (S7, A5, A6, A7, A15, A16,
# A24 Paris, A25 Virgin, A27 Mumbai, A28 Hong Kong, A29 UK migration,
# A30 Bissau) + SPORT 5 (S10, A12, A13, A18, A20) + CULTURE 2 (S12
# Macy's, A19 Ramsay) + WORLD 2 (A10 Australia emissions, A14 astronaut)
# = 43.
FIELDS = [
    ("TRADE", 1), ("CONFLICT", 7), ("ECONOMY", 6), ("DISASTER", 8),
    ("SOCIETY", 12), ("SPORT", 5), ("CULTURE", 2), ("WORLD", 2),
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
    "AFRICA": (178, 62, 104),
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


# ---- content: STORY-LIST.md is the single source of truth (43 stories)
MX = 24            # left/right margin
CW = W - 2 * MX    # content width = 976

STATS = [
    ("−0.6%", "NASDAQ · INTRADAY −4.6%"),
    # v2.3: NIKKEI slot replaced by the storm's power toll — the
    # nor'easter peaked at 961,000 customers without power Thu evening
    # (PowerOutage.us via Reuters); Nikkei +1.6% is still carried by
    # ALSO A1. "~1M" is the verified rounded figure.
    ("~1M", "WITHOUT POWER"),
    # v2.5: Thu settle $96.57 (+2.1%) — the $94.61 was the WED settle
    # (Reuters settlement reports; The Nation: Brent gains 2.07% on 26 Nov).
    ("$96.57", "BRENT · +2.1% THU SETTLE"),
    ("31", "DEAD · CAIRO FIRE"),
    # v2.0: "18TH / ANNIV. · 26/11 MUMBAI" replaced by the Ebola stat —
    # the duel's biggest content gap (12,021 cases in DR Congo, reported
    # Thu 26 Nov by Reuters). The Mumbai story stays as card S9; only
    # the stat slot changes.
    ("12,021", "EBOLA CASES"),
    ("€45BN", "UKRAINE LOAN"),
]

TIMELINE = [
    # v2.5: labels shortened to ONE line each (funds the ALSO floor:
    # timeline advance 42 -> 32). Times stay the same; the node headers
    # already carry the clock, so "Macy's parade hour" needs no (08:30 ET).
    ("01:37 GMT", "Brent $94.71 early trade"),
    ("05:44 UTC", "EU leaders meet in Brussels"),
    ("12:00 UTC", "London Tube strike begins"),
    ("13:30 UTC", "Macy’s parade hour"),
    ("14:00 UTC", "Game 3 begins in Geneva"),
    ("21:00 UTC", "No Tube service in London"),
]

LEADS = [
    {
        # v2.4: LEAD REORDER — the nor'easter is the new L1. The duel's
        # remaining deciding factor was lead-trio strength: every top
        # entry leads with the storm/Macy's, Kuwait or the EU summit,
        # and the storm is the day's biggest visual story. Facts from
        # RESEARCH.md story D (PowerOutage.us via Reuters / NWS): peak
        # ~961,000 customers without power Thu evening; 454 flights
        # cancelled, 2,411 delayed; Central Park 1.82 in rain.
        "num": 1, "kick": "EAST COAST · DISASTER", "pill": "OFFICIAL",
        "head": "Nor’easter cuts power to ~1M",
        # v2.5: the deck now names the Macy's postponement (the parade is
        # the storm's human face; the detail — Sat 8:30 a.m., gusts 60 mph
        # — lives in card S12). "Thu evening" dropped to stay at 2 lines.
        "deck": ("The nor’easter peaks at 961,000 customers without power; "
                 "454 flights cancelled, 2,411 delayed; Macy’s parade "
                 "postponed."),
        # v2.4: WHY IT MATTERS — ~1M in the dark at the peak (deck).
        "why": "WHY IT MATTERS: ~1M in the dark at the peak.",
        "meta": "PowerOutage.us via Reuters · NWS",
        "scene": "storm",
    },
    {
        # v2.4: tariffs demoted L1 -> L2 (content unchanged from v2.3 L1;
        # the container-ship scene moves with it).
        "num": 2, "kick": "WASHINGTON · TRADE", "pill": "REPORTED",
        "head": "US proposes tariffs on 14 partners",
        # v2.0: deck trimmed to 2 lines (was 3) to fund the WHY IT
        # MATTERS line below — drops "Asia rebounds as levies look
        # milder" (still carried by ALSO A1 + the Nikkei stat).
        "deck": ("India 25%, Japan 15%, China & Vietnam 20% in some reports. "
                 "EU rejects the premise; Brazil calls it unacceptable."),
        # v2.0: WHY IT MATTERS — one red line under each lead deck (the
        # top entries' signal line). Facts only, all already in the deck
        # / RESEARCH.md: 14 partners face the proposed levies.
        "why": "WHY IT MATTERS: Levies would hit 14 partners at once.",
        "meta": "BBC, France 24, Japan Times · USTR order, Wed",
        "scene": "tariffs",
    },
    {
        # v2.5: NEW L3 — Kuwait (promoted from ALSO A23). The duel's
        # deciding factor was lead-trio strength: 6/6 top entries show
        # Kuwait as a lead or a card; we showed it only as ALSO. The
        # DEATHS are confirmed (Italian authorities); the ATTRIBUTION is
        # one side's claim — the deck attributes it ("Italy blames Iran,
        # Tehran denies") and never states Iran as the attacker as fact.
        # Pill REPORTED (press report of confirmed deaths), not CLAIM:
        # the claim is the blame, and it is attributed in the deck.
        # Macy's L3 -> card S12.
        "num": 3, "kick": "KUWAIT · CONFLICT", "pill": "REPORTED",
        "head": "Kuwait drone attack kills 2 Italians",
        "deck": ("Debris from a downed drone kills 2 Rheinmetall Italia "
                 "technicians; Italy blames Iran, Tehran denies."),
        # v2.5: WHY IT MATTERS — the Gulf war reaches Kuwait (deck).
        "why": "WHY IT MATTERS: Gulf war reaches Kuwait.",
        "meta": "Reuters, CNN, WSJ · Thu",
        "scene": "kuwait",
    },
]

# small cards: (num, kicker, pill, headline, deck, icon key)
SMALL = [
    (4, "CAIRO · DISASTER", "OFFICIAL", "Cairo tanker fire kills 31",
     # v2.5: hurt 21 -> 26 (Health Ministry's Thu final toll, CNN/Al
     # Jazeera); driver, 21, detained Thu after confessing to 110 km/h;
     # "toll is preliminary" dropped — the Thu toll is final. Still 3 lines.
     "Fuel tanker overturns on the Ring Road, Wed evening; 26 hurt, 27 "
     "vehicles charred. Driver, 21, detained Thu. (AP)", "flame"),
    (5, "KYIV · CONFLICT", "REPORTED", "Ukraine hits 5 jets; Kyiv struck",
     # v2.3: deck reworded to carry story H — overnight ballistic-missile
     # strike on Kyiv, 7 hurt (Klitschko); 87 drones downed or suppressed
     # of 113 launched, 52 jet-powered (Ukraine Air Force, via Reuters /
     # NY Post 26 Nov). Still 3 lines.
     "Savasleyka hit — 3 MiG-31s, 2 Su-34s; 2 Samara refineries hit. "
     "Kyiv hit overnight; 7 hurt, 87 drones downed. (BBC)", "jet"),
    (6, "NEW YORK · ECONOMY", "REPORTED", "Nasdaq plunges, then recovers",
     "Wed close −0.6% at 23,586 after −4.6% intraday dive; Nasdaq-100 "
     "briefly −20% off record. Nvidia −3.9%. (AP, CNBC)", "chart"),
    (7, "LONDON · SOCIETY", "OFFICIAL", "Tube strike halts London",
     "RMT walkout from noon Thu to noon Fri; no Piccadilly or Circle all "
     "day, no service at all after 21:00. (TfL)", "train"),
    (8, "BRUSSELS · ECONOMY", "REPORTED", "EU fights over €45bn Ukraine loan",
     "Leaders meet Thu over a €1.58tn budget and Kyiv’s 2027 gap; deal "
     "aimed for 17–18 Dec. (Reuters, AP)", "flag"),
    # v2.5: S9 Mumbai (18 years since 26/11) -> ALSO A27; replaced by the
    # Bogor mine flood — a hard-news card the top entries all carry (the
    # #2 entry has it as a card). Facts verified 28 Nov ~01:30 WIB:
    # Reuters 26 Nov (via Kitco) + BBC: 13 dead, 13 still trapped, rain
    # halts rescue. The Fri toll (14/16) is NOT used.
    (9, "BOGOR · DISASTER", "REPORTED", "Bogor mine flood kills 13",
     "13 dead, 13 still trapped in a flooded gold mine; rain halts "
     "rescue. (Reuters/BBC)", "mine"),
    # v2.3: S10 updated with the result, now known (G) — Game 3 ended in
    # a 60-move draw, match level 1.5–1.5; Game 4 Saturday 28 Nov
    # (Chess.com / FIDE). Headline + deck + chip updated; still 2/3 lines.
    (10, "GENEVA · SPORT", "OFFICIAL", "Gukesh–Sindarov: Game 3 drawn",
     "Game 3 ends in a 60-move draw; match level 1.5–1.5. Game 4 "
     "Saturday; first to 7.5 takes the $2.5m crown. (FIDE)", "chess"),
    (11, "SEOUL · ECONOMY", "OFFICIAL", "Bank of Korea lifts rate to 3.25%",
     "Up 25bp, the highest in two years; 2027 growth forecast raised to "
     "4.1%. (Yonhap, CNBC)", "bank"),
    # v2.5: S12 Hong Kong -> ALSO A28; replaced by Macy's (demoted L3 ->
    # card). Deck shortened to 2 lines for the 187px card (the v2.4 L3
    # deck was 110 chars); gusts 60 mph kept. Scene: scaled-down parade.
    (12, "NEW YORK · CULTURE", "OFFICIAL",
     "Macy’s 100th parade postponed",
     "First weather delay ever; parade moves to Sat 8:30 a.m. as gusts "
     "hit 60 mph.", "parade"),
    # v2.0: S13 Nepal (213 presumed dead) SWAPPED for the Ebola card —
    # the duel's biggest content gap. Facts verified by parent via
    # Reuters 26 Nov 2026 (DR Congo govt data): 12,021 confirmed cases,
    # 5,904 deaths, Bundibugyo strain, second-largest Ebola outbreak on
    # record, response disrupted by fighting. ECDC: 12,021 at 24 Nov;
    # MoH SitRep 195 at 25 Nov (12,089 / 5,943) is the 25 Nov figure,
    # NOT used. Total was 35 at v2.0 (1-for-1 swap); region AFRICA.
    (13, "DR CONGO · DISASTER", "REPORTED",
     "Ebola tops 12,000 cases in DR Congo",
     "12,021 cases, 5,904 dead — second-largest Ebola outbreak ever "
     "recorded. (Reuters)", "ebola"),
]

# v1.7: two-line coloured chips INSIDE each card's scene — (number, label,
# region). Number 13px bold, label 9px bold (v1.8: was 12/8px); both facts
# already in that card's deck/headline (STORY-LIST.md). Chip colour = the
# story's region (darkened, see CHIP_COLORS); the v1.6 black full-width
# band is gone.
# Regions: S4 AFRICA (v2.0: Cairo moved MIDDLE EAST -> AFRICA), S5 EUROPE,
# S6 AMERICAS, S7 UK, S8 EUROPE, S9 EAST ASIA (v2.5: Bogor, was SOUTH ASIA
# Mumbai), S10 WORLD, S11 EAST ASIA, S12 AMERICAS (v2.5: Macy's, was EAST
# ASIA Hong Kong), S13 AFRICA (v2.0: Ebola, was SOUTH ASIA Nepal).
CHIPS = {
    4: ("31", "DEAD", "AFRICA"),
    5: ("5", "JETS DOWNED", "EUROPE"),
    6: ("−4.6%", "THEN RECOVERED", "AMERICAS"),
    7: ("TUBE", "HALTED", "UK"),
    8: ("€45BN", "LOAN", "EUROPE"),
    9: ("13", "DEAD", "EAST ASIA"),
    10: ("1.5–1.5", "DRAW", "WORLD"),
    11: ("3.25%", "RATE", "EAST ASIA"),
    12: ("100TH", "PARADE", "AMERICAS"),
    13: ("12,021", "CASES", "AFRICA"),
}

# v1.8: per-card chip corner — default top-left (4,2). S13 goes
# top-right (99,2): the enlarged chip would otherwise cover the
# back-peak snow cap, which sits top-centre-left in the flood scene.
# 99 is the flush maximum: chip width 88px, scene width 187px, so the
# chip ends exactly at the scene's right edge (the page's right margin —
# S13 is the last column, no card to its right).
# v2.0: the flood scene is gone (S13 is now Ebola) and the new Ebola
# scene is drawn clear at top-left (tent apex sits right of x+61),
# so S13 uses the default top-left corner again. No overrides remain.
CHIP_POS = {}

# v1.7: (text, region, outlet) — region from the STORY-LIST.md tag
# (EU bucket split UK/EUROPE as in REGION_COLORS: Liverpool + Top Gear are
# British, Lille/Bayern + ECB stay EUROPE); outlet = first-listed source
# for that item in RESEARCH.md (all 22 verified there).
ALSO = [
    # v2.5: A1 corrected — Thu close +0.9% to 57,499 (the +1.6% was the
    # intraday peak); Shanghai Thu close FLAT +0.01% (the −2.1% was
    # Wednesday's close). Barchart / Japan.co.jp / Nikkei.
    ("Nikkei +0.9% to 57,499 as tariffs look milder; Shanghai flat at 3,477", "EAST ASIA", "Barchart"),
    # v2.5: Brent Thu settle $96.57 (+2.1%); WTI unchanged from v2.4.
    ("Brent $96.57 (+2.1%); WTI $83.68 (+2%) as Gulf fears lift oil", "WORLD", "Reuters"),
    ("Trump, Rutte urge Russia not to widen the war (Mar-a-Lago talks)", "AMERICAS", "Reuters"),
    ("ECB: Pablo Hernandez de Cos set to succeed Lagarde", "EUROPE", "Rapporteur"),
    ("Abrego Garcia reaches Spain after a 20-month US legal fight", "AMERICAS", "Euronews"),
    ("Brazil withdraws ambassador to Argentina for good", "AMERICAS", "MercoPress"),
    ("Hasina return dispute: India separates return from extradition", "SOUTH ASIA", "The Hindu"),
    ("ISIL suicide attack kills 2 in Hasakah, Syria", "MIDDLE EAST", "Al Jazeera"),
    ("Somalia: foreign troops withdraw; Uganda steps up anti-al-Shabaab fight", "AFRICA", "BBC"),
    ("Australia projected to miss its 2035 emissions target", "OCEANIA", "Guardian"),
    ("Flinders Island fire destroys at least 6 homes", "OCEANIA", "Guardian"),
    ("Liverpool beat Club Brugge 3–0 in the Champions League", "UK", "BBC"),
    ("Lille beat Bayern 2–1, ending their unbeaten run", "EUROPE", "BBC"),
    ("Canadian astronaut welcomes a baby girl from orbit", "WORLD", "BBC"),
    ("Pig-kidney patient marks one year off dialysis", "AMERICAS", "CBC"),
    ("Famine risk falls in Baidoa, Somalia — but hunger persists", "AFRICA", "AllAfrica"),
    ("US Army calls Iowa 5-ton blast a 'huge success'", "AMERICAS", "BBC"),
    ("Kurtley Beale returns to the Wallabies after five years", "OCEANIA", "ABC"),
    ("Gordon Ramsay to host revived Top Gear", "UK", "BBC"),
    ("U-17 World Cup: Egypt 4–1 Panama; Uganda 6–0 New Caledonia", "WORLD", "Africanews"),
    ("King tides flood the California coast as storms hit Thanksgiving travel", "AMERICAS", "Guardian"),
    # v2.3: 5 new ALSO items (A23–A27), all genuine Thu 26 Nov, verified
    # to primary sources (see STORY-LIST.md / RESEARCH.md):
    # A23 Riyadh intercepts (coalition / al-Maliki via Reuters),
    # A24 Kuwait drone (Italy/Kuwait blame Iran; Tehran denies — Reuters,
    # CNN, WSJ), A25 Bangkok blast (AP via CNN), A26 Paris march
    # (Franceinfo), A27 Virgin strike (TravelTalk / Australian Aviation).
    ("Coalition downs 2 Houthi missiles over Riyadh; Jazan port hit", "MIDDLE EAST", "Reuters"),
    # v2.5: Kuwait left the ALSO list — promoted to lead L3.
    ("Bangkok refinery blast injures 9, 3 critical; plant shut", "EAST ASIA", "AP"),
    ("Paris students march for funds; ~2,000, Bastille to Pantheon", "EUROPE", "Franceinfo"),
    ("Virgin Australia staff strike at 4 airports in pay row", "OCEANIA", "TravelTalk"),
    # v2.4: Ras Tanura demoted lead -> ALSO (keeps the story on the page;
    # the CLAIM wording stays in the text — never a verified fact).
    # A14 (Red Sea lakes, WORLD) dropped — the weakest ALSO line, a
    # science curiosity with no human/policy impact — so the total stays
    # 40 after the storm's promotion to L1 (+1 AMERICAS).
    ("Houthis claim refinery hit; 4 drones downed", "MIDDLE EAST", "Reuters"),
    # v2.5: S9 Mumbai card -> ALSO; S12 Hong Kong card -> ALSO; +2 new
    # ALSO items (UK migration, Bissau) — ALSO 27 -> 30, total 40 -> 43.
    ("Mumbai marks 18 years since 26/11; 166 killed in 2008", "SOUTH ASIA", "IANS"),
    ("Hong Kong marks year since fire killed 168; families await answers", "EAST ASIA", "Japan Times"),
    ("UK net migration 77,000, lowest since 1997", "UK", "ONS"),
    ("Guinea-Bissau junta delays vote to Nov 2028", "AFRICA", "AP"),
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
    # v2.3: SINGLE iconic motif — one giant container ship under a red
    # "25%" stamp. Replaces the v2.2 trading terminal (globe + 4 bars +
    # chip), which the v2.2 duel called the busiest hero on the page
    # (all three thin losses named it). Facts stay in the deck + chip
    # (India 25%, Japan 15%, China & Vietnam 20%). Night sky, bridge
    # superstructure left, two stacked container rows, hull, waves.
    # The stamp is a white-ringed red disc top-right, "25%" 16px bold.
    cv.fill_rect(x, y, w, h, (10, 30, 64))
    for r in range(3):
        cv.fill_rect(x, y + h * (8 + r * 6) // 100, w, h * 3 // 100,
                     (16 + r * 6, 42 + r * 6, 86 + r * 6))
    for (sx, sy) in [(x + 26, y + 9), (x + 90, y + 6), (x + 212, y + 7),
                     (x + 262, y + 10), (x + 296, y + 8)]:
        cv.fill_rect(sx, sy, 2, 2, (255, 255, 255))
    # bridge superstructure (left), same height as the container rows
    cv.fill_rect(x + 14, y + 28, 26, 36, (196, 198, 202))
    cv.fill_rect(x + 14, y + 28, 26, 3, (210, 48, 32))
    cv.fill_rect(x + 18, y + 36, 18, 3, (60, 90, 130))
    cv.fill_rect(x + 18, y + 42, 18, 3, (60, 90, 130))
    cv.fill_rect(x + 18, y + 48, 18, 3, (60, 90, 130))
    # smokestack mid-ship + smoke puffs above it (clear of the label)
    cv.fill_rect(x + 150, y + 16, 6, 12, (210, 48, 32))
    for (sx0, sy0) in [(x + 148, y + 8), (x + 154, y + 5), (x + 160, y + 9)]:
        cv.fill_rect(sx0, sy0, 3, 3, (200, 200, 200))
    # two stacked container rows
    cv.fill_rect(x + 40, y + 28, 258, 36, (18, 44, 82))
    cv.fill_rect(x + 40, y + 28, 258, 2, (60, 90, 130))
    cols1 = [(210, 48, 32), (240, 166, 30), (58, 96, 135), (210, 48, 32),
             (240, 166, 30), (58, 96, 135), (210, 48, 32), (240, 166, 30)]
    for i, c in enumerate(cols1):
        cv.fill_rect(x + 42 + i * 31, y + 32, 28, 14, c)
    cols2 = [(58, 96, 135), (210, 48, 32), (240, 166, 30), (58, 96, 135),
             (210, 48, 32), (240, 166, 30), (58, 96, 135), (210, 48, 32)]
    for i, c in enumerate(cols2):
        cv.fill_rect(x + 42 + i * 31, y + 47, 28, 14, c)
    # hull + water + two wave-dash rows (fills the 110px box to the floor)
    cv.fill_rect(x, y + 64, w, 10, (122, 34, 30))
    cv.fill_rect(x, y + 74, w, 12, (14, 26, 48))
    for wx in range(8, w, 46):
        cv.fill_rect(x + wx, y + 78, 30, 2, (70, 110, 160))
    for wx in range(30, w, 46):
        cv.fill_rect(x + wx, y + 92, 30, 2, (70, 110, 160))
    # red "25%" stamp, top-right, over the containers' right end
    # (white ring = white disc r24 under the red disc r22)
    cv.fill_circle(x + 288, y + 30, 24, (255, 255, 255))
    cv.fill_circle(x + 288, y + 30, 22, (210, 48, 32))
    draw_text(cv, x + 288, y + 25, "25%", 16, True, (255, 255, 255), "c")
    draw_text(cv, x + 12, y + 10, "USTR PROPOSAL", 8, True,
              (255, 255, 255), "l")


def scene_storm(cv, x, y, w, h):
    # v2.4: NEW L1 hero — the nor'easter as ONE iconic motif: dark storm
    # sky + lightning bolt + slanted rain + a leaning power pole with
    # sagging wires (one snapped, sparking) + a dark unlit house +
    # "~1M WITHOUT POWER" tag. Background: deep violet-grey storm,
    # distinct from the L2 ship's navy (10,30,64) and the L3 parade's
    # slate (96,104,116). The tag duplicates the stat-strip figure,
    # the same pattern as the refinery's "550,000 BPD" chip.
    cv.fill_rect(x, y, w, 44, (34, 30, 54))
    cv.fill_rect(x, y + 44, w, 34, (58, 54, 82))
    cv.fill_rect(x, y + 78, w, h - 78, (22, 24, 30))
    # storm clouds, darker than the sky
    cv.fill_ellipse(x + 70, y + 12, 46, 12, (18, 16, 30))
    cv.fill_ellipse(x + 130, y + 8, 38, 10, (18, 16, 30))
    cv.fill_ellipse(x + 250, y + 14, 40, 11, (24, 22, 38))
    # slanted heavy rain (upper two-thirds)
    for rx in range(12, w, 22):
        for ry in range(22, 74, 16):
            cv.line(x + rx, y + ry, x + rx - 8, y + ry + 7, (168, 178, 198))
    # lightning bolt, centre-right (gold zigzag, 3px stroke)
    stroke3(cv, [(x + 208, y + 22), (x + 196, y + 48), (x + 206, y + 48),
                 (x + 190, y + 76)], (250, 205, 80))
    # dark unlit house, bottom-left (no lit windows: no power)
    cv.fill_rect(x + 12, y + 82, 52, 28, (14, 13, 16))
    cv.fill_poly([(x + 8, y + 82), (x + 38, y + 64), (x + 68, y + 82)],
                 (14, 13, 16))
    cv.fill_rect(x + 20, y + 90, 8, 8, (22, 24, 30))
    cv.fill_rect(x + 46, y + 90, 8, 8, (22, 24, 30))
    # leaning power pole + crossarm, centre-left
    stroke3(cv, [(x + 104, y + 108), (x + 122, y + 52)], (16, 14, 12))
    stroke3(cv, [(x + 110, y + 62), (x + 134, y + 56)], (16, 14, 12))
    # sagging wires from the pole top, one snapped with a spark
    stroke3(cv, [(x + 122, y + 52), (x + 150, y + 66), (x + 178, y + 60)],
            (16, 14, 12))
    stroke3(cv, [(x + 122, y + 52), (x + 96, y + 66), (x + 76, y + 62)],
            (16, 14, 12))
    # spark burst at the snapped wire end
    sx0, sy0 = x + 178, y + 60
    for k in range(8):
        a = k * 3.14159265 / 4.0
        cv.line(sx0 + int(round(3 * _cos(a))), sy0 + int(round(3 * _sin(a))),
                sx0 + int(round(7 * _cos(a))), sy0 + int(round(7 * _sin(a))),
                (250, 205, 80))
    # wet road dashes along the floor
    for wx in range(120, w, 52):
        cv.fill_rect(x + wx, y + 100, 30, 2, (70, 78, 96))
    # "~1M WITHOUT POWER" tag, top-right, ink box
    cv.fill_rect(x + w - 128, y + 6, 120, 15, INK)
    draw_text(cv, x + w - 124, y + 17, "~1M WITHOUT POWER", 9, True,
              (255, 255, 255))


def scene_refinery(cv, x, y, w, h):
    # v2.2: hero redrawn for the 110px box — same refinery, taller sky
    # (stars + 2 bigger drones), taller plumes, taller tower, bigger
    # tanks and flame. BRENT chip moves to y+52 (was y+24) so the
    # taller flare flame (apex y+16, base y+34) clears it.
    cv.fill_rect(x, y, w, 30, (56, 34, 74))
    cv.fill_rect(x, y + 30, w, 28, (226, 148, 74))
    cv.fill_rect(x, y + 58, w, 16, (198, 96, 52))
    cv.fill_rect(x, y + 74, w, h - 74, (74, 48, 52))
    for (sx, sy) in [(120, 7), (150, 12), (200, 6), (232, 6), (290, 7),
                     (305, 12), (90, 16), (270, 20)]:
        cv.fill_circle(x + sx, y + sy, 1, (255, 255, 255))
    # drones, bigger (body 10x4, rotors r3)
    for (dx, dy) in [(130, 14), (245, 18)]:
        cv.fill_rect(x + dx - 5, y + dy, 10, 4, (26, 24, 20))
        for rx in (dx - 7, dx + 5):
            cv.fill_circle(x + rx, y + dy - 2, 3, (26, 24, 20))
    # smoke plume A over the mid vent stack (top y+62), drifting left
    for (sx, sy, rx, ry, col) in [(162, 54, 7, 5, (98, 94, 88)),
                                  (160, 46, 9, 5, (104, 100, 94)),
                                  (162, 38, 7, 6, (112, 108, 102)),
                                  (159, 30, 10, 5, (120, 116, 110)),
                                  (161, 22, 8, 5, (128, 124, 118)),
                                  (158, 14, 11, 5, (138, 134, 128)),
                                  (159, 8, 8, 4, (148, 144, 138))]:
        cv.fill_ellipse(x + sx, y + sy, rx, ry, col)
    # smoke plume B over the second stack (top y+44), drifting right
    for (sx, sy, rx, ry, col) in [(266, 48, 7, 5, (98, 94, 88)),
                                  (264, 40, 9, 5, (106, 102, 96)),
                                  (267, 32, 7, 5, (114, 110, 104)),
                                  (265, 24, 10, 5, (124, 120, 114)),
                                  (266, 16, 8, 4, (134, 130, 124))]:
        cv.fill_ellipse(x + sx, y + sy, rx, ry, col)
    # distillation tower, top y+34 (clears the 550,000 BPD chip by 15px)
    cv.fill_rect(x + 18, y + 34, 16, h - 34, (38, 34, 36))
    for py in (44, 56, 68):
        cv.fill_rect(x + 14, y + py, 24, 3, (120, 116, 110))
    # mid vent stack (feeds plume A)
    cv.fill_rect(x + 160, y + 62, 6, h - 62, (38, 34, 36))
    # storage tanks, bigger (first tank centred y+h-16 so its r16 base
    # lands exactly on the scene floor)
    cv.fill_circle(x + 88, y + h - 16, 16, (52, 46, 48))
    cv.fill_circle(x + 118, y + h - 12, 14, (52, 46, 48))
    cv.fill_rect(x + 81, y + h - 22, 14, 2, (120, 116, 110))
    cv.fill_rect(x + 110, y + h - 20, 12, 2, (120, 116, 110))
    # flare stack + bigger flame (base y+34, apex y+16)
    cv.fill_rect(x + 206, y + 34, 9, h - 34, (38, 34, 36))
    fx, fy = x + 210, y + 34
    cv.fill_poly([(fx - 7, fy), (fx, fy - 18), (fx + 7, fy)], (232, 120, 30))
    cv.fill_poly([(fx - 4, fy), (fx, fy - 10), (fx + 4, fy)], (250, 205, 80))
    # second stack (feeds plume B)
    cv.fill_rect(x + 260, y + 44, 9, h - 44, (38, 34, 36))
    # connecting pipe, tower -> tanks
    cv.fill_rect(x + 34, y + h - 26, 44, 3, (38, 34, 36))
    cv.fill_rect(x + 4, y + 4, 104, 15, INK)
    draw_text(cv, x + 8, y + 15, "550,000 BPD", 9, True, (255, 255, 255))
    cv.fill_rect(x + 170, y + 52, 88, 15, INK)
    draw_text(cv, x + 174, y + 63, "BRENT +3.5%", 9, True, (255, 255, 255))
    cv.fill_rect(x + 40, y + 26, 106, 15, INK)
    draw_text(cv, x + 44, y + 37, "4 DRONES DOWNED", 9, True,
              (255, 255, 255))


def scene_parade(cv, x, y, w, h):
    # v2.2: hero redrawn for the 110px box — same nor'easter parade,
    # motifs grown ~1.5x: bigger balloon (rx 42), taller skyline,
    # more crowd, bigger storm clouds + lightning. Facts unchanged
    # (100th, Sat 08:30, gusts 60 mph).
    cv.fill_rect(x, y, w, 40, (96, 104, 116))
    cv.fill_rect(x, y + 40, w, 38, (72, 80, 92))
    cv.fill_rect(x, y + 78, w, h - 78, (52, 58, 66))
    # wind-driven rain, slanted hard sideways
    for rx in range(14, w, 26):
        for ry in range(6, 86, 14):
            cv.line(x + rx, y + ry, x + rx - 9, y + ry + 6, (200, 206, 214))
    # wind streaks, thicker and longer
    for (sx, sy, ln) in [(120, 16, 90), (220, 30, 90), (30, 64, 80)]:
        cv.fill_rect(x + sx, y + sy, ln, 3, (220, 226, 232))
    # storm clouds + lightning bolt
    cv.fill_ellipse(x + 100, y + 8, 30, 10, (60, 66, 78))
    cv.fill_ellipse(x + 145, y + 10, 28, 9, (60, 66, 78))
    stroke3(cv, [(x + 252, y + 26), (x + 246, y + 40), (x + 254, y + 40),
                 (x + 246, y + 56)], (250, 205, 80))
    # Manhattan skyline, taller
    heights = [24, 36, 28, 42, 22, 34, 40, 28, 30, 22]
    bx = x + 8
    for i, hh in enumerate(heights):
        cv.fill_rect(bx + i * 30, y + h - hh, 24, hh, (26, 24, 20))
        for wy in range(5, hh - 4, 10):
            cv.fill_rect(bx + i * 30 + 5, y + h - hh + wy, 3, 4,
                         (250, 205, 80))
    # parade crowd silhouettes along the street
    for cxp in (25, 50, 75, 100, 125, 150, 175, 200):
        cv.fill_circle(x + cxp, y + h - 12, 4, (26, 24, 20))
        cv.fill_rect(x + cxp - 5, y + h - 8, 10, 8, (26, 24, 20))
    # big balloon, tilted by the wind — bigger (rx 42, ry 28)
    bcx, bcy = x + 190, y + 44
    t = 0.28
    ct, st = _cos(t), _sin(t)
    pts = []
    for k in range(28):
        a = k * 2 * 3.14159265 / 28.0
        ca, sa = _cos(a), _sin(a)
        px = bcx + 42 * ca * ct - 28 * sa * st
        py = bcy + 42 * ca * st + 28 * sa * ct
        pts.append((int(round(px)), int(round(py))))
    cv.fill_poly(pts, BALLOON_RED)
    pts2 = []
    for k in range(28):
        a = k * 2 * 3.14159265 / 28.0
        ca, sa = _cos(a), _sin(a)
        px = bcx + 4 + 30 * ca * ct - 10 * sa * st
        py = bcy + 12 + 30 * ca * st + 10 * sa * ct
        pts2.append((int(round(px)), int(round(py))))
    cv.fill_poly(pts2, BALLOON_DK)
    cv.fill_ellipse(bcx - 16, bcy - 14, 12, 7, (205, 105, 92))
    stroke3(cv, [(bcx - 14, bcy - 24), (bcx - 17, bcy),
                 (bcx - 14, bcy + 24)], BALLOON_DK)
    stroke3(cv, [(bcx + 11, bcy - 23), (bcx + 14, bcy + 1),
                 (bcx + 11, bcy + 24)], BALLOON_DK)
    # second, smaller gold balloon trailing behind (moved right so the
    # bigger 100TH text clears it)
    cv.fill_ellipse(x + 122, y + 26, 14, 10, GOLD)
    cv.fill_ellipse(x + 118, y + 23, 5, 4, (250, 205, 80))
    cv.line(x + 122, y + 32, x + 116, y + 42, (26, 24, 20))
    cv.line(x + 132, y + 32, x + 136, y + 42, (26, 24, 20))
    # ropes trailing down-left from the balloon
    cv.line(bcx - 28, bcy + 18, bcx - 42, bcy + 42, (26, 24, 20))
    cv.line(bcx + 18, bcy + 19, bcx + 6, bcy + 44, (26, 24, 20))
    # confetti blown sideways
    for (ccx, ccy, col) in [(230, 10, GOLD), (250, 16, (250, 205, 80)),
                            (280, 12, BLUE), (300, 20, (248, 244, 233)),
                            (270, 30, GOLD), (300, 34, (250, 205, 80)),
                            (240, 40, RED), (130, 44, GOLD),
                            (100, 50, RED), (290, 46, BLUE),
                            (260, 58, GOLD), (180, 64, RED),
                            (140, 70, BLUE), (310, 62, GOLD),
                            (90, 66, (250, 205, 80))]:
        cv.fill_rect(x + ccx, y + ccy, 5, 2, col)
    # parade float (platform + flags) bottom right
    cv.fill_rect(x + 238, y + h - 16, 64, 10, (26, 24, 20))
    cv.fill_rect(x + 244, y + h - 34, 3, 18, (26, 24, 20))
    cv.fill_poly([(x + 247, y + h - 34), (x + 259, y + h - 31),
                  (x + 247, y + h - 28)], RED)
    cv.fill_rect(x + 286, y + h - 34, 3, 18, (26, 24, 20))
    cv.fill_poly([(x + 289, y + h - 34), (x + 301, y + h - 31),
                  (x + 289, y + h - 28)], GOLD)
    # "100TH" badge, bigger (30px)
    draw_text(cv, x + 8, y + 42, "100TH", 30, True, (255, 255, 255))
    cv.fill_rect(x + w - 96, y + 4, 92, 15, INK)
    draw_text(cv, x + w - 92, y + 15, "GUSTS 60 MPH", 9, True,
              (255, 255, 255))
    # red in-scene label bar — drawn last, sits on top of the balloon's
    # lower-left edge (same pattern as v2.1)
    bar_txt = "PARADE POSTPONED — SAT 08:30"
    bw = int(text_width(bar_txt, 9, True)) + 12
    cv.fill_rect(x + 8, y + 46, bw, 16, RED)
    draw_text(cv, x + 14, y + 58, bar_txt, 9, True, (255, 255, 255))


def scene_kuwait(cv, x, y, w, h):
    # v2.5: NEW L3 hero — Kuwait as ONE night air-defence motif: dark
    # blue night sky + orange horizon glow + radar dish + missile
    # launcher + drone with a red trail + gold interception burst +
    # smoke + "2 KILLED" tag. Background is distinct from the storm's
    # violet-grey (34,30,54) and the ship's navy (10,30,64): darker blue
    # with the orange dusk band. The tag duplicates the death toll, the
    # same pattern as the storm's "~1M WITHOUT POWER" tag.
    cv.fill_rect(x, y, w, 46, (20, 24, 44))
    cv.fill_rect(x, y + 46, w, 16, (190, 100, 50))
    cv.fill_rect(x, y + 62, w, h - 62, (18, 20, 26))
    # stars
    for (sx, sy) in [(x + 20, y + 8), (x + 60, y + 6), (x + 110, y + 10),
                     (x + 150, y + 7), (x + 290, y + 30), (x + 300, y + 12)]:
        cv.fill_rect(sx, sy, 2, 2, (255, 255, 255))
    # low skyline silhouette, right (Kuwait City hint)
    for (bx0, bw0, bh0) in [(268, 12, 22), (282, 10, 30), (294, 12, 18)]:
        cv.fill_rect(x + bx0, y + h - bh0, bw0, bh0, (12, 14, 18))
    cv.fill_rect(x + 285, y + h - 38, 3, 3, (250, 205, 80))
    # radar dish, left (pole + tilted dish)
    stroke3(cv, [(x + 36, y + 78), (x + 36, y + 44)], (16, 14, 12))
    cv.fill_ellipse(x + 36, y + 38, 16, 8, (60, 66, 76))
    cv.fill_ellipse(x + 36, y + 36, 16, 5, (120, 126, 138))
    # missile launcher, centre (base + angled rail + missile)
    cv.fill_rect(x + 128, y + 78, 44, 8, (38, 34, 36))
    stroke3(cv, [(x + 138, y + 78), (x + 158, y + 48)], (16, 14, 12))
    stroke3(cv, [(x + 146, y + 78), (x + 166, y + 48)], (16, 14, 12))
    cv.fill_rect(x + 156, y + 42, 4, 14, (200, 200, 200))
    cv.fill_poly([(x + 154, y + 42), (x + 158, y + 36), (x + 162, y + 42)],
                 (200, 200, 200))
    # drone, top-centre (dark body + rotors + red trail to the left)
    cv.fill_rect(x + 196, y + 12, 12, 4, (26, 24, 20))
    for rx in (194, 206):
        cv.fill_circle(x + rx, y + 10, 3, (26, 24, 20))
    cv.line(x + 196, y + 14, x + 168, y + 18, (210, 48, 32))
    cv.line(x + 196, y + 14, x + 176, y + 10, (210, 48, 32))
    # interception burst, centre-right (gold starburst, 12 spikes)
    bx, by = x + 224, y + 44
    burst = []
    for k in range(12):
        a = k * 3.14159265 / 6.0
        r = 11 if k % 2 == 0 else 5
        burst.append((bx + int(round(r * _cos(a))),
                      by + int(round(r * _sin(a)))))
    cv.fill_poly(burst, (232, 120, 30))
    cv.fill_circle(bx, by, 4, (250, 205, 80))
    # smoke column rising right of the burst
    for (sx, sy, rx, ry) in [(238, 30, 6, 4), (242, 22, 7, 4),
                             (246, 14, 6, 3)]:
        cv.fill_ellipse(x + sx, y + sy, rx, ry, (120, 116, 110))
    # ground line + debris dashes
    cv.fill_rect(x, y + 86, w, 2, (40, 36, 34))
    for dx in (60, 100, 240):
        cv.fill_rect(x + dx, y + 92, 14, 2, (90, 86, 80))
    # "2 KILLED" tag, top-right, ink box (text 41.8px + 12 padding)
    cv.fill_rect(x + w - 60, y + 6, 54, 15, INK)
    draw_text(cv, x + w - 56, y + 17, "2 KILLED", 9, True,
              (255, 255, 255))


SCENES = {"tariffs": scene_tariffs, "refinery": scene_refinery,
          "parade": scene_parade, "storm": scene_storm,
          "kuwait": scene_kuwait}
# NOTE v2.4: scene_refinery is kept (unused since the Ras Tanura lead was
# demoted to ALSO) — the code keeps prior scenes, like v2.3 kept the
# v2.2 trading terminal.


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
    # v2.1: each bg is now the TOP band of a layered background (sky) —
    # mid + ground bands are painted inside each branch. No two scenes
    # share a top colour, and none is the page cream.
    bg = {"flame": (58, 36, 76), "jet": (244, 176, 122),
          "chart": (12, 46, 40), "train": (18, 58, 46),
          "flag": (26, 54, 104), "candle": (84, 50, 94),
          "chess": (22, 68, 42), "bank": (22, 80, 92),
          "memorial": (14, 18, 32), "flood": (206, 220, 232),
          "ebola": (26, 74, 40), "mine": (36, 32, 30),
          "parade": (96, 104, 116)}[key]
    cv.fill_rect(x, y, w, h, bg)
    cx, cy = x + w // 2, y + h // 2
    if key == "flame":
        # v2.1: layered dusk background (was flat dark brown) — purple
        # sky + orange horizon + dark road, pale moon top-right, and a
        # second charred car so the pile-up reads, not just one truck.
        cv.fill_rect(x, y + 22, w, 14, (214, 128, 62))
        cv.fill_rect(x, y + 36, w, h - 36, (36, 32, 32))
        cv.fill_circle(x + 168, y + 10, 6, (240, 230, 200))
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
        # second charred car, right of the tanker (27 vehicles charred)
        cv.fill_rect(x + 146, cy + 2, 28, 9, (22, 20, 20))
        cv.fill_poly([(x + 152, cy + 2), (x + 155, cy - 5),
                      (x + 158, cy + 2)], (232, 120, 30))
        for wx in (x + 152, x + 168):
            cv.fill_circle(wx, cy + 12, 3, INK)
    elif key == "jet":
        # v2.1: layered dawn background (was flat pale blue, shared with
        # S13) — pink-orange dawn sky + low sun + dark runway strip with
        # dashes + a smoke column rising right of the jet (airbase hit).
        cv.fill_rect(x, y + 20, w, 18, (232, 120, 80))
        cv.fill_rect(x, y + 38, w, h - 38, (44, 38, 44))
        cv.fill_circle(x + 168, y + 10, 8, (255, 236, 190))
        # v2.3: dashes at y+46 (was y+50) — card scene is 50px now;
        # 4px above the floor, same as v2.2.
        for dx in (20, 60, 100, 140):
            cv.fill_rect(x + dx, y + 46, 6, 2, (248, 244, 233))
        for (sx, sy, rx, ry) in [(162, 34, 5, 3), (160, 40, 6, 3),
                                 (163, 46, 5, 3)]:
            cv.fill_ellipse(x + sx, y + sy, rx, ry, (120, 116, 110))
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
        for sy in (cy - 1, cy + 6, cy + 13):
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
        # v2.1: dark trading-screen background (was cream = the page) —
        # deep teal bands + faint gridlines + a ticker strip of squares
        # along the floor, so the plunge-and-recover reads as a market
        # screen, not a bare chart on paper. Brighter bars/line for dark.
        cv.fill_rect(x, y + 20, w, 20, (18, 64, 54))
        cv.fill_rect(x, y + 40, w, h - 40, (8, 32, 30))
        for gx in range(10, w, 20):
            cv.fill_rect(x + gx, y, 1, h, (40, 90, 80))
        for gy in (15, 30, 45):
            cv.fill_rect(x, y + gy, w, 1, (40, 90, 80))
        # v1.5: axes + bars + a line that PLUNGES then RECOVERS (V / dip and
        # rise) — v1.2 only rose, which was wrong for the Nasdaq story.
        # v1.8: the whole chart sits 10px lower (cy+10) — the v1.7 chip
        # covered the Y-axis top and the V-line's first (dip) point; the
        # axis top now clears the chip bottom by 2px, and the baseline
        # still sits 7px above the scene floor.
        # v2.3: cy +12 (was +13) — card scene is 50px now (was 54);
        # the axis baseline stays 1px above the scene floor.
        cy = cy + 12
        cv.fill_rect(cx - 70, cy - 13, 3, 26, (255, 255, 255))
        cv.fill_rect(cx - 70, cy + 10, 140, 3, (255, 255, 255))
        cv.fill_rect(cx - 58, cy - 4, 12, 14, (96, 168, 232))
        cv.fill_rect(cx - 40, cy + 5, 12, 5, (250, 200, 70))
        cv.fill_rect(cx - 22, cy - 6, 12, 16, (96, 168, 232))
        pts = [(cx - 58, cy - 12), (cx - 36, cy + 6), (cx - 14, cy - 4),
               (cx + 8, cy - 12), (cx + 36, cy - 16)]
        stroke3(cv, pts, (240, 80, 60))
        cv.fill_poly([(cx + 38, cy - 17), (cx + 26, cy - 15), (cx + 34, cy - 7)],
                     (240, 80, 60))
        # ticker strip along the floor
        for i, col in enumerate([(96, 168, 232), (240, 80, 60),
                                 (250, 200, 70), (96, 168, 232),
                                 (240, 80, 60)]):
            cv.fill_rect(x + 20 + i * 10, y + h - 5, 5, 4, col)
    elif key == "train":
        # v2.1: Underground station background (was flat solid red) —
        # green tile top + platform band + dark track, a tunnel arch
        # behind the train and a hanging lamp top-right. The strike now
        # has a station to happen in.
        cv.fill_rect(x, y + 18, w, 26, (198, 188, 158))
        cv.fill_rect(x, y + 44, w, h - 44, (28, 26, 26))
        # tunnel portal behind the train (rect + rounded top) — v2.1
        # first attempt drew one huge filled arch that swallowed the
        # platform band and the barrier; the portal keeps the platform
        # visible on both sides.
        cv.fill_rect(cx - 62, cy - 14, 124, 38, (12, 16, 14))
        cv.fill_ellipse(cx, cy - 14, 62, 12, (12, 16, 14))
        cv.fill_circle(x + 168, y + 8, 4, (250, 205, 80))
        cv.fill_rect(x + 167, y + 12, 2, 6, (250, 205, 80))
        # v1.5: subway front view + London Underground roundel (left) and a
        # closed crossing barrier (right) — the strike halting service
        # roundel: paper ring, red disc, blue bar (shapes, no text)
        # v1.8: centre cy-2 -> cy+5 — the v1.7 chip clipped the ring's top
        # (4px; 6px with the taller v1.8 chip); the ring top now clears
        # the chip bottom by 1px and its base still clears the track line
        ry = cy + 8
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
        cv.fill_rect(cx - 34, cy + 16, 68, 3, (198, 188, 158))
        # closed barrier across the track, right of the train
        cv.fill_rect(cx + 40, cy + 6, 3, 10, INK)
        cv.fill_rect(cx + 66, cy + 6, 3, 10, INK)
        for i in range(5):
            col = (248, 244, 233) if i % 2 == 0 else INK
            cv.fill_rect(cx + 43 + i * 5, cy + 8, 5, 4, col)
    elif key == "flag":
        # v2.1: layered EU-blue background (was flat solid blue) —
        # lighter blue horizon + dark floor + a ring of gold stars across
        # the sky, so the euro document reads as EU, not just money.
        cv.fill_rect(x, y + 22, w, 18, (44, 84, 150))
        cv.fill_rect(x, y + 40, w, h - 40, (30, 44, 88))
        for (sx, sy) in [(72, 8), (88, 6), (104, 9), (120, 6), (140, 8),
                         (158, 6), (174, 9)]:
            cv.fill_circle(x + sx, y + sy, 2, (250, 205, 80))
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
        # v2.1: layered Mumbai-dusk background (was flat dark, shared
        # with S12) — purple sky + orange sunset + dark ground, the
        # Gateway of India arch behind the wreath and a row of small
        # candles at the foot, so the tribute has a place, not a void.
        cv.fill_rect(x, y + 20, w, 18, (212, 128, 78))
        cv.fill_rect(x, y + 38, w, h - 38, (38, 34, 36))
        # Gateway arch silhouette, left of the wreath (below the chip)
        # v2.3: arch legs 16px (was 18) — card scene is 50px now.
        # v2.5: legs 14px — card scene is 48px now (legs end at the floor).
        cv.fill_ellipse(x + 29, y + 34, 20, 8, (30, 26, 30))
        cv.fill_rect(x + 12, y + 34, 6, 14, (30, 26, 30))
        cv.fill_rect(x + 40, y + 34, 6, 14, (30, 26, 30))
        # arch opening, sunset orange showing through (v2.1 fix: the
        # solid arch read as a dark mound; the opening makes it a gate)
        cv.fill_ellipse(x + 29, y + 38, 11, 9, (212, 128, 78))
        # row of small candles, bottom-right
        # v2.3: small candles 2px higher (card scene is 50px now).
        # v2.5: 2px higher again (card scene is 48px now; flames end
        # at y+39, bodies at y+48 = the floor).
        for ccx in (140, 155, 170):
            cv.fill_rect(x + ccx, y + 40, 3, 8, (248, 244, 233))
            cv.fill_circle(x + ccx + 1, y + 37, 2, (250, 205, 80))
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
        # v2.1: layered night background (was flat dark, shared with
        # S9) — near-black night sky + orange fire-glow horizon + dark
        # ground, a smoke column above the fire, a pale moon and a
        # fire-truck ladder reaching the second tower.
        cv.fill_rect(x, y + 22, w, 18, (196, 104, 48))
        cv.fill_rect(x, y + 40, w, h - 40, (28, 26, 26))
        cv.fill_circle(x + 168, y + 9, 5, (240, 230, 200))
        for (sx, sy, rx, ry) in [(104, 5, 6, 3), (100, 9, 5, 3),
                                 (108, 11, 4, 2)]:
            cv.fill_ellipse(x + sx, y + sy, rx, ry, (140, 136, 130))
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
        # fire-truck ladder, bottom-right to the second tower
        # v2.3: whole ladder shifted 4px up (card scene is 50px now;
        # the bottom was at y+52, past the floor).
        # v2.5: 2px higher again (card scene is 48px now; the ladder
        # feet end at y+46, clear of the floor).
        stroke3(cv, [(x + 178, y + 46), (x + 142, y + 30)], RED)
        stroke3(cv, [(x + 175, y + 46), (x + 139, y + 30)], RED)
        for (rx0, ry0) in [(167, 40), (160, 34), (153, 29), (146, 24)]:
            cv.line(x + rx0, y + ry0, x + rx0 + 3, y + ry0 - 4, RED)
    elif key == "chess":
        # v2.1: layered green-felt background (was cream = the page) —
        # dark felt top + lighter felt + wood floor, a chess clock on the
        # right and a white pawn on the left, so the match has a table,
        # a clock and two sides, not a knight floating on paper.
        cv.fill_rect(x, y + 24, w, 20, (30, 88, 54))
        cv.fill_rect(x, y + 44, w, h - 44, (96, 68, 42))
        # white pawn, left of the knight (below the chip)
        cv.fill_circle(x + 30, y + 34, 4, (248, 244, 233))
        cv.fill_rect(x + 25, y + 40, 10, 4, (248, 244, 233))
        # chess clock, right of the board
        cv.fill_rect(x + 156, y + 20, 28, 14, INK)
        cv.fill_circle(x + 164, y + 27, 4, (248, 244, 233))
        cv.fill_circle(x + 176, y + 27, 4, (248, 244, 233))
        cv.line(x + 164, y + 27, x + 164, y + 24, INK)
        cv.line(x + 176, y + 27, x + 178, y + 24, INK)
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
        # v2.1: layered Seoul-dusk background (was beige ≈ the page) —
        # teal dusk sky + lighter horizon + a dark skyline along the
        # bottom with lit windows, so the bank stands in a city, not on
        # paper. The rising-rate arrow is unchanged.
        cv.fill_rect(x, y + 20, w, 18, (56, 132, 142))
        cv.fill_rect(x, y + 38, w, h - 38, (24, 30, 36))
        # v2.3: skyline boxes + windows 4px higher (card scene is 50px
        # now; box bottoms were at y+53, past the floor).
        # v2.5: 2px higher again (card scene is 48px now; box bottoms
        # end at y+48 = the floor).
        for (bx0, by0, bw0, bh0) in [(8, 38, 10, 10), (22, 34, 12, 14),
                                     (38, 40, 10, 8), (140, 36, 12, 12),
                                     (156, 40, 10, 8), (170, 34, 12, 14)]:
            cv.fill_rect(x + bx0, y + by0, bw0, bh0, (16, 22, 28))
        for (wx, wy) in [(11, 41), (25, 37), (143, 39), (173, 37)]:
            cv.fill_rect(x + wx, y + wy, 2, 3, (250, 205, 80))
        # light pavement strip under the bank's base (the dark base
        # would otherwise vanish into the dark skyline band)
        cv.fill_rect(cx - 40, cy + 14, 68, 4, (200, 192, 172))
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
    elif key == "mine":
        # v2.5: flooded gold-mine shaft (Bogor) — dark rock walls + a
        # black shaft opening + flood water along the floor + a rescue
        # rope hanging from the top with a gold helmet + headlamp. The
        # rope/helmet sit right of centre (x+113) so the top-left chip
        # ("13 DEAD") stays clear; the water band is the flood.
        cv.fill_rect(x, y, 30, h, (60, 52, 44))
        cv.fill_rect(x + w - 30, y, 30, h, (60, 52, 44))
        cv.fill_rect(x + 30, y, w - 60, h, (18, 16, 14))
        # rock texture dots on the walls
        for (dx, dy) in [(8, 10), (18, 22), (10, 34), (172, 8), (180, 26),
                         (168, 38)]:
            cv.fill_circle(x + dx, y + dy, 2, (44, 38, 32))
        # flood water along the floor + wave dashes
        cv.fill_rect(x, y + 32, w, h - 32, (24, 72, 110))
        for wx in range(40, w - 20, 34):
            cv.fill_rect(x + wx, y + 36, 18, 2, (90, 140, 190))
        for wx in range(56, w - 20, 34):
            cv.fill_rect(x + wx, y + 42, 18, 2, (90, 140, 190))
        # rescue rope from the top + gold helmet + headlamp glow
        cv.fill_rect(x + 112, y, 2, 26, (200, 190, 160))
        cv.fill_ellipse(x + 113, y + 28, 8, 5, (250, 205, 80))
        cv.fill_circle(x + 113, y + 25, 2, (255, 255, 255))
        # bubbles rising in the water
        cv.fill_circle(x + 96, y + 38, 2, (150, 190, 220))
        cv.fill_circle(x + 128, y + 42, 2, (150, 190, 220))
    elif key == "parade":
        # v2.5: mini Macy's parade (demoted L3 -> card S12) — the same
        # motifs as the lead scene, shrunk to the 48px card box: slate
        # storm sky + rain + red balloon + small gold balloon + dark
        # skyline with lit windows + crowd dots. The balloon sits
        # centre-left, clear of the top-left chip ("100TH PARADE").
        cv.fill_rect(x, y + 20, w, 14, (72, 80, 92))
        cv.fill_rect(x, y + 34, w, h - 34, (52, 58, 66))
        # slanted rain
        for rx in range(10, w, 24):
            for ry in range(4, 30, 12):
                cv.line(x + rx, y + ry, x + rx - 6, y + ry + 4,
                        (200, 206, 214))
        # skyline along the floor
        for (bx0, bw0, bh0) in [(8, 14, 12), (26, 12, 18), (42, 16, 10),
                                (150, 12, 16), (166, 14, 12)]:
            cv.fill_rect(x + bx0, y + h - bh0, bw0, bh0, (26, 24, 20))
        for (wx, wy) in [(12, 40), (30, 34), (154, 36), (170, 40)]:
            cv.fill_rect(x + wx, y + wy, 2, 3, (250, 205, 80))
        # big red balloon + small gold balloon trailing behind
        cv.fill_ellipse(x + 78, y + 16, 16, 11, BALLOON_RED)
        cv.fill_ellipse(x + 74, y + 13, 6, 4, (205, 105, 92))
        cv.fill_ellipse(x + 122, y + 12, 8, 6, GOLD)
        # ropes trailing down from the balloon
        cv.line(x + 66, y + 24, x + 58, y + 36, (26, 24, 20))
        cv.line(x + 90, y + 24, x + 98, y + 36, (26, 24, 20))
        # crowd dots along the street
        for cxp in (30, 55, 130, 155, 175):
            cv.fill_circle(x + cxp, y + h - 4, 3, (26, 24, 20))
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
    elif key == "ebola":
        # v2.1: layered jungle background (was flat pale blue, shared
        # with S5) — deep jungle green + lighter canopy + red earth,
        # palm silhouettes at both edges and a Red Cross flag on a pole
        # beside the worker, so the treatment centre sits in Congo,
        # not on a blank blue card.
        cv.fill_rect(x, y + 20, w, 18, (64, 124, 66))
        cv.fill_rect(x, y + 38, w, h - 38, (104, 80, 50))
        # left palm
        # v2.3: palm trunks end at y+49 (was y+52, past the 50px floor).
        # v2.5: trunks end at y+48 (card scene is 48px now).
        stroke3(cv, [(x + 12, y + 48), (x + 10, y + 34)], (18, 52, 28))
        stroke3(cv, [(x + 10, y + 34), (x + 2, y + 28)], (18, 52, 28))
        stroke3(cv, [(x + 10, y + 34), (x + 20, y + 28)], (18, 52, 28))
        stroke3(cv, [(x + 10, y + 34), (x + 4, y + 38)], (18, 52, 28))
        # right palm
        # v2.3: palm trunks end at y+49 (was y+52, past the 50px floor).
        # v2.5: trunks end at y+48 (card scene is 48px now).
        stroke3(cv, [(x + 176, y + 48), (x + 178, y + 34)], (18, 52, 28))
        stroke3(cv, [(x + 178, y + 34), (x + 168, y + 28)], (18, 52, 28))
        stroke3(cv, [(x + 178, y + 34), (x + 186, y + 30)], (18, 52, 28))
        stroke3(cv, [(x + 178, y + 34), (x + 170, y + 38)], (18, 52, 28))
        # Red Cross flag on a pole, left of the worker
        cv.line(x + 118, y + 18, x + 118, y + 40, INK)
        cv.fill_rect(x + 118, y + 16, 12, 8, (248, 244, 233))
        cv.fill_rect(x + 122, y + 18, 3, 4, RED)
        cv.fill_rect(x + 120, y + 19, 7, 2, RED)
        # v2.0: Ebola treatment centre — isolation tent + PPE health
        # worker + small virus motif. Respectful, no gore: the story is
        # the outbreak's scale (12,021 cases), not suffering. The chip
        # sits top-left (45px wide), so the tent apex is kept right of
        # x+61 and the worker right of x+127 — both clear of the chip.
        # tent: white triangle, ink outline, dark door
        cv.fill_poly([(cx - 52, cy + 16), (cx - 22, cy - 14),
                      (cx + 8, cy + 16)], (248, 244, 233))
        stroke3(cv, [(cx - 52, cy + 16), (cx - 22, cy - 14),
                     (cx + 8, cy + 16), (cx - 52, cy + 16)], INK)
        cv.fill_poly([(cx - 30, cy + 16), (cx - 22, cy - 2),
                      (cx - 14, cy + 16)], (52, 48, 44))
        # PPE worker: hooded figure right of the tent
        cv.fill_circle(cx + 45, cy - 8, 8, INK)
        cv.fill_circle(cx + 45, cy - 8, 7, (168, 190, 210))
        cv.fill_ellipse(cx + 45, cy - 8, 4, 5, (52, 48, 44))
        cv.fill_poly([(cx + 34, cy + 16), (cx + 38, cy - 2),
                      (cx + 52, cy - 2), (cx + 56, cy + 16)],
                     (168, 190, 210))
        stroke3(cv, [(cx + 34, cy + 16), (cx + 38, cy - 2),
                     (cx + 52, cy - 2), (cx + 56, cy + 16),
                     (cx + 34, cy + 16)], INK)
        # virus motif, bottom-left (below the chip): spiky dark-red ball
        vx, vy = cx - 70, cy + 8
        for k in range(8):
            a = k * 3.14159265 / 4.0
            cv.line(vx + int(round(5 * _cos(a))),
                    vy + int(round(5 * _sin(a))),
                    vx + int(round(8 * _cos(a))),
                    vy + int(round(8 * _sin(a))), RED_DK)
        cv.fill_circle(vx, vy, 5, RED_DK)


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
# v2.4: pin 1 is the nor'easter (offshore New England, -66, 41 — the
# storm centre sat off the coast) and pin 2 is Washington (tariffs);
# pin 3 stays New York (Macy's), pin 6 New York (Nasdaq). The storm
# label sits south-east of its dot (+30/+16, over the Atlantic) so the
# four north-east US labels + London stay >=18px apart (audit v2.4
# first run: +22/-18 put the storm label 13px from London's).
# v2.5: pin 3 is Kuwait City (48.0, 29.4) — the new L3; pin 9 is Bogor
# (106.8, -6.6) — the new S9; pin 12 is New York (Macy's) — the demoted
# L3. Pin 6 stays New York (Nasdaq). Pin 3 label (+10/-12) clears the
# Cairo (+8/+10) and Kyiv (+16/-12) labels; pin 12 label (-16/+10)
# clears the Washington (-20/-14) and Nasdaq (+12/-10) labels; all
# label pairs >=18px (audit v2.5).
PINS = [
    (1, -66.0, 41.0, 30, 16),
    (2, -77.0, 38.9, -20, -14),
    (3, 48.0, 29.4, 10, -12),
    (4, 31.2, 30.0, 8, 10),
    (5, 30.5, 50.4, 16, -12),
    (6, -74.0, 40.7, 12, -10),
    (7, -0.1, 51.5, -22, -12),
    (8, 4.4, 50.8, 16, -16),
    (9, 106.8, -6.6, 18, -8),
    (10, 6.1, 46.2, 8, 22),
    (11, 127.0, 37.6, 10, -10),
    (12, -74.0, 40.7, -16, 10),
    # v2.0: pin 13 moves Kathmandu (85.3, 27.7) -> Beni, North Kivu, DR
    # Congo (29.6, 0.5), the Ebola outbreak's epicentre.
    (13, 29.6, 0.5, 10, 10),
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
    # v2.0: Egypt + DR Congo + Somalia read AFRICA (the new 9th region);
    # the rest of Africa stays WORLD grey, Europe = UK / EUROPE by
    # lat/lon box, Asia = MIDDLE EAST / SOUTH ASIA / EAST ASIA by
    # lat/lon box, Australia = OCEANIA).
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
                    if ci == 2:  # Africa: Egypt + DR Congo + Somalia
                        # read AFRICA (v2.0); the rest stays WORLD grey
                        if (25 <= lon <= 36 and 22 <= lat <= 32) or \
                           (12 <= lon <= 31 and -13 <= lat <= 5) or \
                           (40 <= lon <= 51 and -2 <= lat <= 12):
                            reg = "AFRICA"
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
    # top strip — v2.3: advance 13 -> 12 (funds the bigger masthead)
    draw_text(cv, MX, y + 11, "THE WORLD IN ONE DAY", 11, True, INK)
    draw_text(cv, MX + CW, y + 11, "43 STORIES · 9 REGIONS · THURSDAY 26 NOVEMBER 2026",
              11, True, INK, "r")
    y += 12
    cv.hline(MX, y, CW, RULE, 2)
    y += 6
    # masthead — v2.3: 52 -> 64px (dense core ~30px; top #9 is 30px,
    # #10 is 28px). Measured 64px = ~791px wide, fits the 976px line.
    # Baseline y+53, advance 51 -> 63 (costs +12, funded below).
    draw_text(cv, MX + CW // 2, y + 53, "Thursday 26 November 2026", 64, True,
              INK, "c")
    y += 63
    # red deck line: the three leads in one line — v2.5: L3 is Kuwait now.
    draw_text(cv, MX + CW // 2, y + 12,
              "Nor’easter cuts power to ~1M · US proposes tariffs on 14 "
              "partners · Kuwait drone kills 2 Italians",
              13, True, RED, "c")
    y += 15
    cv.hline(MX, y, CW, RULE, 1)
    y += 5
    # stat strip: 6 callouts — v1.7: values 22 -> 32px (top-10 median
    # 32-35px; ours were the smallest stat numbers in the set).
    # v2.3: advance 43 -> 37 (values y+23, labels y+34, vline 32px).
    # v2.5: advance 37 -> 34 (values 30px at y+21, labels y+31, vline
    # 28px) — funds the ALSO floor. Values stay >=30px (top-10 median).
    sw = CW // 6
    for i, (val, lab) in enumerate(STATS):
        bx = MX + i * sw
        if i:
            cv.vline(bx, y + 3, 28, (200, 192, 172), 1)
        draw_text(cv, bx + sw // 2, y + 21, val, 30, True, RED_DK, "c")
        draw_text(cv, bx + sw // 2, y + 31, lab, 9, True, INK_SOFT, "c")
    y += 34
    cv.hline(MX, y, CW, RULE, 1)
    y += 3
    # region bar: segments proportional to story counts (must total 43) —
    # v1.7: 8 segments; the last takes the remainder so rounding never
    # overshoots the 976px content width by a pixel.
    # v2.3: 9 segments, totals 40. Only SOUTH ASIA 2 is narrow now
    # (49px); its label shrinks to 6px ("SOUTH ASIA 2" is 48px at 7px,
    # 41px at 6px — the loop floor is 6px so it fits with margin).
    # v2.5: 9 segments, totals 43 (SOUTH ASIA 2 is 45px at /43).
    total = sum(c for (_, c, _) in REGION_COLORS)
    assert total == 43, total
    rx = MX
    for si, (name, count, col) in enumerate(REGION_COLORS):
        seg = int(round(CW * count / 43.0)) if si < len(REGION_COLORS) - 1 \
            else MX + CW - rx
        cv.fill_rect(rx, y, seg, 17, col)
        label = "%s %d" % (name, count)
        rsize = 10
        while rsize > 6 and text_width(label, rsize, True) > seg - 2:
            rsize -= 1
        draw_text(cv, rx + seg // 2, y + 11 + int(rsize * 0.35), label,
                  rsize, True, (255, 255, 255), "c")
        rx += seg
    y += 17
    # v1.7: FIELDS strip — the same 43 stories by topic (see FIELDS above),
    # the taxonomy strip the top entries carry (hwang-steven 21 fields,
    # tidy-meteor 20 fields + 8 stats). One thin PAPER_DIM band.
    # v2.3: band 16 -> 13px, text baseline y+11, advance 15 -> 13.
    # v2.5: band 13 -> 11px, text 8px baseline y+9, advance 13 -> 11 —
    # funds the ALSO floor.
    cv.fill_rect(MX, y, CW, 11, PAPER_DIM)
    fields_txt = "FIELDS   " + "  ·  ".join("%s %d" % (n, c)
                                            for (n, c) in FIELDS)
    draw_text(cv, MX + CW // 2, y + 9, fields_txt, 8, True, INK, "c")
    y += 11
    # timeline: THE DAY IN UTC — title at left, nodes shifted right of it
    # v2.3: tl_y y+18 (was y+20), advance 45 -> 42.
    # v2.5: tl_y y+14, advance 42 -> 32 — labels are ONE line now (see
    # TIMELINE), so the block needs only tl_y+17; funds the ALSO floor.
    tl_y = y + 14
    draw_text(cv, MX, tl_y + 4, "THE DAY IN UTC", 10, True, INK)
    cv.hline(MX + 150, tl_y, CW - 150, INK_SOFT, 1)
    tw = (CW - 150) // 6
    for i, (tm, lab) in enumerate(TIMELINE):
        cx = MX + 150 + tw * i + tw // 2
        cv.fill_circle(cx, tl_y, 4, RED)
        draw_text(cv, cx, tl_y - 5, tm, 11, True, RED_DK, "c")
        lines = wrap_text(lab, 9, False, tw - 14)
        draw_lines(cv, cx - (tw - 14) // 2, tl_y + 6, lines, 9, 10,
                   False, INK_SOFT, "l", tw - 14)
    y += 32
    # ---- three leads
    lw = (CW - 2 * 11) // 3
    lead_top = y
    for i, lead in enumerate(LEADS):
        lx = MX + i * (lw + 11)
        draw_text(cv, lx, y + 11, "%d · %s" % (lead["num"], lead["kick"]), 10,
                  True, RED_DK)
        pw = draw_pill(cv, lx + lw - 62, y, lead["pill"])
        SCENES[lead["scene"]](cv, lx, y + 16, lw, 110)
        hy = y + 16 + 110 + 6  # v2.2: was 64 — headline sat on the hero
        lines = wrap_text(lead["head"], 20, True, lw)
        draw_lines(cv, lx, hy, lines, 20, 21, True, INK)
        dy = hy + 21 * len(lines) + 2
        dlines = wrap_text(lead["deck"], 11, False, lw)
        draw_lines(cv, lx, dy, dlines, 11, 12, False, INK_SOFT)
        # v2.0: WHY IT MATTERS, one red bold line under each lead deck.
        # Decks are 2 lines now (L1/L3 trimmed, L2 already was), so the
        # row advance is unchanged: 2*12 deck + 12 WHY = the old 3*12
        # deck, and the meta lands exactly where it did in v1.9.
        wy = dy + 12 * len(dlines) + 12
        draw_text(cv, lx, wy, lead["why"], 10, True, RED)
        my = wy + 8
        draw_text(cv, lx, my, lead["meta"], 9, False, INK_SOFT)
    y = lead_top + 16 + 110 + 6 + 2 * 21 + 2 + 2 * 12 + 12 + 8 + 3
    cv.hline(MX, y, CW, (200, 192, 172), 1)
    y += 3  # v2.3: was 4 (funds the bigger masthead + ALSO floor)
    # ---- small cards: 5 across x 2 rows
    # v1.7: each card is a mini-scene — the v1.5 illustration is drawn
    # natively into a 187x60 scene box (same absolute motif size as v1.5,
    # centred, edges crisp, no scaling), with the two-line coloured chip
    # INSIDE the scene's top-left corner (the v1.6 black full-width band is
    # gone). Kicker/headline/deck keep the v1.6 geometry below the scene.
    # v2.3: cardh 138 -> 134, scene 54 -> 50 (kicker +58, pill +52,
    # headline +66); funds the bigger masthead + ALSO floor.
    # v2.5: cardh 134 -> 130, scene 50 -> 48 (kicker +56, pill +50,
    # headline +64); headline leading 15 -> 14, deck leading 12 -> 11 —
    # a 2-line head + 3-line deck card now ends at cy0+128 (was cy0+134),
    # 6px clear of the next row; funds the ALSO floor.
    cardw = (CW - 4 * 10) // 5
    cardh = 130
    for row in range(2):
        for col in range(5):
            idx = row * 5 + col
            num, kick, pill, head, deck, icon = SMALL[idx]
            cx0 = MX + col * (cardw + 10)
            cy0 = y + row * (cardh + 4)
            draw_icon(cv, cx0, cy0, cardw, 48, icon)
            cn, cl, creg = CHIPS[num]
            cdx, cdy = CHIP_POS.get(num, (4, 2))
            draw_chip(cv, cx0 + cdx, cy0 + cdy, cn, cl, creg)
            draw_text(cv, cx0, cy0 + 56, "%d · %s" % (num, kick), 9, True,
                      RED_DK)
            pw = draw_pill(cv, cx0 + cardw - 58, cy0 + 50, pill)
            hlines = wrap_text(head, 14, True, cardw)
            draw_lines(cv, cx0, cy0 + 64, hlines, 14, 14, True, INK)
            dlines = wrap_text(deck, 11, False, cardw)
            draw_lines(cv, cx0, cy0 + 64 + 14 * len(hlines) + 2, dlines,
                       11, 11, False, INK_SOFT)
    y += 2 * cardh + 4
    cv.hline(MX, y, CW, (200, 192, 172), 1)
    y += 3  # v2.3: was 4 (funds the bigger masthead + ALSO floor)
    # ---- map LEFT + ALSO list RIGHT
    mapw = 300
    maph = 152
    draw_text(cv, MX, y + 11, "WHERE IT HAPPENED — STORIES 1–13", 11, True,
              INK)
    draw_map(cv, MX, y + 16, mapw, maph - 16)
    draw_text(cv, MX, y + maph + 4,
              "Pins match story numbers 1–13; colours show region.", 9,
              False, INK_SOFT)
    ax = MX + mapw + 14
    aw = CW - mapw - 14
    # v2.5: 30 ALSO items in 3 columns of 10 (was 27 in 3 columns of 9).
    draw_text(cv, ax, y + 11, "ALSO ON THURSDAY 26 NOVEMBER — 30 MORE STORIES",
              11, True, INK)
    colw = (aw - 2 * 12) // 3
    for ci in range(3):
        col_items = ALSO[ci * 10:(ci + 1) * 10]
        cxx = ax + ci * (colw + 12)
        for ri, (item, reg, outlet) in enumerate(col_items):
            n = ci * 10 + ri + 1
            yy = y + 18 + ri * 20
            # v1.7: number in the story's region colour (darkened, so the
            # gold UK number still reads on cream) + verified outlet at
            # the end of the item — every ALSO item has one (RESEARCH.md)
            draw_text(cv, cxx, yy + 10, "%d." % n, 10, True,
                      CHIP_COLORS[reg])
            text = item + " (%s)" % outlet
            lines = wrap_text(text, 10, False, colw - 18)
            draw_lines(cv, cxx + 18, yy, lines[:2], 10, 11, False, INK)
    # v2.5: ALSO floor 200 -> 220 (10 rows end y+209; map 152). Funded by
    # timeline −10, stat −3, FIELDS −2, cards −8 = −23; net −3, so the
    # footer that touched the bottom edge in v2.4 (0px margin) now has 3px.
    y += 220  # v2.5: ALSO floor (10 rows end y+209); map 152
    # ---- DATE CHECK, red-bordered
    dc_top = y
    cv.rect(MX, y, CW, 2, RED, 2)
    draw_text(cv, MX + 8, y + 14, "DATE CHECK", 11, True, RED)
    draw_text(cv, MX + 96, y + 14,
              "Every story above happened or was first reported or developing "
              "on Thursday 26 November 2026 (UTC). Left out as earlier news:",
              9, False, INK_SOFT)
    dc_y = y + 16  # v2.3: was y+18 (funds the bigger masthead + ALSO floor)
    # v1.6: the 12 DATE CHECK items as flowing prose (same items, same
    # words, same order — only the grid layout is gone), the shape the top
    # entries use. Measured: 3 lines at 9px (2 lines is not reachable at a
    # readable size: 707 chars need ~2,900px at 9px vs 960px available).
    # Frees ~29px vs the grid — that funds the card chips + 11px decks.
    dc_prose = "  ·  ".join("%d. %s" % (i + 1, it)
                            for i, it in enumerate(DATE_CHECK))
    plines = wrap_text(dc_prose, 9, False, CW - 16)
    draw_lines(cv, MX + 8, dc_y, plines, 9, 10, False, INK)
    dc_y += 10 * len(plines) + 1  # v2.3: was +2 (funds the ALSO floor)
    # MORE row: +50% word spacing (space 2.0 -> 3.0px at 8px), leading 10 -> 11,
    # max width 960 -> 944 so no line ends near the right border; the 2px
    # saved in the gap above keeps the page bottom margin unchanged.
    mlines = wrap_text(MORE_CHECKED, 8, False, CW - 32, space_extra=1.0)
    draw_lines(cv, MX + 8, dc_y, mlines, 8, 10, False, INK_SOFT,
               space_extra=1.0)
    dc_bottom = dc_y + 10 * len(mlines) + 2  # v2.3: was +4
    cv.rect(MX, dc_top, CW, dc_bottom - dc_top, RED, 2)
    y = dc_bottom + 3
    # ---- footer — v2.3: advances 10 -> 9 (funds the ALSO floor)
    draw_text(cv, MX, y + 8,
              "OFFICIAL = authority’s own figure or act · REPORTED = press "
              "report · CLAIM = one side’s account. Drawn from verified "
              "reporting; every story first reported or developing Thu 26 Nov "
              "2026 unless dated in DATE CHECK.", 9, False, INK_SOFT)
    y += 9
    draw_text(cv, MX, y + 8,
              "Sources: Reuters, AP, BBC, CNN, Yonhap, TfL, FIDE, The Hindu, "
              "Guardian, Africanews, ONS", 9, False, INK_SOFT)
    y += 9
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
