# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "uharfbuzz==0.57.0",
#   "fonttools==4.67.0",
#   "resvg-py==0.5.0",
#   "pillow==13.0.0",
# ]
# ///
"""Draw Marjaa's logo, icon, favicon and Open Graph files (docs/brand.md).

    uv run scripts/build_brand.py

Downloads Reem Kufi and IBM Plex Sans from the Google Fonts repository (pinned
commit, SIL Open Font License) into .cache/brand-fonts, shapes the text with
HarfBuzz so the Arabic letters join correctly, and converts every glyph to an
SVG path. The files therefore need no fonts to render. Writes:

  web/public/brand/                 logo, icon and favicon SVGs and PNGs, og.png
  web/src/app/favicon.ico           16, 32 and 48 px, served at /favicon.ico
  web/src/components/brand/glyphs.ts  the same outlines for the React logo
"""

from __future__ import annotations

import io
import json
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import resvg_py
import uharfbuzz as hb
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / ".cache" / "brand-fonts"
OUT = ROOT / "web" / "public" / "brand"
GLYPHS_TS = ROOT / "web" / "src" / "components" / "brand" / "glyphs.ts"
FAVICON_ICO = ROOT / "web" / "src" / "app" / "favicon.ico"

FONTS_COMMIT = "5bb28733cec313b63fbd415b574b5ae35c8aa8b8"  # google/fonts, 2026-11-08
FONTS = {
    "reem": "ofl/reemkufi/ReemKufi%5Bwght%5D.ttf",
    "plex": "ofl/ibmplexsans/IBMPlexSans%5Bwdth%2Cwght%5D.ttf",
}

# Brand colours (web/src/app/tokens.css)
PEARL, SAND, SEA, GOLD, DATE = "#FAF7F1", "#F3EBDD", "#4F7C7A", "#C9A46A", "#3A2E26"

WORDMARK = "مرجع"
LATIN = "MARJAA"
TRACKING = 0.26  # em, for MARJAA

# The Sadu tile: 20 x 18 units, a large triangle with a small one inside it.
TILE_W, TILE_H = 20, 18
BIG = [(0, 18), (10, 0), (20, 18)]
SMALL = [(5, 18), (10, 9), (15, 18)]


def font_path(name: str) -> Path:
    path = CACHE / f"{name}.ttf"
    if not path.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        url = f"https://raw.githubusercontent.com/google/fonts/{FONTS_COMMIT}/{FONTS[name]}"
        with urllib.request.urlopen(url, timeout=60) as r:
            path.write_bytes(r.read())
    return path


def num(v: float) -> str:
    s = f"{v:.2f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


@dataclass
class Text:
    """Shaped text as one SVG path, placed with its ink box's top-left at (0, 0)."""

    d: str
    width: float
    height: float
    baseline: float  # distance from the ink top down to the baseline


def shape(name: str, text: str, size: float, weight: int, tracking: float = 0.0) -> Text:
    """Shape `text` at `size` px and return its outline, normalised to its ink box."""
    face = hb.Face(hb.Blob.from_file_path(str(font_path(name))))
    font = hb.Font(face)
    font.set_variations({"wght": weight})
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(font, buf, {"kern": True, "liga": True})
    scale = size / face.upem
    infos, positions = buf.glyph_infos, buf.glyph_positions

    def draw(pen_factory, dx: float, dy: float):
        x = 0.0
        for i, (info, pos) in enumerate(zip(infos, positions, strict=True)):
            t = (scale, 0, 0, -scale, dx + (x + pos.x_offset) * scale, dy - pos.y_offset * scale)
            font.draw_glyph_with_pen(info.codepoint, TransformPen(pen_factory, t))
            x += pos.x_advance
            if tracking and i < len(infos) - 1 and pos.x_advance:
                x += tracking * face.upem

    bounds = BoundsPen(None)
    draw(bounds, 0, 0)
    x0, y0, x1, y1 = bounds.bounds  # y is already flipped: y0 is the top
    svg = SVGPathPen(None, ntos=num)
    draw(svg, -x0, -y0)
    return Text(d=svg.getCommands(), width=x1 - x0, height=y1 - y0, baseline=-y0)


def poly(points, ox: float, oy: float, k: float) -> str:
    return " ".join(f"{num(ox + x * k)},{num(oy + y * k)}" for x, y in points)


def paint(fill: str) -> str:
    """A colour for the static files, or a class for the web app's themed copy."""
    return f'fill="{fill}"' if fill.startswith("#") else f'class="{fill}"'


def band(
    x: float,
    y: float,
    tiles: int,
    tile_w: float,
    big: str,
    small: str | None,
    animated: bool = False,
) -> str:
    """A row of Sadu tiles starting at (x, y). `small=None` draws the one-colour band.
    `animated` groups each tile for the web app's draw-in (globals.css .sadu-draw)."""
    k = tile_w / TILE_W
    out = []
    for i in range(tiles):
        ox = x + i * tile_w
        tile = f'<polygon points="{poly(BIG, ox, y, k)}" {paint(big)}/>'
        if small:
            tile += f'<polygon points="{poly(SMALL, ox, y, k)}" {paint(small)}/>'
        out.append(f'<g class="sadu-tile" style="--i:{i}">{tile}</g>' if animated else tile)
    return "".join(out)


def path(t: Text, x: float, y: float, fill: str) -> str:
    return f'<path transform="translate({num(x)} {num(y)})" {paint(fill)} d="{t.d}"/>'


def svg(w: float, h: float, body: str, title: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {num(w)} {num(h)}" '
        f'width="{num(w)}" height="{num(h)}" role="img" aria-label="{title}">'
        f"<title>{title}</title>{body}</svg>\n"
    )


# ---------------------------------------------------------------- the logo

PRIMARY_TILES = 9  # the band spans the wordmark in this many tiles


def stacked(
    wordmark_w: float, ink: str, band_big: str, band_small: str, pad: float, animated: bool = False
):
    """The primary lockup: wordmark, Sadu band, MARJAA. Returns (w, h, body)."""
    tile_w = wordmark_w / PRIMARY_TILES
    band_h = tile_w * TILE_H / TILE_W
    word = shape("reem", WORDMARK, 100, 700)
    word = shape("reem", WORDMARK, 100 * wordmark_w / word.width, 700)
    latin = shape("plex", LATIN, band_h * 0.8 / 0.698, 600, TRACKING)  # cap height: 0.8 of the band
    gap1, gap2 = band_h * 0.55, band_h * 0.8
    width = wordmark_w + 2 * pad
    y_band = pad + word.height + gap1
    y_latin = y_band + band_h + gap2
    height = y_latin + latin.height + pad
    body = (
        path(word, pad, pad, ink)
        + band(pad, y_band, PRIMARY_TILES, tile_w, band_big, band_small, animated)
        + path(latin, (width - latin.width) / 2, y_latin, ink)
    )
    return width, height, body, {"word": word, "latin": latin, "band_h": band_h, "tile_w": tile_w}


def header_lockup(word_h: float, ink: str, sea: str, animated: bool = False):
    """Compact horizontal lockup: wordmark over a thin one-colour band, MARJAA beside it."""
    word = shape("reem", WORDMARK, 100, 700)
    word = shape("reem", WORDMARK, 100 * word_h / word.height, 700)
    tiles = 14
    tile_w = word.width / tiles
    band_h = tile_w * TILE_H / TILE_W
    gap = band_h * 0.6
    block_h = word.height + gap + band_h
    latin = shape("plex", LATIN, block_h * 0.3 / 0.698, 600, TRACKING)
    space = word.height * 0.42
    width = word.width + space + latin.width
    body = (
        path(word, 0, 0, ink)
        + band(0, word.height + gap, tiles, tile_w, sea, None, animated)
        + path(latin, word.width + space, (block_h - latin.height) / 2, ink)
    )
    return width, block_h, body


# ---------------------------------------------------------------- the icon


def icon(size: float, with_band: bool, rounded: bool = True) -> str:
    """Sea square, م in Pearl slightly above centre, a Sadu strip along the bottom."""
    r = size * 0.22 if rounded else 0
    meem = shape("reem", "م", 100, 700)
    target_w = size * (0.58 if with_band else 0.72)
    meem = shape("reem", "م", 100 * target_w / meem.width, 700)
    tiles = 8
    tile_w = size / tiles
    band_h = tile_w * TILE_H / TILE_W
    space_h = size - band_h if with_band else size
    x = (size - meem.width) / 2
    y = (space_h - meem.height) / 2 - (size * 0.03 if with_band else size * 0.02)
    square = f'width="{num(size)}" height="{num(size)}"'
    clip = f'<clipPath id="c"><rect {square} rx="{num(r)}"/></clipPath>'
    strip = band(0, size - band_h, tiles, tile_w, SAND, GOLD) if with_band else ""
    body = (
        f'<defs>{clip}</defs><g clip-path="url(#c)">'
        f'<rect width="{num(size)}" height="{num(size)}" fill="{SEA}"/>{strip}</g>'
        + path(meem, x, y, PEARL)
    )
    return svg(size, size, body, "Marjaa")


# ---------------------------------------------------------------- Open Graph


def og_image() -> str:
    w, h = 1200, 630
    tiles = 30
    tile_w = w / tiles
    band_h = tile_w * TILE_H / TILE_W
    lw, lh, logo, _ = stacked(400, DATE, SEA, GOLD, 0)
    line = shape("plex", "Cited answers on UAE Labour Law", 42, 500)
    block = lh + 64 + line.height
    top = (h - band_h - block) / 2
    body = (
        f'<rect width="{w}" height="{h}" fill="{SAND}"/>'
        f'<g transform="translate({num((w - lw) / 2)} {num(top)})">{logo}</g>'
        + path(line, (w - line.width) / 2, top + lh + 64, DATE)
        + band(0, h - band_h, tiles, tile_w, SEA, GOLD)
    )
    return svg(w, h, body, "Marjaa: cited answers on UAE Labour Law")


# ---------------------------------------------------------------- output


def png(svg_text: str, width: int, height: int | None = None) -> bytes:
    return bytes(resvg_py.svg_to_bytes(svg_string=svg_text, width=width, height=height or width))


def glyphs_module() -> str:
    """The logo for the web app: the same geometry as the files, coloured by theme tokens."""
    ink, sea, gold = "fill-brand-ink", "fill-brand-sea", "fill-brand-gold"
    hw, hh, header = header_lockup(40, ink, sea, animated=True)
    pw, ph, primary, _ = stacked(360, ink, sea, gold, 0, animated=True)
    data = {
        "header": {"width": round(hw, 2), "height": round(hh, 2), "markup": header},
        "primary": {"width": round(pw, 2), "height": round(ph, 2), "markup": primary},
    }
    return (
        "// Generated by scripts/build_brand.py from Reem Kufi 700 and IBM Plex Sans 600.\n"
        "// Do not edit by hand: change the script and run `uv run scripts/build_brand.py`.\n\n"
        f"export const LOGOS = {json.dumps(data, ensure_ascii=False, indent=2)} as const;\n\n"
        f"/** The Sadu tile: {TILE_W} x {TILE_H} units. */\n"
        f"export const TILE = {{ w: {TILE_W}, h: {TILE_H} }} as const;\n"
        f'export const BIG_TRIANGLE = "{poly(BIG, 0, 0, 1)}";\n'
        f'export const SMALL_TRIANGLE = "{poly(SMALL, 0, 0, 1)}";\n'
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    written = []

    def write(name: str, data: str | bytes, where: Path = OUT) -> None:
        target = where / name
        if isinstance(data, str):
            target.write_text(data, encoding="utf-8")
        else:
            target.write_bytes(data)
        written.append(target.relative_to(ROOT))

    w, h, body, _ = stacked(360, DATE, SEA, GOLD, 8)
    write("logo-primary.svg", svg(w, h, body, "Marjaa"))

    pad = 56
    w, h, body, _ = stacked(360, PEARL, SAND, GOLD, pad)
    write(
        "logo-reversed.svg",
        svg(w, h, f'<rect width="{num(w)}" height="{num(h)}" fill="{SEA}"/>' + body, "Marjaa"),
    )

    w, h, body = header_lockup(40, DATE, SEA)
    write("logo-header.svg", svg(w, h, body, "Marjaa"))

    full = icon(512, with_band=True)
    small = icon(512, with_band=False)
    write("icon.svg", full)
    write("favicon.svg", small)
    write("favicon-16.png", png(small, 16))
    write("favicon-32.png", png(small, 32))
    write("icon-192.png", png(full, 192))
    write("icon-512.png", png(full, 512))
    # iOS rounds the corners itself, so the touch icon is a full square.
    write("apple-touch-icon.png", png(icon(512, with_band=True, rounded=False), 180))

    og = og_image()
    write("og.svg", og)
    write("og.png", png(og, 1200, 630))

    # favicon.ico: each size drawn on its own, not scaled down from one image.
    frames = [Image.open(io.BytesIO(png(small, s))).convert("RGBA") for s in (48, 32, 16)]
    buf = io.BytesIO()
    frames[0].save(
        buf, format="ICO", sizes=[(48, 48), (32, 32), (16, 16)], append_images=frames[1:]
    )
    write("favicon.ico", buf.getvalue(), FAVICON_ICO.parent)

    GLYPHS_TS.parent.mkdir(parents=True, exist_ok=True)
    write(GLYPHS_TS.name, glyphs_module(), GLYPHS_TS.parent)

    for p in written:
        print("wrote", p)


if __name__ == "__main__":
    main()
