#!/usr/bin/env python3
"""Turn source-data/markers-raw.tsv into the plugin's data/ files.

Outputs, all relative to the plugin root:

  data/shelters.json          every shelter, compact, for the map
  data/counties.json          county name + slug + count, for the PHP navigation
  data/counties/<slug>.json   one file per county, for the server-rendered list

Run build/fetch-boundaries.sh first.
"""

import html
import json
import os
import re
import unicodedata

import pip as point_in_polygon

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE = os.path.join(ROOT, 'source-data', 'markers-raw.tsv')
FIXES = os.path.join(ROOT, 'source-data', 'fixed-coordinates.json')
DEST = os.path.join(ROOT, 'data')

SECTOR = re.compile(r'sector\s*([1-6])', re.I)


def clean(title):
    """The registers were pasted from Word: literal <br />, double-escaped
    entities and '÷' used as a range separator all show up."""
    title = re.sub(r'<br\s*/?>', ' ', title, flags=re.I)
    title = html.unescape(html.unescape(title))
    title = re.sub(r'\s*÷\s*', '-', title)
    return re.sub(r'\s+', ' ', title).strip(' ,;')


def slugify(value):
    value = (value.replace('ș', 's').replace('ț', 't').replace('ă', 'a')
                  .replace('â', 'a').replace('î', 'i'))
    value = unicodedata.normalize('NFD', value).encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z0-9]+', '-', value.lower()).strip('-')


def main():
    shelters = []
    with open(SOURCE, encoding='utf-8') as fh:
        for line in fh:
            line = line.rstrip('\n')
            if not line:
                continue
            parts = line.split('\t')
            shelters.append({
                'id': int(parts[0]),
                'lat': float(parts[1]),
                'lng': float(parts[2]),
                'title': clean('\t'.join(parts[3:])),
            })
    shelters.sort(key=lambda s: s['id'])
    print('shelters read: %d' % len(shelters))

    # Coordinates re-geocoded and verified against street + sector + number.
    with open(FIXES, encoding='utf-8') as fh:
        fixes = json.load(fh)
    fixed = 0
    for shelter in shelters:
        fix = fixes.get(str(shelter['id']))
        if fix:
            shelter['lat'], shelter['lng'] = fix['lat'], fix['lng']
            shelter['fixed'] = fix['precision']
            fixed += 1
    print('coordinates corrected: %d' % fixed)

    assigned = point_in_polygon.counties_for(
        (s['lat'], s['lng']) for s in shelters)
    for shelter, county in zip(shelters, assigned):
        shelter['county'] = county
    unplaced = [s for s in shelters if not s['county']]
    if unplaced:
        raise SystemExit('%d shelters fell outside every county' % len(unplaced))

    # Sectors only mean anything for Bucharest.
    for shelter in shelters:
        match = SECTOR.search(shelter['title'])
        shelter['sector'] = int(match.group(1)) if (
            match and shelter['county'] == 'București') else 0

    counties = sorted({s['county'] for s in shelters}, key=slugify)
    index = {name: i for i, name in enumerate(counties)}
    shelters.sort(key=lambda s: (slugify(s['county']), s['sector'], slugify(s['title'])))

    os.makedirs(os.path.join(DEST, 'counties'), exist_ok=True)

    def write(path, payload):
        with open(os.path.join(DEST, path), 'w', encoding='utf-8') as fh:
            json.dump(payload, fh, ensure_ascii=False, separators=(',', ':'))

    # [countyIndex, lat, lng, name, sector]
    write('shelters.json', {
        'v': 1,
        'counties': counties,
        'a': [[index[s['county']], round(s['lat'], 5), round(s['lng'], 5),
               s['title'], s['sector']] for s in shelters],
    })

    summary = []
    for name in counties:
        group = [s for s in shelters if s['county'] == name]
        summary.append({'name': name, 'slug': slugify(name), 'n': len(group)})
        write('counties/%s.json' % slugify(name), {
            'v': 1,
            'name': name,
            'n': len(group),
            'a': [[round(s['lat'], 5), round(s['lng'], 5), s['title'], s['sector']]
                  for s in group],
        })
    write('counties.json', {'v': 1, 'counties': summary})

    size = os.path.getsize(os.path.join(DEST, 'shelters.json'))
    print('shelters.json: %d B | counties: %d | with sector: %d' % (
        size, len(counties), sum(1 for s in shelters if s['sector'])))


if __name__ == '__main__':
    main()
