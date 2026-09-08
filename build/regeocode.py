#!/usr/bin/env python3
"""Re-geocode the shelters whose coordinates contradict their own address.

Thirteen records name a Bucharest sector in the title but sit outside Bucharest
on the map. The corruption is systematic: the integer part of the latitude or
longitude is one too high (45.44229,27.13429 instead of 44.44226,26.13433), so
these are transcription errors in the source registers, not map bugs.

Each address is resolved through Nominatim and only accepted when the result
lies in Bucharest; the score prefers a match on street, sector and house number.
Results land in source-data/fixed-coordinates.json, which build-data.py applies.

Nominatim allows roughly one request per second and wants a real User-Agent, so
this deliberately runs slowly. It only needs re-running if the source registers
change.
"""

import html
import json
import os
import re
import time
import unicodedata
import urllib.parse
import urllib.request

import pip as point_in_polygon

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE = os.path.join(ROOT, 'source-data', 'markers-raw.tsv')
LOG = os.path.join(ROOT, 'source-data', 'geocode-results.json')
DEST = os.path.join(ROOT, 'source-data', 'fixed-coordinates.json')

USER_AGENT = 'shelter-map-ve build/1.0 (+https://github.com/spiri439/shelter-map-ve)'
DELAY = 1.2

SECTOR = re.compile(r'sector\s*([1-6])', re.I)
STREET_KIND = (r'(?:str\.?|strada|bd\.?|b-dul|bulevardul|şos\.?|sos\.?|şoseaua|'
               r'soseaua|aleea|calea|pia[țţ]a|drumul|intrarea)')


def clean(title):
    title = re.sub(r'<br\s*/?>', ' ', title, flags=re.I)
    return re.sub(r'\s+', ' ', html.unescape(html.unescape(title))).strip()


def fold(value):
    value = value.replace('ş', 's').replace('ţ', 't')
    value = unicodedata.normalize('NFD', value)
    return ''.join(c for c in value if unicodedata.category(c) != 'Mn').lower()


def parse_address(title):
    """'Str. Turda 127 Bl. 2, sc. C, Sector 1' -> ('Turda', '127')."""
    text = clean(title).replace('ş', 's').replace('ţ', 't')
    match = re.match(r'^\s*(%s)\s+(.+?)\s+(?:nr\.?\s*)?(\d+)' % STREET_KIND, text, re.I)
    if not match:
        return None, None
    street = re.sub(r'\s+(bl\.?|bloc|sc\.?|corp|nr\.?)\b.*$', '',
                    match.group(2), flags=re.I).strip(' .,')
    return street, match.group(3)


def query(params):
    url = 'https://nominatim.openstreetmap.org/search?' + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=25) as fh:
            return json.load(fh)
    except Exception as error:            # noqa: BLE001 - network, log and move on
        print('    request failed: %s' % error)
        return []


def main():
    shelters = []
    with open(SOURCE, encoding='utf-8') as fh:
        for line in fh:
            line = line.rstrip('\n')
            if not line:
                continue
            parts = line.split('\t')
            shelters.append({'id': int(parts[0]), 'lat': float(parts[1]),
                             'lng': float(parts[2]), 'title': '\t'.join(parts[3:]).strip()})

    counties = point_in_polygon.counties_for((s['lat'], s['lng']) for s in shelters)
    suspects = [s for s, county in zip(shelters, counties)
                if SECTOR.search(s['title']) and county != 'București']
    print('records to re-geocode: %d' % len(suspects))

    log = []
    for shelter in suspects:
        sector = SECTOR.search(shelter['title']).group(1)
        street, number = parse_address(shelter['title'])
        print('%6d  street=%r number=%r sector=%s' % (shelter['id'], street, number, sector))

        results = []
        if street:
            attempts = (
                {'street': '%s %s' % (number, street), 'city': 'Bucharest',
                 'country': 'Romania', 'format': 'jsonv2', 'limit': 3},
                {'q': 'Strada %s %s, Sectorul %s, Bucuresti' % (street, number, sector),
                 'format': 'jsonv2', 'limit': 3, 'countrycodes': 'ro'},
                {'q': 'Strada %s, Bucuresti' % street,
                 'format': 'jsonv2', 'limit': 3, 'countrycodes': 'ro'},
            )
            for params in attempts:
                results = query(params)
                time.sleep(DELAY)
                if results:
                    break

        log.append({
            'id': shelter['id'], 'title': clean(shelter['title']),
            'street': street, 'number': number, 'sector': sector,
            'old': [shelter['lat'], shelter['lng']],
            'results': [{'lat': float(r['lat']), 'lng': float(r['lon']),
                         'name': r.get('display_name', '')[:130]} for r in results[:3]],
        })

    # Pick the best candidate: it must be in Bucharest; street, sector and house
    # number each add to the score, and only a house-number hit counts as exact.
    fixed = {}
    for entry in log:
        street = fold(entry['street'] or '')
        best, best_score, reasons = None, -1, ''
        for candidate in entry['results']:
            name = fold(candidate['name'])
            if 'bucuresti' not in name:
                continue
            score, why = 0, []
            if street and street in name:
                score += 4
                why.append('street')
            if ('sector %s' % entry['sector']) in name:
                score += 3
                why.append('sector')
            if entry['number'] and re.search(
                    r'(?:^|,\s*)%s,' % re.escape(entry['number']), candidate['name']):
                score += 2
                why.append('number')
            if score > best_score:
                best, best_score, reasons = candidate, score, '+'.join(why)
        if best is None:
            print('%6d  UNRESOLVED  %s' % (entry['id'], entry['title'][:60]))
            continue
        fixed[str(entry['id'])] = {
            'lat': round(best['lat'], 5),
            'lng': round(best['lng'], 5),
            'precision': 'exact' if 'number' in reasons else 'street',
            'matched': reasons,
            'source': best['name'],
        }

    with open(LOG, 'w', encoding='utf-8') as fh:
        json.dump(log, fh, ensure_ascii=False, indent=1)
    with open(DEST, 'w', encoding='utf-8') as fh:
        json.dump(fixed, fh, ensure_ascii=False, indent=1)

    print('\nresolved: %d / %d (exact: %d, street level: %d)' % (
        len(fixed), len(log),
        sum(1 for v in fixed.values() if v['precision'] == 'exact'),
        sum(1 for v in fixed.values() if v['precision'] == 'street')))


if __name__ == '__main__':
    main()
