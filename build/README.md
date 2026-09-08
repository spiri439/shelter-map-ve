# Build

Nothing here ships with the plugin. `.distignore` keeps this folder out of the zip.

## Order

```sh
sh  build/fetch-boundaries.sh   # county polygons, ~32 MB, not committed
python3 build/build-data.py     # source-data/markers-raw.tsv -> data/*.json
python3 build/make-mo.py        # languages/*.po and *.mo
python3 build/make-images.py    # .wordpress-org/ icon + banner
python3 build/make-screenshots.py   # .wordpress-org/ screenshot-1..3
php     tests/render-test.php   # 27 assertions against the rendered shortcode
python3 build/make-zip.py       # dist/shelter-map-ve.zip
```

`make-zip.py` refuses to run if anything unexpected sits in the plugin root, so a
stray Plugin Check export cannot ride along into a release again. Put such files in
`reports/`, which is ignored by both git and `.distignore`.

## Images

`pin-shelter.png` is the author's own drawing and is **not** generated — it is committed
as it is, and `make-images.py` reuses it so the marker, the directory icon and the
banner all carry the same bunker. The banner's county outlines and all 4538 dots are the
plugin's real data.

`make-screenshots.py` renders the plugin for real: the shortcode's own markup (through
`tests/wp-harness.php`), its own stylesheet, script and data, served from a throwaway
local HTTP server, with tiles from OpenStreetMap. Nothing is mocked up.

Both need headless Chromium, the only rasteriser present. It is a snap, and snap
confinement cannot read `/tmp` or `/mnt`, so they work in `~/.cache/smve-*` and copy the
results back.

`build-data.py` and `make-mo.py` are deterministic: re-running them on unchanged
input reproduces byte-identical output.

## The other two scripts

`export-markers.sh` re-exports the marker rows from the live WP Google Maps
tables. `source-data/markers-raw.tsv` is the frozen export this build was made
from, so this is only needed if the upstream registers change.

`regeocode.py` resolves the records whose coordinates contradict their own
address and writes `source-data/fixed-coordinates.json`. It talks to Nominatim at
roughly one request per second, so it takes a minute. Its output is committed —
there is no reason to re-run it unless the registers change.

## Data format

`data/shelters.json` — one array per shelter, positional to keep it small:

```
[countyIndex, lat, lng, name, sector]
```

`countyIndex` points into the sibling `counties` array; `sector` is 0 everywhere
except Bucharest. 4538 rows come to 323 KB, about 75 KB over the wire.

`data/counties.json` is the summary the PHP navigation reads (name, slug, count).
`data/counties/<slug>.json` is one file per county, `[lat, lng, name, sector]`,
so rendering a single county's list server-side never parses the full set.

## Requirements

Python 3.8+ and PHP 7.4+, both standard library only. No Node, no Composer, no
build step for the plugin's own JS and CSS — they ship as written.
