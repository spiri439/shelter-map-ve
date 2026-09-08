#!/bin/sh
# Re-export the marker rows from the WP Google Maps tables of a WordPress site.
#
# Kept for reference: source-data/markers-raw.tsv is the frozen export this
# build was made from, so this is only needed if the upstream registers change.
#
# Columns: id, lat, lng, title (tab separated, no header).
#
# Usage: sh build/export-markers.sh [/path/to/wordpress] [map-id]
#          > source-data/markers-raw.tsv
set -e

WP_PATH="${1:-.}"
MAP_ID="${2:-3}"

prefix=$(wp --path="$WP_PATH" db prefix)

wp --path="$WP_PATH" db query "SELECT id, lat, lng, title
  FROM ${prefix}wpgmza
  WHERE map_id = ${MAP_ID} AND approved = 1
  ORDER BY id;" --skip-column-names
