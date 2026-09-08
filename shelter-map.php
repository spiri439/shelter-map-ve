<?php
/**
 * Plugin Name: Vlad Enterprises Shelter Map
 * Plugin URI: https://github.com/spiri439/shelter-map-ve
 * Description: Interactive map of Romania's civil protection shelters, with county and sector filtering, text search, and nearest-shelter lookup. Leaflet and OpenStreetMap, no API key. Shortcode: [smve_map]
 * Version: 1.0.0
 * Author: nextdoorentertainment
 * Author URI: https://vladenterprises.ro
 * License: MIT
 * License URI: https://opensource.org/licenses/MIT
 * Text Domain: shelter-map-ve
 * Domain Path: /languages
 * Requires at least: 5.8
 * Requires PHP: 7.4
 */

if (!defined('ABSPATH')) { exit; }

define('SMVE_VERSION', '1.0.0');
define('SMVE_PLUGIN_DIR', plugin_dir_path(__FILE__));
define('SMVE_PLUGIN_URL', plugin_dir_url(__FILE__));

class SMVE_Shelter_Map {

    /** Decoded data files, cached per request. */
    private $data = array();

    public function __construct() {
        add_action('wp_enqueue_scripts', array($this, 'enqueue_assets'));
        add_shortcode('smve_map', array($this, 'shortcode_map'));
    }

    /* ---------------------------------------------------------------------
     * DATA
     * ------------------------------------------------------------------- */

    /**
     * Read a JSON file from data/. Generated at build time and immutable at
     * runtime, so holding it for the request is enough.
     *
     * @param string $name Path inside data/, without the .json extension.
     * @return array|null
     */
    private function data($name) {
        if (array_key_exists($name, $this->data)) {
            return $this->data[$name];
        }

        // Only predictable names: one optional subdirectory, no traversal.
        if (!preg_match('#^[a-z0-9-]+(/[a-z0-9-]+)?$#', $name)) {
            return $this->data[$name] = null;
        }

        $file = SMVE_PLUGIN_DIR . 'data/' . $name . '.json';
        if (!is_readable($file)) {
            return $this->data[$name] = null;
        }

        $decoded = json_decode(file_get_contents($file), true);

        return $this->data[$name] = (is_array($decoded) ? $decoded : null);
    }

    /**
     * The county requested through the URL (?county=cluj), validated against
     * the real list so an arbitrary value can never reach the filesystem.
     *
     * @return array|null Entry from data/counties.json.
     */
    private function requested_county() {
        // No nonce here on purpose: this is a public, read-only filter shared in
        // links and indexed by search engines. Nothing is written, and the value
        // only ever reaches the shipped county list a few lines below.
        // phpcs:ignore WordPress.Security.NonceVerification.Recommended
        $requested = isset($_GET['county']) ? wp_unslash($_GET['county']) : '';
        if (!is_string($requested) || $requested === '') {
            return null;
        }

        $slug = sanitize_key($requested);
        $summary = $this->data('counties');
        if (!$summary) {
            return null;
        }

        foreach ($summary['counties'] as $county) {
            if ($county['slug'] === $slug) {
                return $county;
            }
        }

        return null;
    }

    /* ---------------------------------------------------------------------
     * ASSETS
     * ------------------------------------------------------------------- */

    /** Does the current page actually use the shortcode? */
    private function page_has_map() {
        if (!is_singular()) {
            return false;
        }

        $post = get_post();

        return $post instanceof WP_Post && has_shortcode((string) $post->post_content, 'smve_map');
    }

    /**
     * Only our own small script is enqueued. Leaflet, its stylesheets and the
     * 4538 shelters are fetched from JavaScript once the map nears the
     * viewport: the map sits below the fold, so it has no business competing
     * with the initial render.
     */
    public function enqueue_assets() {
        if (!$this->page_has_map()) {
            return;
        }

        wp_enqueue_style('smve-shelter-map', SMVE_PLUGIN_URL . 'shelter-map.css', array(), SMVE_VERSION);

        wp_enqueue_script('smve-shelter-map', SMVE_PLUGIN_URL . 'shelter-map.js', array(), SMVE_VERSION, array(
            'strategy'  => 'defer',
            'in_footer' => true,
        ));

        wp_add_inline_script('smve-shelter-map', 'window.SMVEConfig = ' . wp_json_encode(array(
            'shelters'   => SMVE_PLUGIN_URL . 'data/shelters.json?v=' . SMVE_VERSION,
            'leafletJs'  => SMVE_PLUGIN_URL . 'vendor/leaflet.js',
            'leafletCss' => SMVE_PLUGIN_URL . 'vendor/leaflet.css',
            'clusterJs'  => SMVE_PLUGIN_URL . 'vendor/leaflet.markercluster.js',
            'clusterCss' => array(
                SMVE_PLUGIN_URL . 'vendor/MarkerCluster.css',
                SMVE_PLUGIN_URL . 'vendor/MarkerCluster.Default.css',
            ),
            'pin'        => SMVE_PLUGIN_URL . 'pin-shelter.png',
            // BCP 47, so counts are grouped the way the site's language does it.
            'locale'     => str_replace('_', '-', get_locale()),
            'text'       => array(
                'loadError'    => __('The map could not be loaded. Please reload the page.', 'shelter-map-ve'),
                'navigate'     => __('Directions', 'shelter-map-ve'),
                /* translators: %s: sector number, 1 to 6. */
                'sector'       => __('Sector %s', 'shelter-map-ve'),
                /* translators: %s: a formatted distance, e.g. "420 m" or "3.7 km". */
                'awayFromYou'  => __('%s away from you', 'shelter-map-ve'),
                'nearest'      => __('Nearest shelter to you', 'shelter-map-ve'),
                'yourPosition' => __('Your position', 'shelter-map-ve'),
                'locating'     => __('Finding your position…', 'shelter-map-ve'),
                'noPosition'   => __('Could not determine your position. Check that location access is allowed.', 'shelter-map-ve'),
                'noResults'    => __('No shelter matches your search.', 'shelter-map-ve'),
                'oneResult'    => __('1 shelter', 'shelter-map-ve'),
                /* translators: %s: number of shelters matching the current filter. */
                'nResults'     => __('%s shelters', 'shelter-map-ve'),
                'allCounties'  => __('All counties', 'shelter-map-ve'),
                'allSectors'   => __('All sectors', 'shelter-map-ve'),
            ),
        )) . ';', 'before');
    }

    /* ---------------------------------------------------------------------
     * SHORTCODE
     * ------------------------------------------------------------------- */

    /**
     * [smve_map height="600" zoom="6" lat="44.109417" lng="24.359083"]
     *
     * Server-side output covers everything that still makes sense without
     * JavaScript: the total, the county navigation with per-county counts and,
     * when the URL asks for one county, that county's list of shelters. The
     * map is layered on top from JavaScript.
     */
    public function shortcode_map($atts) {
        $atts = shortcode_atts(array(
            'height' => 600,
            'zoom'   => 6,
            'lat'    => 44.109417,
            'lng'    => 24.359083,
        ), $atts, 'smve_map');

        $summary = $this->data('counties');
        if (!$summary) {
            return '';
        }

        $total = 0;
        foreach ($summary['counties'] as $county) {
            $total += (int) $county['n'];
        }

        $selected = $this->requested_county();
        $height = max(300, min(1200, (int) $atts['height']));
        $base = get_permalink();

        ob_start();
        ?>
        <div class="smve-map"
            data-smve-map
            data-zoom="<?php echo esc_attr((int) $atts['zoom']); ?>"
            data-lat="<?php echo esc_attr((float) $atts['lat']); ?>"
            data-lng="<?php echo esc_attr((float) $atts['lng']); ?>"
            <?php if ($selected) : ?>
            data-county="<?php echo esc_attr($selected['name']); ?>"
            <?php endif; ?>
        >
            <div class="smve-bar">
                <p class="smve-total">
                    <?php
                    printf(
                        /* translators: %s: number of shelters. */
                        esc_html(_n('%s civil protection shelter', '%s civil protection shelters', $total, 'shelter-map-ve')),
                        '<strong>' . esc_html(number_format_i18n($total)) . '</strong>'
                    );
                    ?>
                </p>

                <div class="smve-controls" data-smve-controls hidden>
                    <label class="smve-field">
                        <span><?php esc_html_e('County', 'shelter-map-ve'); ?></span>
                        <select data-smve-county></select>
                    </label>

                    <label class="smve-field" data-smve-sector-field hidden>
                        <span><?php esc_html_e('Sector', 'shelter-map-ve'); ?></span>
                        <select data-smve-sector></select>
                    </label>

                    <label class="smve-field smve-field--search">
                        <span><?php esc_html_e('Search by address or name', 'shelter-map-ve'); ?></span>
                        <input type="search" data-smve-search
                            placeholder="<?php esc_attr_e('e.g. Main Street', 'shelter-map-ve'); ?>">
                    </label>

                    <button type="button" class="smve-button" data-smve-nearest>
                        <?php esc_html_e('Nearest to me', 'shelter-map-ve'); ?>
                    </button>
                </div>
            </div>

            <div class="smve-canvas"
                data-smve-canvas
                style="height: <?php echo esc_attr($height); ?>px;"
                role="application"
                aria-label="<?php esc_attr_e('Civil protection shelter map', 'shelter-map-ve'); ?>">
                <p class="smve-placeholder"><?php esc_html_e('Loading the map…', 'shelter-map-ve'); ?></p>
            </div>

            <p class="smve-status" data-smve-status role="status" aria-live="polite"></p>

            <?php /* Server-rendered list: works without JavaScript and is indexable. */ ?>
            <div class="smve-server-list">
                <?php if ($selected) : ?>
                    <h2 class="smve-county-title">
                        <?php
                        printf(
                            /* translators: 1: county or municipality name, 2: number of shelters. */
                            esc_html__('Shelters in %1$s (%2$s)', 'shelter-map-ve'),
                            esc_html($selected['name']),
                            esc_html(number_format_i18n((int) $selected['n']))
                        );
                        ?>
                    </h2>
                    <?php
                    $detail = $this->data('counties/' . $selected['slug']);
                    if ($detail && !empty($detail['a'])) :
                        ?>
                        <ol class="smve-list">
                            <?php foreach ($detail['a'] as $shelter) : ?>
                                <li>
                                    <span class="smve-name"><?php echo esc_html($shelter[2]); ?></span>
                                    <a class="smve-navigate"
                                        href="<?php echo esc_url(sprintf('https://www.google.com/maps/dir/?api=1&destination=%s,%s', $shelter[0], $shelter[1])); ?>"
                                        target="_blank" rel="noopener noreferrer nofollow">
                                        <?php esc_html_e('Directions', 'shelter-map-ve'); ?>
                                    </a>
                                </li>
                            <?php endforeach; ?>
                        </ol>
                        <?php
                    endif;
                    ?>
                    <p><a href="<?php echo esc_url($base); ?>"><?php esc_html_e('← All counties', 'shelter-map-ve'); ?></a></p>
                <?php else : ?>
                    <h2 class="smve-county-title"><?php esc_html_e('Shelters by county', 'shelter-map-ve'); ?></h2>
                    <ul class="smve-counties">
                        <?php foreach ($summary['counties'] as $county) : ?>
                            <li>
                                <a href="<?php echo esc_url(add_query_arg('county', $county['slug'], $base)); ?>">
                                    <?php echo esc_html($county['name']); ?>
                                    <span class="smve-count"><?php echo esc_html(number_format_i18n((int) $county['n'])); ?></span>
                                </a>
                            </li>
                        <?php endforeach; ?>
                    </ul>
                <?php endif; ?>
            </div>
        </div>
        <?php
        return (string) ob_get_clean();
    }
}

new SMVE_Shelter_Map();
