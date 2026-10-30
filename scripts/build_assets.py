#!/usr/bin/env python3
"""Builds the ASCII portrait and the terminal + flashy hero SVGs.

The premium hero is built by scripts/build_premium.py.

Usage:
    python3 scripts/build_assets.py                 # uses assets/photo.(jpg|png) if present
    python3 scripts/build_assets.py path/to/me.jpg  # uses an explicit photo

With no photo it renders an "AK" monogram, so every README works before a
portrait exists. Re-run after adding a photo and commit the regenerated files.
"""
from __future__ import annotations

import json
import sys
from html import escape
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"

# Dark to light ink density; reversed for dark backgrounds.
RAMP = "@%#*+=-:. "
EASE = "cubic-bezier(0.16, 1, 0.3, 1)"
MONO = "ui-monospace, SFMono-Regular, Menlo, Consolas, 'Liberation Mono', monospace"
SANS = "-apple-system, 'Segoe UI', 'Helvetica Neue', Helvetica, Arial, sans-serif"


def find_photo(argv: list[str]) -> Path | None:
    if len(argv) > 1:
        return Path(argv[1])
    for name in ("photo.jpg", "photo.jpeg", "photo.png", "photo.webp"):
        if (ASSETS / name).exists():
            return ASSETS / name
    return None


def photo_config() -> dict:
    """assets/photo.json: {"crop": [left, top, side] as fractions of width/height/width,
    "invert": bool}. invert=false suits backlit photos (dark hair, bright sky)."""
    path = ASSETS / "photo.json"
    return json.loads(path.read_text()) if path.exists() else {}


def monogram() -> Image.Image:
    img = Image.new("L", (600, 600), 255)
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("DejaVuSerif-Bold.ttf", 300)
    except OSError:
        font = ImageFont.load_default(size=300)
    draw.ellipse((40, 40, 560, 560), outline=0, width=26)
    box = draw.textbbox((0, 0), "AK", font=font)
    w, h = box[2] - box[0], box[3] - box[1]
    draw.text(((600 - w) / 2 - box[0], (600 - h) / 2 - box[1]), "AK", font=font, fill=0)
    return img


def load_source(photo: Path | None, cfg: dict) -> tuple[Image.Image, Image.Image | None]:
    """Returns the prepared portrait and a subject mask (255 = keep, 0 = background)."""
    if photo is None:
        return monogram(), None
    img = ImageOps.exif_transpose(Image.open(photo)).convert("L")
    if "crop" in cfg:
        fl, ft, fs = cfg["crop"]
        left, top, side = int(fl * img.width), int(ft * img.height), int(fs * img.width)
    else:
        # Square crop biased upward so the face, not the chest, fills the frame.
        side = min(img.size)
        left = (img.width - side) // 2
        top = max(0, min((img.height - side) // 4, img.height - side))
    img = img.crop((left, top, left + side, top + side))

    # A bright sky or wall reads as background: drop it before equalizing,
    # otherwise it turns into noise around the head.
    cut = cfg.get("background_above", 205)
    mask = img.point(lambda v: 0 if v > cut else 255).filter(ImageFilter.MedianFilter(9))
    mask = mask.filter(ImageFilter.GaussianBlur(side / 120))

    # Equalizing pulls features out of backlit, shadowed faces.
    img = ImageOps.equalize(img, mask=mask) if cfg.get("equalize", True) else ImageOps.autocontrast(img, cutoff=2)
    img = ImageEnhance.Contrast(img).enhance(1.2)
    return img.filter(ImageFilter.UnsharpMask(radius=2, percent=160, threshold=2)), mask


def to_ascii(img: Image.Image, cols: int, rows: int, invert: bool, mask: Image.Image | None = None) -> list[str]:
    """invert=True maps bright pixels to dense glyphs: a positive image in light ink on dark panels."""
    small = img.resize((cols, rows), Image.LANCZOS)
    if mask is not None:
        # Blank the background, then soften the frame edge with a head-shaped
        # ellipse so stray scenery fades out instead of ending in a hard line.
        keep = mask.resize((cols, rows), Image.LANCZOS)
        oval = Image.new("L", (cols, rows), 0)
        ImageDraw.Draw(oval).ellipse((-cols * 0.06, -rows * 0.04, cols * 1.06, rows * 1.2), fill=255)
        oval = oval.filter(ImageFilter.GaussianBlur(min(cols, rows) / 12))
        keep = ImageChops.multiply(keep, oval)
        if invert:
            # Dark hair would vanish in a positive render; a density floor keeps the silhouette.
            small = small.point(lambda v: 80 + v * 175 // 255)
        small = Image.composite(small, Image.new("L", small.size, 0 if invert else 255), keep)
    ramp = RAMP[::-1] if invert else RAMP
    px = small.load()
    out = []
    for y in range(rows):
        out.append("".join(ramp[px[x, y] * (len(ramp) - 1) // 255] for x in range(cols)).rstrip())
    return out


def ascii_rows_svg(lines, x, y, size, lead, width, fill, delay0=0.0, step=0.035, cls="r"):
    """One <text> per row; textLength pins every row to the same width in any font."""
    parts = []
    for i, line in enumerate(lines):
        if not line.strip():
            continue
        padded = line.ljust(len(max(lines, key=len)))
        parts.append(
            f'<text class="{cls}" x="{x}" y="{y + i * lead:.1f}" font-size="{size}" '
            f'textLength="{width}" lengthAdjust="spacingAndGlyphs" fill="{fill}" '
            f'style="animation-delay:{delay0 + i * step:.3f}s" xml:space="preserve">{escape(padded)}</text>'
        )
    return "\n    ".join(parts)


def reduced_motion(selector: str) -> str:
    return f"@media (prefers-reduced-motion: reduce) {{ {selector} {{ animation: none !important; opacity: 1 !important; transform: none !important; }} }}"


# --------------------------------------------------------------------------- terminal

def terminal_svg(face: list[str]) -> str:
    info = [
        ("abdullah", "@", "baku"),
        None,
        ("Role", "Product developer — idea, design, code, launch"),
        ("Base", "Baku, Azerbaijan 🇦🇿  ·  working worldwide"),
        ("Ships", "Web apps · Mobile apps · Games · AI tools"),
        ("Front", "Next.js · React · TypeScript · Tailwind · Vite"),
        ("Mobile", "Expo · React Native · Skia · Capacitor"),
        ("Back", "Supabase · PostgreSQL · Edge Functions · Docker"),
        ("AI/ML", "Python · Whisper · OpenCV · FFmpeg"),
        ("Games", "Roblox / Luau · 60 fps Skia engines"),
        ("Speaks", "Azerbaijani · English · Russian"),
        ("Status", "● taking on new projects"),
    ]
    rows = []
    y = 116
    for i, item in enumerate(info):
        d = 1.15 + i * 0.07
        if item is None:
            rows.append(f'<text class="l" x="372" y="{y}" fill="#3B4252" style="animation-delay:{d:.2f}s">──────────────────</text>')
        elif len(item) == 3:
            rows.append(
                f'<text class="l" x="372" y="{y}" style="animation-delay:{d:.2f}s">'
                f'<tspan fill="#7EE787" font-weight="700">{item[0]}</tspan><tspan fill="#8B949E">{item[1]}</tspan>'
                f'<tspan fill="#79C0FF" font-weight="700">{item[2]}</tspan></text>'
            )
        else:
            val_fill = "#7EE787" if item[0] == "Status" else "#E6EDF3"
            rows.append(
                f'<text class="l" x="372" y="{y}" style="animation-delay:{d:.2f}s">'
                f'<tspan fill="#F0883E" font-weight="700">{item[0]}</tspan><tspan fill="#8B949E">: </tspan>'
                f'<tspan fill="{val_fill}">{escape(item[1])}</tspan></text>'
            )
        y += 22
    swatches = "".join(
        f'<rect class="l" x="{372 + i * 30}" y="{y - 4}" width="26" height="14" rx="3" fill="{c}" style="animation-delay:{1.15 + len(info) * 0.07:.2f}s"/>'
        for i, c in enumerate(["#F85149", "#F0883E", "#D29922", "#7EE787", "#79C0FF", "#BC8CFF", "#FF7AC6", "#E6EDF3"])
    )
    face_svg = ascii_rows_svg(face, 36, 92, 10.5, 12.4, 300, "#7EE787", delay0=0.55, step=0.028)
    cmd = "neofetch --user abdullah"
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="900" height="440" viewBox="0 0 900 440" role="img" aria-labelledby="t d">
  <title id="t">Abdullah Karimli — terminal profile</title>
  <desc id="d">A terminal window running neofetch: an ASCII portrait of Abdullah next to his role, location, stack and availability.</desc>
  <style>
    text {{ font-family: {MONO}; font-size: 14px; }}
    .r, .l {{ opacity: 0; animation: in 300ms {EASE} forwards; }}
    .l {{ transform: translateX(-6px); }}
    @keyframes in {{ to {{ opacity: 1; transform: none; }} }}
    .type {{ animation: type 900ms steps({len(cmd)}) 150ms both; }}
    @keyframes type {{ from {{ width: 0; }} to {{ width: {len(cmd) * 8.45:.0f}px; }} }}
    .cur {{ animation: blink 1s steps(1) infinite; }}
    @keyframes blink {{ 50% {{ opacity: 0; }} }}
    {reduced_motion(".r, .l, .type")}
  </style>
  <defs>
    <clipPath id="typed"><rect class="type" x="64" y="40" height="26" width="{len(cmd) * 8.45:.0f}"/></clipPath>
    <linearGradient id="glass" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#161B22"/><stop offset="1" stop-color="#0D1117"/></linearGradient>
  </defs>
  <rect x="1" y="1" width="898" height="438" rx="14" fill="url(#glass)" stroke="#30363D"/>
  <rect x="1" y="1" width="898" height="30" rx="14" fill="#1C2128"/>
  <rect x="1" y="17" width="898" height="14" fill="#1C2128"/>
  <line x1="1" y1="31" x2="899" y2="31" stroke="#30363D"/>
  <circle cx="22" cy="16" r="6" fill="#FF5F57"/><circle cx="42" cy="16" r="6" fill="#FEBC2E"/><circle cx="62" cy="16" r="6" fill="#28C840"/>
  <text x="450" y="20" text-anchor="middle" fill="#8B949E" font-size="12">abdullah@baku: ~</text>
  <text x="24" y="58" fill="#7EE787" font-weight="700">➜</text><text x="44" y="58" fill="#79C0FF">~</text>
  <g clip-path="url(#typed)"><text x="64" y="58" fill="#E6EDF3">{cmd}</text></g>
  <rect class="cur" x="{64 + len(cmd) * 8.45 + 4:.0f}" y="46" width="8" height="15" fill="#E6EDF3" opacity=".8"/>
  <g>
    {face_svg}
  </g>
  {"".join(rows)}
  {swatches}
</svg>
'''


# --------------------------------------------------------------------------- flashy

def flashy_svg(face: list[str]) -> str:
    face_svg = ascii_rows_svg(face, 560, 52, 8.6, 9.6, 300, "url(#neon)", delay0=0.2, step=0.018)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="900" height="400" viewBox="0 0 900 400" role="img" aria-labelledby="t d">
  <title id="t">ABDULLAH KARIMLI — builds apps, sites and games</title>
  <desc id="d">Neon banner with Abdullah's name, a glowing ASCII portrait and a scanline sweeping across it.</desc>
  <style>
    .r, .f {{ opacity: 0; animation: in 300ms {EASE} forwards; }}
    .f {{ transform: translateY(10px); }}
    @keyframes in {{ to {{ opacity: 1; transform: none; }} }}
    .scan {{ animation: scan 3.2s {EASE} 1.2s infinite; }}
    @keyframes scan {{ 0% {{ transform: translateY(0); opacity: 0; }} 15% {{ opacity: .9; }} 85% {{ opacity: .9; }} 100% {{ transform: translateY(330px); opacity: 0; }} }}
    .glow {{ animation: glow 3s ease-in-out infinite alternate; }}
    @keyframes glow {{ from {{ opacity: .55; }} to {{ opacity: 1; }} }}
    {reduced_motion(".r, .f, .scan, .glow")}
  </style>
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#0B0620"/><stop offset=".55" stop-color="#160A33"/><stop offset="1" stop-color="#05141F"/></linearGradient>
    <linearGradient id="neon" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#22D3EE"/><stop offset=".5" stop-color="#A78BFA"/><stop offset="1" stop-color="#F472B6"/></linearGradient>
    <linearGradient id="beam" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#22D3EE" stop-opacity="0"/><stop offset=".5" stop-color="#22D3EE" stop-opacity=".55"/><stop offset="1" stop-color="#22D3EE" stop-opacity="0"/></linearGradient>
    <radialGradient id="halo" cx=".5" cy=".5" r=".5"><stop offset="0" stop-color="#A78BFA" stop-opacity=".35"/><stop offset="1" stop-color="#A78BFA" stop-opacity="0"/></radialGradient>
    <pattern id="grid" width="28" height="28" patternUnits="userSpaceOnUse"><path d="M28 0H0V28" fill="none" stroke="#FFFFFF" stroke-opacity=".045"/></pattern>
    <filter id="soft" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="6"/></filter>
  </defs>
  <rect width="900" height="400" rx="20" fill="url(#bg)"/>
  <rect width="900" height="400" rx="20" fill="url(#grid)"/>
  <ellipse class="glow" cx="710" cy="200" rx="230" ry="190" fill="url(#halo)"/>
  <text class="f" x="52" y="96" fill="#22D3EE" font-family="{MONO}" font-size="14" letter-spacing="4">// PRODUCT DEVELOPER · BAKU</text>
  <g font-family="{SANS}" font-weight="900" letter-spacing="-2">
    <text class="f glow" x="48" y="172" font-size="76" fill="url(#neon)" filter="url(#soft)" style="animation-delay:80ms">ABDULLAH</text>
    <text class="f" x="48" y="172" font-size="76" fill="url(#neon)" style="animation-delay:80ms">ABDULLAH</text>
    <text class="f" x="48" y="248" font-size="76" fill="#F8FAFC" style="animation-delay:160ms">KARIMLI</text>
  </g>
  <text class="f" x="52" y="292" fill="#CBD5E1" font-family="{SANS}" font-size="17" style="animation-delay:240ms">Apps · Websites · Games · AI tools — idea to launch, solo.</text>
  <g class="f" style="animation-delay:300ms" font-family="{MONO}" font-size="12">
    <rect x="52" y="318" width="132" height="30" rx="15" fill="#22D3EE" fill-opacity=".12" stroke="#22D3EE" stroke-opacity=".6"/>
    <text x="118" y="337" text-anchor="middle" fill="#67E8F9">3,000+ USERS</text>
    <rect x="194" y="318" width="122" height="30" rx="15" fill="#A78BFA" fill-opacity=".12" stroke="#A78BFA" stroke-opacity=".6"/>
    <text x="255" y="337" text-anchor="middle" fill="#C4B5FD">60 FPS GAMES</text>
    <rect x="326" y="318" width="142" height="30" rx="15" fill="#F472B6" fill-opacity=".12" stroke="#F472B6" stroke-opacity=".6"/>
    <text x="397" y="337" text-anchor="middle" fill="#F9A8D4">AZ · EN · RU</text>
  </g>
  <g>
    {face_svg}
  </g>
  <rect class="scan" x="540" y="34" width="340" height="18" fill="url(#beam)"/>
</svg>
'''


def main() -> None:
    photo = find_photo(sys.argv)
    cfg = photo_config() if photo else {}
    src, mask = load_source(photo, cfg)
    ASSETS.mkdir(exist_ok=True)

    # Photos render as a positive image: light ink on dark panels needs bright
    # pixels dense. The monogram is ink on paper and reads right either way.
    on_dark = lambda cols, rows: to_ascii(src, cols, rows, invert=photo is not None, mask=mask)
    on_light = lambda cols, rows: to_ascii(src, cols, rows, invert=False, mask=mask)

    (ASSETS / "face.txt").write_text("\n".join(on_light(64, 32)) + "\n")
    (ASSETS / "terminal-hero.svg").write_text(terminal_svg(on_dark(46, 24)))
    (ASSETS / "flashy-hero.svg").write_text(flashy_svg(on_dark(52, 34)))
    print(f"built assets from {'photo ' + str(photo) if photo else 'AK monogram placeholder'}")


if __name__ == "__main__":
    main()
