=== Vlad Enterprises Shelter Map ===
Contributors: nextdoorentertainment
Tags: map, leaflet, openstreetmap, civil protection, shelters
Requires at least: 5.8
Tested up to: 7.0
Requires PHP: 7.4
Stable tag: 1.0.0
License: MIT
License URI: https://opensource.org/licenses/MIT

Interactive map of Romania's civil protection shelters, with county and sector filtering, text search and nearest-shelter lookup. Leaflet and OpenStreetMap, no API key.

== Description ==

Vlad Enterprises Shelter Map renders the 4,538 civil protection shelters of Romania on a clustered Leaflet map. It needs no map API key, no billing account and no third-party map service beyond OpenStreetMap tiles.

The shelter list ships with the plugin as static JSON, so no database tables and no queries are involved. Every shelter carries a name, an address and coordinates; the county is precomputed for each one, and Bucharest shelters also carry their sector.

= Key features =

* Clustered map of all shelters, so several thousand markers stay usable on a phone.
* Filtering by county, and by sector inside Bucharest.
* Diacritic-insensitive text search over shelter names and addresses ("timisoara" finds "Timișoara").
* "Nearest to me": uses the browser's geolocation, finds the closest shelter across the whole set, zooms to it and shows the distance.
* A "Directions" link on every shelter that opens the visitor's own maps app.
* Server-rendered county navigation with per-county counts, and a full per-county list at `?county=<slug>`. Both work without JavaScript and are indexable.
* Leaflet, its stylesheets and the shelter data load only once the map nears the viewport, so a map placed below the fold does not compete with the page's first render.
* No settings page, no database writes, no cookies, no tracking.

= Shortcode =

`[smve_map]`

Attributes, all optional:

* `height` — map height in pixels (300–1200, default 600).
* `zoom` — initial zoom level (default 6).
* `lat`, `lng` — initial centre (default 44.109417, 24.359083).

`zoom`, `lat` and `lng` set the view shown before the shelters arrive; once they
have, the map frames whatever is currently displayed.

Example: `[smve_map height="700" zoom="7"]`

== Installation ==

1. Upload the `shelter-map-ve` folder to `/wp-content/plugins/`.
2. Activate the plugin through the Plugins screen.
3. Put `[smve_map]` in the page where the map should appear.

== Frequently Asked Questions ==

= Does it need a Google Maps API key? =

No. Map tiles come from OpenStreetMap and require no key. The "Directions" links open Google Maps in a new tab, which needs no key either.

= Are the shelters loaded from the database? =

No. They ship as static JSON files inside the plugin, which means they are cacheable by the browser and by any page cache, and they cost no queries.

= Can the map be placed more than once on a page? =

Yes. Every instance initialises on its own.

= How is the county of each shelter determined? =

It is precomputed from the shelter's coordinates by point-in-polygon against Romanian county boundaries, then shipped inside the data files. Nothing is computed at runtime.

== Screenshots ==

1. The whole country: 4,538 shelters clustered, with the county, sector and search controls above the map.
2. A single county. Picking one filters the map and lists every shelter in it, each with a directions link.
3. The same map on a phone.

== External services ==

This plugin relies on two external services, both only in the visitor's browser and only on pages that contain the shortcode:

* **OpenStreetMap tiles** (`tile.openstreetmap.org`) — supplies the map background. The visitor's browser requests map tiles, which sends their IP address and the map area being viewed. Terms: https://operations.osmfoundation.org/policies/tiles/ — Privacy policy: https://osmfoundation.org/wiki/Privacy_Policy
* **Google Maps** (`google.com/maps`) — only when the visitor clicks a "Directions" link, which opens Google Maps in a new tab with the shelter's coordinates. Nothing is sent unless the visitor clicks. Terms: https://policies.google.com/terms — Privacy policy: https://policies.google.com/privacy

No data is sent to any service owned by the plugin author, and the plugin sets no cookies.

== Third-party libraries ==

Bundled in `vendor/`, unmodified:

* **Leaflet 1.9.4** — (c) 2010-2023 Vladimir Agafonkin, (c) 2010-2011 CloudMade. BSD-2-Clause. https://leafletjs.com
* **Leaflet.markercluster 1.5.3** — (c) 2012 David Leaver. MIT. https://github.com/Leaflet/Leaflet.markercluster

== Data ==

The shelter list comes from the civil protection shelter registers published per county. County assignment was derived offline from each shelter's coordinates using the geoBoundaries ADM1 boundaries for Romania (CC BY 4.0, https://www.geoboundaries.org); only the resulting county name is shipped, not the boundary geometry.

Twelve records whose coordinates fell outside the county named in their own address were re-geocoded against OpenStreetMap and corrected. The underlying registers are not error-free; corrections are welcome through the issue tracker.

== Changelog ==

= 1.0.0 =
* First release.
