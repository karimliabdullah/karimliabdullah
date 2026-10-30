#!/usr/bin/env python3
"""Builds the premium hero (light + dark) with real typography and a duotone portrait.

Text is shaped with HarfBuzz and written as vector paths, so it renders the same
in every browser without web fonts. Fonts are downloaded once into scripts/.fonts.

Requires: pip install pillow fonttools uharfbuzz
"""
from __future__ import annotations

import base64
import io
import json
import urllib.request
from pathlib import Path

import uharfbuzz as hb
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from PIL import Image, ImageEnhance, ImageOps

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
FONTS = Path(__file__).resolve().parent / ".fonts"
GF = "https://raw.githubusercontent.com/google/fonts/main/ofl"
FONT_URLS = {
    "Archivo.ttf": f"{GF}/archivo/Archivo%5Bwdth,wght%5D.ttf",
    "PlexMono.ttf": f"{GF}/ibmplexmono/IBMPlexMono-Medium.ttf",
}
EASE = "cubic-bezier(0.16, 1, 0.3, 1)"
W, H = 900, 480

THEMES = {
    "light": dict(bg="#EDEDE7", ink="#0B0C0E", soft="#55585E", rule="#0B0C0E", rule_o=0.14,
                  accent="#1E3AE6", shadow=(13, 16, 34), mid=(96, 104, 148), light=(237, 237, 231)),
    "dark": dict(bg="#0A0B0D", ink="#ECECE6", soft="#9A9DA4", rule="#ECECE6", rule_o=0.14,
                 accent="#7D8FFF", shadow=(10, 11, 13), mid=(82, 88, 124), light=(222, 224, 230)),
}


class Face:
    def __init__(self, path: Path, **axes: float):
        blob = hb.Blob(path.read_bytes())
        self.font = hb.Font(hb.Face(blob))
        if axes:
            self.font.set_variations(axes)
        self.upem = self.font.face.upem

    def shape(self, text: str, size: float, tracking: float = 0.0):
        buf = hb.Buffer()
        buf.add_str(text)
        buf.guess_segment_properties()
        hb.shape(self.font, buf, {"kern": True, "liga": True})
        s = size / self.upem
        x, glyphs = 0.0, []
        for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
            glyphs.append((info.codepoint, x + pos.x_offset * s, pos.y_offset * s))
            x += pos.x_advance * s + tracking
        return glyphs, x - tracking

    def path(self, text: str, size: float, x: float, y: float, tracking: float = 0.0, anchor: str = "start") -> str:
        glyphs, width = self.shape(text, size, tracking)
        if anchor == "end":
            x -= width
        s = size / self.upem
        pen = SVGPathPen(None, ntos=lambda v: f"{v:.1f}".rstrip("0").rstrip("."))
        for gid, gx, gy in glyphs:
            self.font.draw_glyph_with_pen(gid, TransformPen(pen, (s, 0, 0, -s, x + gx, y - gy)))
        return pen.getCommands()


def ensure_fonts() -> None:
    FONTS.mkdir(exist_ok=True)
    for name, url in FONT_URLS.items():
        if not (FONTS / name).exists():
            urllib.request.urlretrieve(url, FONTS / name)


def portrait(theme: dict, box: tuple[int, int]) -> str:
    """Duotone crop of assets/photo.jpg as a base64 JPEG at 2x the display size."""
    cfg = json.loads((ASSETS / "photo.json").read_text()).get("portrait", [0.395, 0.22, 0.41])
    img = ImageOps.exif_transpose(Image.open(ASSETS / "photo.jpg")).convert("L")
    fl, ft, fw = cfg
    cw = int(fw * img.width)
    ch = int(cw * box[1] / box[0])
    left, top = int(fl * img.width), int(ft * img.height)
    img = img.crop((left, top, left + cw, top + ch)).resize((box[0] * 2, box[1] * 2), Image.LANCZOS)
    img = ImageOps.autocontrast(img, cutoff=1)
    img = ImageEnhance.Contrast(img).enhance(1.15)
    img = ImageOps.colorize(img, black=theme["shadow"], white=theme["light"], mid=theme["mid"])
    out = io.BytesIO()
    img.save(out, "JPEG", quality=82, optimize=True, progressive=True)
    return base64.b64encode(out.getvalue()).decode()


def hero(mode: str) -> str:
    t = THEMES[mode]
    display = Face(FONTS / "Archivo.ttf", wght=760, wdth=62)
    body = Face(FONTS / "Archivo.ttf", wght=400, wdth=100)
    label = Face(FONTS / "Archivo.ttf", wght=600, wdth=100)
    mono = Face(FONTS / "PlexMono.ttf")

    M = 40
    px, py, pw, ph = 612, 84, 248, 300
    photo = portrait(t, (pw, ph))
    caps = lambda text, x, y, anchor="start", size=10.5: mono.path(text, size, x, y, 1.1, anchor)

    name1 = display.path("Abdullah", 160, M - 5, 204, -2)
    name2 = display.path("Karimli", 160, M - 5, 344, -2)
    lead1 = body.path("Apps, websites and games, designed,", 17, M, 390, 0)
    lead2 = body.path("built and shipped by one person.", 17, M, 413, 0)

    avail_w = mono.shape("AVAILABLE FOR NEW WORK", 10.5, 1.1)[1]
    disciplines = [("01", "Web", 0), ("02", "Mobile", 112), ("03", "Games", 236), ("04", "AI tools", 356)]
    disc = "".join(
        f'<path d="{caps(n, M + dx, 458)}" fill="{t["accent"]}"/>'
        f'<path d="{label.path(word, 13, M + dx + 26, 458.5, 0.1)}" fill="{t["ink"]}"/>'
        for n, word, dx in disciplines
    )

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-labelledby="t d">
  <title id="t">Abdullah Karimli — product developer, Baku</title>
  <desc id="d">Editorial header: the name Abdullah Karimli in large condensed type, a duotone portrait, and the disciplines web, mobile, games and AI tools. Available for new work.</desc>
  <style>
    .up {{ animation: up 300ms {EASE} both; }}
    .fade {{ animation: fade 300ms {EASE} both; }}
    .settle {{ animation: settle 300ms {EASE} both; transform-origin: {px + pw / 2}px {py + ph / 2}px; }}
    @keyframes up {{ from {{ transform: translateY(28px); }} to {{ transform: none; }} }}
    @keyframes fade {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}
    @keyframes settle {{ from {{ opacity: 0; transform: scale(1.04); }} to {{ opacity: 1; transform: none; }} }}
    .dot {{ animation: pulse 2.4s {EASE} infinite; }}
    @keyframes pulse {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: .3; }} }}
    @media (prefers-reduced-motion: reduce) {{ .up, .fade, .settle, .dot {{ animation: none; }} }}
  </style>
  <defs>
    <clipPath id="l1"><rect x="0" y="70" width="600" height="140"/></clipPath>
    <clipPath id="l2"><rect x="0" y="210" width="600" height="140"/></clipPath>
    <clipPath id="frame"><rect x="{px}" y="{py}" width="{pw}" height="{ph}"/></clipPath>
  </defs>

  <rect width="{W}" height="{H}" fill="{t["bg"]}"/>

  <g class="fade">
    <path d="{caps("AK / PROFILE", M, 44)}" fill="{t["ink"]}"/>
    <path d="{caps("PRODUCT DEVELOPER", 330, 44)}" fill="{t["ink"]}"/>
    <path d="{caps("40.4093° N   49.8671° E", W - M, 44, "end")}" fill="{t["soft"]}"/>
    <rect x="{M}" y="58" width="{W - 2 * M}" height="1" fill="{t["rule"]}" fill-opacity="{t["rule_o"]}"/>
  </g>

  <g clip-path="url(#l1)"><path class="up" style="animation-delay:60ms" d="{name1}" fill="{t["ink"]}"/></g>
  <g clip-path="url(#l2)"><path class="up" style="animation-delay:140ms" d="{name2}" fill="{t["ink"]}"/></g>

  <g class="fade" style="animation-delay:220ms">
    <path d="{lead1}" fill="{t["soft"]}"/>
    <path d="{lead2}" fill="{t["soft"]}"/>
  </g>

  <g clip-path="url(#frame)">
    <image class="settle" style="animation-delay:120ms" x="{px}" y="{py}" width="{pw}" height="{ph}" preserveAspectRatio="xMidYMid slice" href="data:image/jpeg;base64,{photo}"/>
  </g>
  <rect x="{px + .5}" y="{py + .5}" width="{pw - 1}" height="{ph - 1}" fill="none" stroke="{t["rule"]}" stroke-opacity="{t["rule_o"]}"/>
  <g class="fade" style="animation-delay:260ms">
    <path d="{caps("FIG. 01", px, py + ph + 20)}" fill="{t["ink"]}"/>
    <path d="{caps("BAKU, AZERBAIJAN", px + pw, py + ph + 20, "end")}" fill="{t["soft"]}"/>
  </g>

  <g class="fade" style="animation-delay:300ms">
    <rect x="{M}" y="432" width="{W - 2 * M}" height="1" fill="{t["rule"]}" fill-opacity="{t["rule_o"]}"/>
    {disc}
    <circle class="dot" cx="{W - M - avail_w - 14}" cy="454.5" r="3.5" fill="{t["accent"]}"/>
    <path d="{caps("AVAILABLE FOR NEW WORK", W - M, 458, "end")}" fill="{t["ink"]}"/>
  </g>
</svg>
'''


def main() -> None:
    ensure_fonts()
    for mode in THEMES:
        (ASSETS / f"premium-hero-{mode}.svg").write_text(hero(mode))
    print("built premium heroes")


if __name__ == "__main__":
    main()
