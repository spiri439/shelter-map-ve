#!/usr/bin/env python3
"""Generate the images for the WordPress.org listing.

`pin-shelter.png` is NOT generated here — the bunker illustration is the plugin
author's own artwork and is committed as it is. This script reuses that file, so
the map marker, the directory icon and the banner all carry the same bunker.

Outputs:

  .wordpress-org/icon-128x128.png        plugin directory icon
  .wordpress-org/icon-256x256.png
  .wordpress-org/banner-772x250.png      plugin page header
  .wordpress-org/banner-1544x500.png

The banner is not decoration: the county outlines and all 4538 dots on it are
the plugin's own data, projected here.

Rasterising goes through headless Chromium, the only renderer present. Chromium
is packaged as a snap, whose confinement cannot read /tmp or /mnt — so it works
inside WORK (under $HOME) and the results are copied back.
"""

import base64
import json
import math
import os
import shutil
import subprocess
import sys

from PIL import Image, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORK = os.path.join(os.path.expanduser('~'), '.cache', 'smve-images')
ORG = os.path.join(ROOT, '.wordpress-org')

CHROMIUM = '/snap/bin/chromium'
BOUNDARIES = os.path.join(ROOT, 'build', 'boundaries', 'ro-counties.geojson')
SHELTERS = os.path.join(ROOT, 'data', 'shelters.json')
PIN = os.path.join(ROOT, 'pin-shelter.png')

FONT = "'Ubuntu Sans','Ubuntu','DejaVu Sans',sans-serif"

DEEP = '#123468'
MID = '#1f51a1'
LIGHT = '#3572d6'


# ---------------------------------------------------------------- rasterising

def write(name, text):
    path = os.path.join(WORK, name)
    with open(path, 'w', encoding='utf-8') as fh:
        fh.write(text)
    return path


def shot(svg_name, out_name, width, height):
    """Render an SVG in WORK at the given pixel size; returns the PNG path."""
    page = write(svg_name + '.html',
                 '<!doctype html><meta charset="utf-8">'
                 '<style>html,body{margin:0;background:transparent}'
                 'img{display:block;width:%dpx;height:%dpx}</style>'
                 '<img src="%s">' % (width, height, svg_name))
    out = os.path.join(WORK, out_name)
    subprocess.run([
        CHROMIUM, '--headless', '--no-sandbox', '--disable-gpu',
        '--disable-dev-shm-usage', '--hide-scrollbars',
        '--default-background-color=00000000',
        '--force-device-scale-factor=1',
        '--screenshot=' + out,
        '--window-size=%d,%d' % (width, height),
        'file://' + page,
    ], capture_output=True, timeout=180)
    if not os.path.exists(out):
        raise SystemExit('Chromium produced nothing for %s' % svg_name)
    return out


def bunker(cx, cy, width):
    """The author's 48x48 bunker, embedded so the SVG needs no extra request.

    Beyond about 2x it goes soft, so the callers keep within that.
    """
    with open(PIN, 'rb') as fh:
        data = base64.b64encode(fh.read()).decode('ascii')
    return ('<image x="%.2f" y="%.2f" width="%.2f" height="%.2f" '
            'href="data:image/png;base64,%s"/>'
            % (cx - width / 2, cy - width / 2, width, width, data))


# ---------------------------------------------------------------- icon

def build_icon():
    svg = '''<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256" viewBox="0 0 128 128">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="{light}"/><stop offset="0.55" stop-color="{mid}"/>
      <stop offset="1" stop-color="{deep}"/>
    </linearGradient>
    <filter id="sh" x="-30%" y="-30%" width="160%" height="160%">
      <feDropShadow dx="0" dy="2" stdDeviation="2.2" flood-color="#08172e" flood-opacity="0.4"/>
    </filter>
  </defs>
  <rect width="128" height="128" fill="url(#bg)"/>
  <g stroke="#ffffff" stroke-opacity="0.10" stroke-width="1.4" fill="none">
    <path d="M0 34 H128 M0 64 H128 M0 94 H128 M34 0 V128 M64 0 V128 M94 0 V128"/>
    <circle cx="64" cy="64" r="46"/>
  </g>
  <g filter="url(#sh)">{bunker}</g>
</svg>'''.format(light=LIGHT, mid=MID, deep=DEEP,
                 bunker=bunker(cx=64, cy=65, width=86))
    write('icon.svg', svg)
    raw = shot('icon.svg', 'icon.png', 256, 256)
    # The bunker is a 48px raster, so filling 256 leaves it soft; a light
    # unsharp pass buys back the edges of the dome and the antenna.
    source = Image.open(raw).convert('RGBA').filter(
        ImageFilter.UnsharpMask(radius=2.0, percent=95, threshold=2))
    for size in (256, 128):
        source.resize((size, size), Image.LANCZOS).save(
            os.path.join(ORG, 'icon-%dx%d.png' % (size, size)), optimize=True)
    print('icon-256x256.png, icon-128x128.png')


# ---------------------------------------------------------------- banner

def simplify(ring, tol):
    """Drop points sitting within `tol` degrees of the last one kept."""
    out = [ring[0]]
    for point in ring[1:]:
        if abs(point[0] - out[-1][0]) > tol or abs(point[1] - out[-1][1]) > tol:
            out.append(point)
    return out if len(out) >= 4 else None


def load_geometry():
    if not os.path.exists(BOUNDARIES):
        raise SystemExit('Missing %s — run build/fetch-boundaries.sh first.' % BOUNDARIES)
    with open(BOUNDARIES, encoding='utf-8') as fh:
        geojson = json.load(fh)
    rings = []
    for feature in geojson['features']:
        geometry = feature['geometry']
        polygons = ([geometry['coordinates']] if geometry['type'] == 'Polygon'
                    else geometry['coordinates'])
        for polygon in polygons:
            for ring in polygon:
                reduced = simplify(ring, 0.008)
                if reduced:
                    rings.append(reduced)
    with open(SHELTERS, encoding='utf-8') as fh:
        shelters = json.load(fh)['a']
    return rings, [(row[1], row[2]) for row in shelters]


def build_banner(width, height, rings, points):
    """Map on the right, wordmark on the left, both on one dark field."""
    scale = width / 772.0

    lngs = [p[0] for ring in rings for p in ring]
    lats = [p[1] for ring in rings for p in ring]
    west, east = min(lngs), max(lngs)
    south, north = min(lats), max(lats)
    squash = math.cos(math.radians((south + north) / 2))

    pad = 14 * scale
    map_w = width * 0.485
    box_w, box_h = map_w - pad, height - 2 * pad
    span_x, span_y = (east - west) * squash, north - south
    k = min(box_w / span_x, box_h / span_y)
    off_x = width - map_w + (box_w - span_x * k) / 2
    off_y = pad + (box_h - span_y * k) / 2

    def project(lng, lat):
        return off_x + (lng - west) * squash * k, off_y + (north - lat) * k

    counties = ' '.join(
        'M' + 'L'.join('%.1f %.1f' % project(p[0], p[1]) for p in ring) + 'Z'
        for ring in rings)

    # `r` is not an inheritable attribute, so every circle carries its own.
    r = max(0.9, 1.25 * scale)
    dots = ''.join('<circle cx="%.1f" cy="%.1f" r="%.2f"/>' % (project(lng, lat) + (r,))
                   for lat, lng in points)

    left = 34 * scale
    return '''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">
  <defs>
    <linearGradient id="field" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#173f80"/><stop offset="0.6" stop-color="{deep}"/>
      <stop offset="1" stop-color="#0c2148"/>
    </linearGradient>
    <radialGradient id="glow" cx="0.74" cy="0.5" r="0.55">
      <stop offset="0" stop-color="{light}" stop-opacity="0.34"/>
      <stop offset="1" stop-color="{light}" stop-opacity="0"/>
    </radialGradient>
  </defs>

  <rect width="{w}" height="{h}" fill="url(#field)"/>
  <rect width="{w}" height="{h}" fill="url(#glow)"/>

  <!-- county outlines, from geoBoundaries ADM1 -->
  <g fill="#ffffff" fill-opacity="0.055" stroke="{light}" stroke-opacity="0.5"
     stroke-width="{stroke:.2f}" stroke-linejoin="round"><path d="{counties}"/></g>

  <!-- one dot per shelter: all 4538 of them -->
  <g fill="#ffd36b" fill-opacity="0.85">{dots}</g>

  {bunker}
  <text x="{tx:.0f}" y="{ey:.0f}" fill="{light}" font-family="{font}" font-size="{eyebrow:.1f}"
        font-weight="600" letter-spacing="{track:.2f}">VLAD ENTERPRISES</text>
  <text x="{lx:.0f}" y="{ty:.0f}" fill="#ffffff" font-family="{font}" font-size="{title:.1f}"
        font-weight="700">Shelter Map</text>
  <text x="{lx:.0f}" y="{sy:.0f}" fill="#cfe0f7" font-family="{font}" font-size="{sub:.1f}"
        >4,538 civil protection shelters in Romania</text>
  <text x="{lx:.0f}" y="{sy2:.0f}" fill="#8fb3e6" font-family="{font}" font-size="{sub:.1f}"
        >Leaflet + OpenStreetMap &#183; no API key</text>
</svg>'''.format(
        w=width, h=height, deep=DEEP, light=LIGHT, font=FONT,
        stroke=max(0.5, 0.7 * scale), counties=counties, dots=dots,
        bunker=bunker(cx=left + 17 * scale, cy=height * 0.225, width=40 * scale),
        lx=left, tx=left + 42 * scale, ey=height * 0.272,
        ty=height * 0.53, sy=height * 0.70, sy2=height * 0.845,
        title=42 * scale, sub=13.2 * scale, eyebrow=11.4 * scale, track=1.6 * scale,
    )


def build_banners(rings, points):
    for width, height in ((772, 250), (1544, 500)):
        name = 'banner-%dx%d' % (width, height)
        write(name + '.svg', build_banner(width, height, rings, points))
        raw = shot(name + '.svg', name + '.png', width, height)
        Image.open(raw).convert('RGB').save(
            os.path.join(ORG, name + '.png'), optimize=True)
        print('%s.png' % name)


def main():
    if not os.path.exists(CHROMIUM):
        raise SystemExit('Chromium not found at %s; it is the only rasteriser here.' % CHROMIUM)
    if not os.path.exists(PIN):
        raise SystemExit('Missing %s' % PIN)
    shutil.rmtree(WORK, ignore_errors=True)
    os.makedirs(WORK, exist_ok=True)
    os.makedirs(ORG, exist_ok=True)

    build_icon()
    rings, points = load_geometry()
    print('geometry: %d rings, %d shelters' % (len(rings), len(points)))
    build_banners(rings, points)

    shutil.rmtree(WORK, ignore_errors=True)


if __name__ == '__main__':
    sys.exit(main())
