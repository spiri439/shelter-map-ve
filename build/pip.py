"""Point-in-polygon against Romanian county boundaries (geoBoundaries ADM1).

The algorithm indexes query points by latitude once, then for every polygon edge
looks up (by bisection) only the points whose latitude falls inside the edge's
span and runs the crossing test for those. Even/odd counting across *all* rings
of a polygon handles holes for free.

4538 points against 42 counties and 740k edges runs in well under a second.
"""

import bisect
import json
import os
from collections import defaultdict

BOUNDARIES = os.path.join(os.path.dirname(__file__), 'boundaries', 'ro-counties.geojson')

# geoBoundaries ships upper-case, diacritic-free names.
NAMES = {
    'ALBA': 'Alba', 'ARAD': 'Arad', 'ARGES': 'Argeș', 'BACAU': 'Bacău',
    'BIHOR': 'Bihor', 'BISTRITA-NASAUD': 'Bistrița-Năsăud', 'BOTOSANI': 'Botoșani',
    'BRAILA': 'Brăila', 'BRASOV': 'Brașov', 'BUCURESTI': 'București',
    'BUZAU': 'Buzău', 'CALARASI': 'Călărași', 'CARAS-SEVERIN': 'Caraș-Severin',
    'CLUJ': 'Cluj', 'CONSTANTA': 'Constanța', 'COVASNA': 'Covasna',
    'DAMBOVITA': 'Dâmbovița', 'DOLJ': 'Dolj', 'GALATI': 'Galați',
    'GIURGIU': 'Giurgiu', 'GORJ': 'Gorj', 'HARGHITA': 'Harghita',
    'HUNEDOARA': 'Hunedoara', 'IALOMITA': 'Ialomița', 'IASI': 'Iași',
    'ILFOV': 'Ilfov', 'MARAMURES': 'Maramureș', 'MEHEDINTI': 'Mehedinți',
    'MURES': 'Mureș', 'NEAMT': 'Neamț', 'OLT': 'Olt', 'PRAHOVA': 'Prahova',
    'SALAJ': 'Sălaj', 'SATU MARE': 'Satu Mare', 'SIBIU': 'Sibiu',
    'SUCEAVA': 'Suceava', 'TELEORMAN': 'Teleorman', 'TIMIS': 'Timiș',
    'TULCEA': 'Tulcea', 'VALCEA': 'Vâlcea', 'VASLUI': 'Vaslui',
    'VRANCEA': 'Vrancea',
}

_FEATURES = None


def _rings(geometry):
    if geometry['type'] == 'Polygon':
        return list(geometry['coordinates'])
    if geometry['type'] == 'MultiPolygon':
        return [ring for polygon in geometry['coordinates'] for ring in polygon]
    raise ValueError('unsupported geometry: %s' % geometry['type'])


def _load(path=None):
    global _FEATURES
    if _FEATURES is None:
        path = path or BOUNDARIES
        if not os.path.exists(path):
            raise SystemExit(
                'Missing %s — run build/fetch-boundaries.sh first.' % path)
        with open(path, encoding='utf-8') as fh:
            geojson = json.load(fh)
        _FEATURES = [
            (NAMES.get(f['properties']['shapeName'], f['properties']['shapeName']),
             _rings(f['geometry']))
            for f in geojson['features']
        ]
    return _FEATURES


def counties_for(coords):
    """coords: iterable of (lat, lng). Returns a list of county names (or None).

    Bucharest is an enclave inside Ilfov; where a point matches both, Bucharest
    wins.
    """
    coords = list(coords)
    order = sorted(range(len(coords)), key=lambda i: coords[i][0])
    lats = [coords[i][0] for i in order]
    lngs = [c[1] for c in coords]
    result = [None] * len(coords)

    for name, rings in _load():
        crossings = defaultdict(int)
        for ring in rings:
            size = len(ring)
            for k in range(size):
                x0, y0 = ring[k][0], ring[k][1]
                x1, y1 = ring[(k + 1) % size][0], ring[(k + 1) % size][1]
                if y0 == y1:
                    continue
                low, high = (y0, y1) if y0 < y1 else (y1, y0)
                start = bisect.bisect_left(lats, low)
                stop = bisect.bisect_left(lats, high)
                if start == stop:
                    continue
                slope = (x1 - x0) / (y1 - y0)
                for s in range(start, stop):
                    i = order[s]
                    if x0 + (lats[s] - y0) * slope > lngs[i]:
                        crossings[i] += 1
        for i, count in crossings.items():
            if count % 2 and (result[i] is None or name == 'București'):
                result[i] = name

    return result
