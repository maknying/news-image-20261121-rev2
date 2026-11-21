#!/usr/bin/env python3
"""The World in One Page — Saturday 21 November 2026.

A one-page newspaper drawn entirely by this program: stdlib only, no
network, no clock, no randomness, so two runs write identical bytes.
It reads a pre-rendered glyph atlas (atlas.bin) sitting next to it,
paints the page into an RGB buffer and encodes that buffer as PNG.

The page: a masthead with the date, a lead story (COP31 overtime) beside
a drawn globe, then 28 more stories grouped into 7 regions over two
columns, and a band of numbers at the foot. 29 stories in all, every one
real and reported on 21 November 2026 (see SOURCES.md in the work
directory for the source of each story).
"""

import math
import os
import struct
import sys
import zlib

PAGE_W = 1024
PAGE_H = 1024

PAPER = (248, 243, 231)
INK = (24, 23, 20)
RED = (176, 36, 28)
BLUE = (28, 76, 138)
TEAL = (14, 110, 105)
FAINT = (170, 160, 142)
WHITE = (255, 255, 255)
SKY = (214, 230, 242)

BOLD = 1
PLAIN = 0


# ------------------------------------------------------------------ atlas
def read_atlas(path):
    """Read atlas.bin into {(bold, size): (ascent, descent, glyphs)}."""
    with open(path, "rb") as handle:
        blob = handle.read()
    if blob[:7] != b"ATLAS1\n":
        raise ValueError("atlas.bin has the wrong magic")
    pos = 7
    (count,) = struct.unpack_from(">I", blob, pos)
    pos += 4
    faces = {}
    for _ in range(count):
        bold, size, ascent, descent = struct.unpack_from(">HBHH", blob, pos)
        pos += 7
        (nglyphs,) = struct.unpack_from(">H", blob, pos)
        pos += 2
        glyphs = {}
        for _ in range(nglyphs):
            code, xoff, yoff, gw, gh, adv = struct.unpack_from(
                ">IhhHHH", blob, pos)
            pos += 14
            (nbytes,) = struct.unpack_from(">I", blob, pos)
            pos += 4
            glyphs[code] = (xoff, yoff, gw, gh, adv, blob[pos:pos + nbytes])
            pos += nbytes
        faces[(bold, size)] = (ascent, descent, glyphs)
    return faces


# ----------------------------------------------------------------- canvas
class Canvas:
    """An RGB pixel buffer with rectangle, line and circle primitives."""

    def __init__(self, width, height, background):
        self.width = width
        self.height = height
        self.pixels = bytearray(bytes(background) * width * height)

    def set_px(self, x, y, colour):
        if 0 <= x < self.width and 0 <= y < self.height:
            at = (y * self.width + x) * 3
            self.pixels[at:at + 3] = bytes(colour)

    def fill(self, x, y, w, h, colour):
        x0 = max(0, x)
        y0 = max(0, y)
        x1 = min(self.width, x + w)
        y1 = min(self.height, y + h)
        if x1 <= x0 or y1 <= y0:
            return
        row = bytes(colour) * (x1 - x0)
        for yy in range(y0, y1):
            at = (yy * self.width + x0) * 3
            self.pixels[at:at + len(row)] = row

    def rule(self, x, y, w, colour, thick=1):
        self.fill(x, y, w, thick, colour)

    def frame(self, x, y, w, h, colour, thick=1):
        self.fill(x, y, w, thick, colour)
        self.fill(x, y + h - thick, w, thick, colour)
        self.fill(x, y, thick, h, colour)
        self.fill(x + w - thick, y, thick, h, colour)

    def line(self, x0, y0, x1, y1, colour):
        """Bresenham line."""
        dx = abs(x1 - x0)
        dy = -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        while True:
            self.set_px(x0, y0, colour)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy

    def fill_circle(self, cx, cy, r, colour):
        for yy in range(cy - r, cy + r + 1):
            dy = yy - cy
            half = int(math.sqrt(max(0, r * r - dy * dy)))
            self.fill(cx - half, yy, half * 2 + 1, 1, colour)

    def circle(self, cx, cy, r, colour, thick=1):
        for t in range(thick):
            rr = r - t
            steps = max(64, int(2 * math.pi * rr))
            for i in range(steps):
                a = 2 * math.pi * i / steps
                self.set_px(cx + int(rr * math.cos(a)),
                            cy + int(rr * math.sin(a)), colour)

    def ellipse(self, cx, cy, a, b, colour):
        steps = max(64, int(2 * math.pi * max(a, b)))
        for i in range(steps):
            ang = 2 * math.pi * i / steps
            self.set_px(cx + int(a * math.cos(ang)),
                        cy + int(b * math.sin(ang)), colour)

    def chord(self, cx, cy, r, dy, colour):
        """Horizontal chord of a circle, dy below centre."""
        half = int(math.sqrt(max(0, r * r - dy * dy)))
        self.fill(cx - half, cy + dy, half * 2 + 1, 1, colour)


# ------------------------------------------------------------------- text
def find_glyph(faces, face, char):
    _, _, glyphs = faces[face]
    found = glyphs.get(ord(char))
    if found is None:
        found = glyphs.get(ord("?"))
    return found


def measure_text(faces, face, text, tracking=0):
    total = 0
    for char in text:
        total += find_glyph(faces, face, char)[4] + tracking
    return total - tracking if text else 0


def row_height(faces, face):
    ascent, descent, _ = faces[face]
    return ascent + descent


def paint_text(page, faces, face, x, y_top, text, colour, tracking=0):
    """Paint text; returns the pen x after the last glyph."""
    ascent, _, _ = faces[face]
    baseline = y_top + ascent
    pen = x
    for char in text:
        xoff, yoff, gw, gh, adv, bits = find_glyph(faces, face, char)
        if gw and gh:
            row_bytes = (gw + 7) // 8
            for gy in range(gh):
                yy = baseline - ascent + yoff + gy
                if yy < 0 or yy >= page.height:
                    continue
                for bx in range(row_bytes):
                    byte = bits[gy * row_bytes + bx]
                    if not byte:
                        continue
                    for bit in range(8):
                        if byte & (0x80 >> bit):
                            xx = pen + xoff + bx * 8 + bit
                            if 0 <= xx < page.width:
                                at = (yy * page.width + xx) * 3
                                page.pixels[at:at + 3] = bytes(colour)
        pen += adv + tracking
    return pen


def paint_centred(page, faces, face, cx, y_top, text, colour, tracking=0):
    width = measure_text(faces, face, text, tracking)
    paint_text(page, faces, face, cx - width // 2, y_top, text,
               colour, tracking)


def wrap_text(faces, face, text, max_width, tracking=0):
    lines = []
    for chunk in text.split("\n"):
        words = chunk.split(" ")
        current = ""
        for word in words:
            trial = word if not current else current + " " + word
            if not current or measure_text(faces, face, trial, tracking) <= max_width:
                current = trial
            else:
                lines.append(current)
                current = word
        lines.append(current)
    return lines


def paint_paragraph(page, faces, face, x, y_top, text, max_width,
                    colour, gap=3, tracking=0):
    step = row_height(faces, face) + gap
    y = y_top
    for line in wrap_text(faces, face, text, max_width, tracking):
        paint_text(page, faces, face, x, y, line, colour, tracking)
        y += step
    return y


# -------------------------------------------------------------------- png
def encode_png(page):
    raw = bytearray()
    stride = page.width * 3
    for yy in range(page.height):
        raw.append(0)
        raw += page.pixels[yy * stride:(yy + 1) * stride]
    payload = zlib.compress(bytes(raw), 9)

    def chunk(kind, data):
        out = struct.pack(">I", len(data)) + kind + data
        return out + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    header = struct.pack(">IIBBBBB", page.width, page.height, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header)
            + chunk(b"IDAT", payload) + chunk(b"IEND", b""))


# ---------------------------------------------------------------- content
MASTHEAD = "THE WORLD IN ONE PAGE"
DATE_LINE = "SATURDAY, 21 NOVEMBER 2026"
TAG_LINE = "29 STORIES  \u00b7  7 REGIONS  \u00b7  ONE DAY"

LEAD_KICKER = "ANTALYA \u2014 COP31 IN OVERTIME"
LEAD_LINES = ["COP31 runs into overtime", "as fossil fuels vanish"]
LEAD_TEXT = (
    "The summit missed its Friday deadline after the draft dropped fossil "
    "fuels and a $120bn fund. Talks run on."
)

# (region kicker, colour, [(dateline, one-line story), ...])
REGIONS_LEFT = [
    ("MIDDLE EAST", RED, [
        ("RIYADH", "3 Houthi missiles downed; 2nd raid in days."),
        ("HODEIDAH", "Coalition hits port, Sanaa after raids."),
        ("HORMUZ", "Tanker attacks at monthly high; no hurt."),
        ("LEBANON", "Israeli strikes hit four southern districts."),
    ]),
    ("EUROPE", BLUE, [
        ("COPENHAGEN", "Envoy to be expelled over murder plot."),
        ("BERLIN", "Defence chief sorry for \u2018stupid\u2019 remark."),
        ("PARIS", "Police sentenced over racist beating."),
        ("ISTANBUL", "Turkey takes control of Sozcu TV."),
    ]),
    ("UKRAINE WAR", TEAL, [
        ("KRYVYI RIH", "Missile kills 2, wounds 60 in hometown."),
        ("KYIV", "Bridges hit, power cut in mass strike."),
        ("CRIMEA", "Zelensky: the bridge \u2018won\u2019t remain\u2019."),
        ("UKRAINE", "148 drones in a night; 117 shot down."),
    ]),
]

REGIONS_RIGHT = [
    ("AMERICAS", RED, [
        ("SINALOA", "FBI most-wanted cartel boss captured."),
        ("SAN SALVADOR", "Bukele seeks an unusual third term."),
        ("BRAZIL", "Bacteria mosquitoes cut dengue cases 69%."),
        ("HAITI", "Salvadoran troops fight gangs in capital."),
    ]),
    ("ASIA-PACIFIC", BLUE, [
        ("SHENZHEN", "Trump, Xi, Putin sign joint peace pact."),
        ("DHAKA", "50 Awami League homes burnt before return."),
        ("JAKARTA", "Daycare head jailed 5 years over abuse."),
        ("THE HAGUE", "ICJ: Myanmar guilty of genocide."),
    ]),
    ("MARKETS & TECH", TEAL, [
        ("NEW YORK", "S&P falls 3.7% as AI sell-off spreads."),
        ("WALL ST", "Anthropic debuts as a $2 trillion firm."),
        ("CHIPS", "Nvidia halts H200 exports to China."),
        ("CALIFORNIA", "State probes Nvidia over ex-chief affair."),
    ]),
    ("SCIENCE & WORLD", RED, [
        ("SPACE", "BepiColombo reaches Mercury orbit at last."),
        ("STRAIT", "Swimmer Pugh crosses Hormuz for wildlife."),
        ("GENEVA", "UN AI-weapons talks go on; no treaty yet."),
        ("ETHIOPIA", "700,000 displaced in the south."),
    ]),
]

STATS = [
    ("3", "missiles downed\nover Riyadh"),
    ("3.7%", "S&P 500 fall\nin a day"),
    ("700,000", "displaced in\nsouthern Ethiopia"),
    ("69%", "dengue cut\nin Brazil"),
]

FOOT_A = ("Sources: Reuters \u00b7 AP \u00b7 AFP \u00b7 NYT \u00b7 DW \u00b7 CBC \u00b7 UKMTO"
          "  \u2014  Events of Saturday 21 November 2026")
FOOT_B = ("29 stories \u00b7 7 regions \u2014 Drawn by a program. No network, "
          "no AI images; every word set in type.")


# ------------------------------------------------------------------ layout
def paint_item(page, faces, x, y, width, dateline, text):
    """One story on a single line: bold dateline, regular rest."""
    head = dateline + " \u2014 "
    after = paint_text(page, faces, (BOLD, 16), x, y, head, INK)
    paint_text(page, faces, (PLAIN, 16), after, y, text, INK)
    total = measure_text(faces, (BOLD, 16), head) + \
        measure_text(faces, (PLAIN, 16), text)
    if total > width:
        raise ValueError("item too wide for column: %s %s (%d > %d)"
                         % (dateline, text, total, width))
    return y + 20


def paint_column(page, faces, x, width, y, regions):
    for kicker, colour, items in regions:
        paint_text(page, faces, (BOLD, 19), x, y, kicker, colour,
                   tracking=1)
        page.rule(x, y + 26, 52, colour, 3)
        y += 32
        for dateline, text in items:
            y = paint_item(page, faces, x, y, width, dateline, text)
        y += 8
    return y


def paint_globe(page, cx, cy, r):
    page.fill_circle(cx, cy, r, BLUE)
    page.circle(cx, cy, r, INK, 2)
    page.circle(cx, cy, r + 7, INK, 1)
    page.ellipse(cx, cy, 26, r - 4, WHITE)
    page.ellipse(cx, cy, r - 4, 26, WHITE)
    page.chord(cx, cy, r - 2, -30, WHITE)
    page.chord(cx, cy, r - 2, 30, WHITE)
    page.fill_circle(cx + 44, cy - 46, 5, RED)


def render(faces):
    page = Canvas(PAGE_W, PAGE_H, PAPER)
    page.frame(14, 14, PAGE_W - 28, PAGE_H - 28, INK, 2)
    page.frame(20, 20, PAGE_W - 40, PAGE_H - 40, INK, 1)

    paint_centred(page, faces, (BOLD, 64), PAGE_W // 2, 32, MASTHEAD, INK)
    paint_centred(page, faces, (BOLD, 22), PAGE_W // 2, 112, DATE_LINE, RED)
    paint_centred(page, faces, (PLAIN, 18), PAGE_W // 2, 142, TAG_LINE,
                  INK, tracking=3)
    page.rule(36, 172, PAGE_W - 72, INK, 5)
    page.rule(36, 181, PAGE_W - 72, INK, 1)

    # Lead story, left; drawn globe, right.
    paint_text(page, faces, (BOLD, 19), 36, 192, LEAD_KICKER, RED,
               tracking=1)
    y = 216
    for line in LEAD_LINES:
        paint_text(page, faces, (BOLD, 34), 36, y, line, INK)
        y += row_height(faces, (BOLD, 34)) + 2
    y += 4
    y = paint_paragraph(page, faces, (PLAIN, 22), 36, y, LEAD_TEXT, 664,
                        INK, gap=3)
    paint_globe(page, 852, 272, 70)
    page.rule(36, 364, PAGE_W - 72, FAINT, 1)

    # Region grid, two columns.
    left_end = paint_column(page, faces, 36, 469, 376, REGIONS_LEFT)
    right_end = paint_column(page, faces, 519, 469, 376, REGIONS_RIGHT)
    grid_end = max(left_end, right_end)
    page.fill(512, 378, 1, grid_end - 384, FAINT)

    # Numbers band.
    band_y = grid_end + 10
    band_h = 80
    page.frame(36, band_y, PAGE_W - 72, band_h, INK, 1)
    cell_w = (PAGE_W - 72) // 4
    for i, (big, small) in enumerate(STATS):
        cx = 36 + cell_w * i
        if i:
            page.fill(cx, band_y + 8, 1, band_h - 16, FAINT)
        paint_centred(page, faces, (BOLD, 34), cx + cell_w // 2,
                      band_y + 6, big, RED)
        for j, line in enumerate(small.split("\n")):
            paint_centred(page, faces, (PLAIN, 16), cx + cell_w // 2,
                          band_y + 44 + j * 18, line, INK)

    page.rule(36, 950, PAGE_W - 72, INK, 1)
    paint_centred(page, faces, (PLAIN, 14), PAGE_W // 2, 958, FOOT_A, INK)
    paint_centred(page, faces, (PLAIN, 14), PAGE_W // 2, 978, FOOT_B, INK)
    return page


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    faces = read_atlas(os.path.join(here, "atlas.bin"))
    data = encode_png(render(faces))
    outdir = os.environ.get("MAKEFUN_OUTPUT_DIR")
    if not outdir:
        outdir = "/output" if os.path.isdir("/output") else "out"
    os.makedirs(outdir, exist_ok=True)
    path = os.path.join(outdir, "entry.png")
    with open(path, "wb") as handle:
        handle.write(data)
    sys.stdout.write("wrote %s (%d bytes)\n" % (path, len(data)))


if __name__ == "__main__":
    main()
