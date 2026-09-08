#!/bin/sh
# Romanian county boundaries (ADM1), pinned to a geoBoundaries release commit so
# the build stays reproducible. ~32 MB, deliberately not committed.
#
# Licence: CC BY 4.0 — https://www.geoboundaries.org
# Only the resulting county names are shipped in the plugin, never the geometry.
set -e
DIR="$(dirname "$0")/boundaries"
URL="https://github.com/wmgeolab/geoBoundaries/raw/9469f09/releaseData/gbOpen/ROU/ADM1/geoBoundaries-ROU-ADM1.geojson"
mkdir -p "$DIR"
if [ -s "$DIR/ro-counties.geojson" ]; then
  echo "already present: $DIR/ro-counties.geojson"
  exit 0
fi
echo "downloading county boundaries (~32 MB)…"
curl -sfL -m 300 -A 'shelter-map-ve build/1.0' "$URL" -o "$DIR/ro-counties.geojson"
echo "done: $(wc -c < "$DIR/ro-counties.geojson") bytes"
