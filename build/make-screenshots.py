#!/usr/bin/env python3
"""Capture the WordPress.org screenshots from the plugin actually running.

Everything is served from a throwaway local HTTP server: the plugin's own
stylesheet, script and data, plus the markup its shortcode really produces
(rendered through tests/wp-harness.php). Only the map tiles come from
OpenStreetMap, exactly as they would for a visitor.

Serving over http rather than opening a file:// page matters — the script
fetches its data with fetch(), which a file:// origin is not allowed to do.

Chromium is a snap and its confinement cannot read /tmp or /mnt, so the web root
is built under $HOME and the results are copied back.
"""

import functools
import gettext
import http.server
import json
import os
import shutil
import socketserver
import subprocess
import threading

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORK = os.path.join(os.path.expanduser('~'), '.cache', 'smve-shots')
ORG = os.path.join(ROOT, '.wordpress-org')
CHROMIUM = '/snap/bin/chromium'

# name, county slug, viewport, height to keep
SHOTS = (
    ('screenshot-1', '', (1200, 1000), 900),
    ('screenshot-2', 'cluj', (1200, 1240), 1140),
    ('screenshot-3', '', (430, 940), 880),
)

PAGE = '''<!doctype html>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="stylesheet" href="/plugin/shelter-map.css">
<style>
  html {{ background: #fff; }}
  body {{
    margin: 0; padding: {pad}px;
    font: 16px/1.55 "Ubuntu Sans", Ubuntu, "DejaVu Sans", sans-serif;
    color: #23282d; background: #fff;
  }}
  .wrap {{ max-width: 1120px; margin: 0 auto; }}
</style>
<div class="wrap">{markup}</div>
<script>window.SMVEConfig = {config};</script>
<script src="/plugin/shelter-map.js"></script>
'''


def translations():
    path = os.path.join(ROOT, 'languages', 'shelter-map-ve-ro_RO.mo')
    with open(path, 'rb') as fh:
        return gettext.GNUTranslations(fh)


def build_config():
    _ = translations().gettext
    base = '/plugin'
    return json.dumps({
        'shelters': base + '/data/shelters.json',
        'leafletJs': base + '/vendor/leaflet.js',
        'leafletCss': base + '/vendor/leaflet.css',
        'clusterJs': base + '/vendor/leaflet.markercluster.js',
        'clusterCss': [base + '/vendor/MarkerCluster.css',
                       base + '/vendor/MarkerCluster.Default.css'],
        'pin': base + '/pin-shelter.png',
        'locale': 'ro-RO',
        'text': {
            'loadError': _('The map could not be loaded. Please reload the page.'),
            'navigate': _('Directions'),
            'sector': _('Sector %s'),
            'awayFromYou': _('%s away from you'),
            'nearest': _('Nearest shelter to you'),
            'yourPosition': _('Your position'),
            'locating': _('Finding your position…'),
            'noPosition': _('Could not determine your position. '
                            'Check that location access is allowed.'),
            'noResults': _('No shelter matches your search.'),
            'oneResult': _('1 shelter'),
            'nResults': _('%s shelters'),
            'allCounties': _('All counties'),
            'allSectors': _('All sectors'),
        },
    }, ensure_ascii=False)


def render_markup(county):
    result = subprocess.run(
        ['php', os.path.join(ROOT, 'build', 'render-markup.php'), county],
        capture_output=True, text=True, timeout=120)
    if result.returncode or '<div class="smve-map"' not in result.stdout:
        raise SystemExit('render-markup.php failed:\n%s' % (result.stderr or result.stdout)[:600])
    return result.stdout


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


class ReusableServer(socketserver.TCPServer):
    # Set on the class: TCPServer binds inside __init__, so setting the flag on
    # the instance afterwards is too late and a re-run hits "address in use".
    allow_reuse_address = True


def serve(directory):
    """Start a throwaway server on whatever port the OS hands out."""
    handler = functools.partial(QuietHandler, directory=directory)
    httpd = ReusableServer(('127.0.0.1', 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, httpd.server_address[1]


def main():
    if not os.path.exists(CHROMIUM):
        raise SystemExit('Chromium not found at %s' % CHROMIUM)

    shutil.rmtree(WORK, ignore_errors=True)
    os.makedirs(WORK, exist_ok=True)
    os.makedirs(ORG, exist_ok=True)

    # The web root holds a copy of the plugin exactly as it ships.
    plugin_root = os.path.join(WORK, 'plugin')
    for name in ('shelter-map.css', 'shelter-map.js', 'pin-shelter.png'):
        os.makedirs(plugin_root, exist_ok=True)
        shutil.copy(os.path.join(ROOT, name), plugin_root)
    for name in ('vendor', 'data'):
        shutil.copytree(os.path.join(ROOT, name), os.path.join(plugin_root, name))

    config = build_config()
    for name, county, (width, height), crop in SHOTS:
        page = PAGE.format(pad=14 if width < 700 else 26,
                           markup=render_markup(county), config=config)
        with open(os.path.join(WORK, name + '.html'), 'w', encoding='utf-8') as fh:
            fh.write(page)

    httpd, port = serve(WORK)
    try:
        for name, _county, (width, height), crop in SHOTS:
            raw = os.path.join(WORK, name + '-raw.png')
            subprocess.run([
                CHROMIUM, '--headless', '--no-sandbox', '--disable-gpu',
                '--disable-dev-shm-usage', '--hide-scrollbars',
                '--force-device-scale-factor=1',
                '--virtual-time-budget=40000',
                '--screenshot=' + raw,
                '--window-size=%d,%d' % (width, height),
                'http://127.0.0.1:%d/%s.html' % (port, name),
            ], capture_output=True, timeout=300)
            if not os.path.exists(raw):
                raise SystemExit('Chromium produced nothing for %s' % name)
            image = Image.open(raw).convert('RGB')
            if crop and crop < image.height:
                image = image.crop((0, 0, image.width, crop))
            # Map tiles are photographic and push a true-colour PNG past a
            # megabyte; an adaptive palette holds up fine at this size.
            image = image.quantize(colors=256, method=Image.FASTOCTREE, dither=Image.FLOYDSTEINBERG)
            out = os.path.join(ORG, name + '.png')
            image.save(out, optimize=True)
            print('%s.png  %dx%d  %.0f KB' % (
                name, image.width, image.height, os.path.getsize(out) / 1024))
    finally:
        httpd.shutdown()
        httpd.server_close()

    shutil.rmtree(WORK, ignore_errors=True)


if __name__ == '__main__':
    main()
