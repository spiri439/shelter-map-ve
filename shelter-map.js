/**
 * Vlad Enterprises Shelter Map
 *
 * Leaflet, its stylesheets and the shelter data are fetched only once the map
 * nears the viewport. The map usually sits below the fold, so it has no
 * business competing with the initial render of the page.
 */
(function(window, document) {
  'use strict';

  const cfg = window.SMVEConfig;
  if (!cfg) { return; }

  const T = cfg.text;

  // ============================================================================
  // HELPERS
  // ============================================================================

  /** Strip diacritics so that "timisoara" also matches "Timișoara". */
  function fold(value) {
    return String(value)
      .replace(/ș|ş/g, 's')   // ș, ş
      .replace(/ț|ţ/g, 't')   // ț, ţ
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .toLowerCase();
  }

  /** Great-circle distance in metres. */
  function distance(lat1, lng1, lat2, lng2) {
    const R = 6371000;
    const p1 = lat1 * Math.PI / 180;
    const p2 = lat2 * Math.PI / 180;
    const dp = p2 - p1;
    const dl = (lng2 - lng1) * Math.PI / 180;
    const a = Math.sin(dp / 2) * Math.sin(dp / 2) +
      Math.cos(p1) * Math.cos(p2) * Math.sin(dl / 2) * Math.sin(dl / 2);
    return 2 * R * Math.asin(Math.min(1, Math.sqrt(a)));
  }

  function formatDistance(metres) {
    if (metres < 1000) {
      return (Math.round(metres / 10) * 10) + ' m';
    }
    return (metres / 1000).toFixed(metres < 10000 ? 1 : 0) + ' km';
  }

  function loadScript(url) {
    return new Promise(function(resolve, reject) {
      const el = document.createElement('script');
      el.src = url;
      el.async = true;
      el.onload = resolve;
      el.onerror = function() { reject(new Error('Failed to load ' + url)); };
      document.head.appendChild(el);
    });
  }

  function loadStyle(url) {
    return new Promise(function(resolve) {
      const el = document.createElement('link');
      el.rel = 'stylesheet';
      el.href = url;
      // A missing stylesheet only breaks looks, not behaviour.
      el.onload = resolve;
      el.onerror = resolve;
      document.head.appendChild(el);
    });
  }

  // ============================================================================
  // MAP
  // ============================================================================

  function ShelterMap(root) {
    this.root = root;
    this.elCanvas = root.querySelector('[data-smve-canvas]');
    this.elControls = root.querySelector('[data-smve-controls]');
    this.elCounty = root.querySelector('[data-smve-county]');
    this.elSector = root.querySelector('[data-smve-sector]');
    this.elSectorField = root.querySelector('[data-smve-sector-field]');
    this.elSearch = root.querySelector('[data-smve-search]');
    this.elNearest = root.querySelector('[data-smve-nearest]');
    this.elStatus = root.querySelector('[data-smve-status]');

    this.zoom = parseInt(root.dataset.zoom, 10) || 6;
    this.centre = [parseFloat(root.dataset.lat), parseFloat(root.dataset.lng)];
    this.initialCounty = root.dataset.county || '';

    this.shelters = [];
    this.counties = [];
    this.sectorCounty = '';   // the county that uses sectors, derived from the data
    this.myPosition = null;
  }

  ShelterMap.prototype.status = function(text) {
    this.elStatus.textContent = text || '';
  };

  ShelterMap.prototype.start = function() {
    const self = this;

    return Promise.all([
      loadStyle(cfg.leafletCss),
      loadScript(cfg.leafletJs).then(function() { return loadScript(cfg.clusterJs); }),
      Promise.all(cfg.clusterCss.map(loadStyle)),
      fetch(cfg.shelters, { credentials: 'omit' }).then(function(response) {
        if (!response.ok) { throw new Error('HTTP ' + response.status); }
        return response.json();
      })
    ]).then(function(results) {
      const data = results[3];
      self.counties = data.counties;
      self.shelters = data.a.map(function(row) {
        const county = data.counties[row[0]];
        return {
          county: county,
          lat: row[1],
          lng: row[2],
          name: row[3],
          sector: row[4],
          haystack: fold(row[3] + ' ' + county)
        };
      });

      // Sectors exist for exactly one county; find it rather than hard-coding
      // a name that a translation could break.
      for (let i = 0; i < self.shelters.length; i++) {
        if (self.shelters[i].sector) {
          self.sectorCounty = self.shelters[i].county;
          break;
        }
      }

      self.build();
    }).catch(function(error) {
      self.elCanvas.textContent = '';
      const p = document.createElement('p');
      p.className = 'smve-placeholder';
      p.textContent = T.loadError;
      self.elCanvas.appendChild(p);
      if (window.console && window.console.warn) {
        window.console.warn('[smve]', error);
      }
    });
  };

  ShelterMap.prototype.build = function() {
    const self = this;
    const L = window.L;

    this.L = L;
    this.elCanvas.textContent = '';

    this.map = L.map(this.elCanvas, {
      center: this.centre,
      zoom: this.zoom,
      minZoom: 5,
      maxZoom: 19,
      scrollWheelZoom: false
    });

    // The wheel scrolls the page; the map zooms once it has focus.
    this.map.on('focus', function() { self.map.scrollWheelZoom.enable(); });
    this.map.on('blur', function() { self.map.scrollWheelZoom.disable(); });

    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" rel="nofollow">OpenStreetMap</a>'
    }).addTo(this.map);

    // pin-shelter.png is 48x48; shown at 32 so a cluster of them stays legible,
    // anchored at the base of the bunker rather than its middle.
    this.icon = L.icon({
      iconUrl: cfg.pin,
      iconSize: [32, 32],
      iconAnchor: [16, 32],
      popupAnchor: [0, -30]
    });

    this.cluster = L.markerClusterGroup({
      chunkedLoading: true,
      spiderfyOnMaxZoom: true,
      showCoverageOnHover: false,
      maxClusterRadius: 60
    });

    this.shelters.forEach(function(shelter) {
      const marker = L.marker([shelter.lat, shelter.lng], {
        icon: self.icon,
        title: shelter.name,
        alt: shelter.name
      });
      marker.bindPopup(function() { return self.popup(shelter); });
      shelter.marker = marker;
    });

    this.map.addLayer(this.cluster);

    this.prepareControls();
    this.applyFilter(true);
    this.elControls.hidden = false;
  };

  /** Popup body. Shelter names come from the database, so they go in as text. */
  ShelterMap.prototype.popup = function(shelter) {
    const wrap = document.createElement('div');
    wrap.className = 'smve-popup';

    const name = document.createElement('strong');
    name.textContent = shelter.name;
    wrap.appendChild(name);

    const place = document.createElement('span');
    place.className = 'smve-popup-place';
    place.textContent = shelter.sector
      ? T.sector.replace('%s', shelter.sector) + ', ' + shelter.county
      : shelter.county;
    wrap.appendChild(place);

    if (this.myPosition) {
      const away = document.createElement('span');
      away.className = 'smve-popup-distance';
      away.textContent = T.awayFromYou.replace('%s', formatDistance(distance(
        this.myPosition[0], this.myPosition[1], shelter.lat, shelter.lng
      )));
      wrap.appendChild(away);
    }

    const link = document.createElement('a');
    link.className = 'smve-navigate';
    link.href = 'https://www.google.com/maps/dir/?api=1&destination=' +
      encodeURIComponent(shelter.lat + ',' + shelter.lng);
    link.target = '_blank';
    link.rel = 'noopener noreferrer nofollow';
    link.textContent = T.navigate;
    wrap.appendChild(link);

    return wrap;
  };

  // ============================================================================
  // FILTERS
  // ============================================================================

  ShelterMap.prototype.prepareControls = function() {
    const self = this;

    function option(value, label) {
      const el = document.createElement('option');
      el.value = value;
      el.textContent = label;
      return el;
    }

    this.elCounty.appendChild(option('', T.allCounties));
    this.counties.forEach(function(county) {
      self.elCounty.appendChild(option(county, county));
    });
    if (this.initialCounty && this.counties.indexOf(this.initialCounty) !== -1) {
      this.elCounty.value = this.initialCounty;
    }

    this.elSector.appendChild(option('', T.allSectors));
    for (let s = 1; s <= 6; s++) {
      this.elSector.appendChild(option(String(s), T.sector.replace('%s', s)));
    }

    this.elCounty.addEventListener('change', function() {
      self.elSector.value = '';
      self.applyFilter(true);
    });
    this.elSector.addEventListener('change', function() {
      self.applyFilter(true);
    });

    let timer = null;
    this.elSearch.addEventListener('input', function() {
      window.clearTimeout(timer);
      timer = window.setTimeout(function() { self.applyFilter(true); }, 200);
    });

    this.elNearest.addEventListener('click', function() {
      self.findNearest();
    });
  };

  ShelterMap.prototype.applyFilter = function(fit) {
    const county = this.elCounty.value;
    const needle = fold(this.elSearch.value.trim());

    this.elSectorField.hidden = !this.sectorCounty || county !== this.sectorCounty;
    const sector = this.elSectorField.hidden ? '' : this.elSector.value;

    const matches = this.shelters.filter(function(shelter) {
      if (county && shelter.county !== county) { return false; }
      if (sector && String(shelter.sector) !== sector) { return false; }
      if (needle && shelter.haystack.indexOf(needle) === -1) { return false; }
      return true;
    });

    this.cluster.clearLayers();
    this.cluster.addLayers(matches.map(function(shelter) { return shelter.marker; }));

    if (!matches.length) {
      this.status(T.noResults);
      return;
    }

    this.status(matches.length === 1
      ? T.oneResult
      : T.nResults.replace('%s', matches.length.toLocaleString(cfg.locale)));

    // The configured centre and zoom are only the view before the data lands;
    // once it has, the map frames whatever is actually shown. Without this a
    // wide container at zoom 6 puts half the Balkans around Romania.
    if (fit !== false) {
      this.map.fitBounds(
        this.L.latLngBounds(matches.map(function(shelter) {
          return [shelter.lat, shelter.lng];
        })),
        { padding: [30, 30], maxZoom: 15 }
      );
    }
  };

  // ============================================================================
  // NEAREST SHELTER
  // ============================================================================

  ShelterMap.prototype.findNearest = function() {
    const self = this;

    if (!navigator.geolocation) {
      this.status(T.noPosition);
      return;
    }

    this.elNearest.disabled = true;
    this.status(T.locating);

    navigator.geolocation.getCurrentPosition(function(position) {
      self.elNearest.disabled = false;

      const lat = position.coords.latitude;
      const lng = position.coords.longitude;
      self.myPosition = [lat, lng];

      // Searched across the whole set, not just what is filtered right now.
      let best = null;
      let least = Infinity;
      self.shelters.forEach(function(shelter) {
        const d = distance(lat, lng, shelter.lat, shelter.lng);
        if (d < least) {
          least = d;
          best = shelter;
        }
      });
      if (!best) { return; }

      // Clearing the filters, otherwise the shelter we found may stay hidden.
      self.elCounty.value = '';
      self.elSector.value = '';
      self.elSearch.value = '';
      self.applyFilter(false);

      if (self.myMarker) {
        self.map.removeLayer(self.myMarker);
      }
      self.myMarker = self.L.circleMarker([lat, lng], {
        radius: 8,
        color: '#1f51a1',
        weight: 3,
        fillColor: '#ffffff',
        fillOpacity: 1
      }).addTo(self.map).bindPopup(T.yourPosition);

      self.status(T.nearest + ': ' + best.name + ' — ' +
        T.awayFromYou.replace('%s', formatDistance(least)));

      self.cluster.zoomToShowLayer(best.marker, function() {
        best.marker.openPopup();
      });
    }, function() {
      self.elNearest.disabled = false;
      self.status(T.noPosition);
    }, { enableHighAccuracy: true, timeout: 15000, maximumAge: 60000 });
  };

  // ============================================================================
  // BOOT
  // ============================================================================

  function activate(root) {
    if (root.dataset.smveStarted) { return; }
    root.dataset.smveStarted = '1';
    new ShelterMap(root).start();
  }

  function init() {
    const roots = document.querySelectorAll('[data-smve-map]');
    if (!roots.length) { return; }

    Array.prototype.forEach.call(roots, function(root) {
      if (!('IntersectionObserver' in window)) {
        activate(root);
        return;
      }
      const observer = new IntersectionObserver(function(entries) {
        entries.forEach(function(entry) {
          if (entry.isIntersecting) {
            observer.disconnect();
            activate(root);
          }
        });
      }, { rootMargin: '300px 0px' });
      observer.observe(root);
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})(window, document);
