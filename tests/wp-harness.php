<?php
/**
 * The bare minimum of WordPress needed to render the shortcode outside WP.
 *
 * Enough to exercise the data reading, the county navigation, the per-county
 * list, the query-argument validation and the escaping — none of which need a
 * real WordPress to be meaningful.
 */

define('ABSPATH', __DIR__);

$GLOBALS['__hooks'] = array();
$GLOBALS['__shortcodes'] = array();
$GLOBALS['__scripts'] = array();
$GLOBALS['__styles'] = array();
$GLOBALS['__inline'] = array();

function add_action($hook, $cb, $priority = 10, $args = 1) { $GLOBALS['__hooks'][$hook][] = $cb; }
function add_filter($hook, $cb, $priority = 10, $args = 1) { $GLOBALS['__hooks'][$hook][] = $cb; }
function add_shortcode($tag, $cb) { $GLOBALS['__shortcodes'][$tag] = $cb; }
function plugin_dir_path($file) { return dirname($file) . '/'; }
function plugin_dir_url($file) { return 'https://example.test/wp-content/plugins/' . basename(dirname($file)) . '/'; }
function is_singular() { return true; }
function get_post() { return $GLOBALS['__post']; }
function has_shortcode($content, $tag) { return strpos($content, '[' . $tag) !== false; }
function get_permalink() { return 'https://example.test/shelters/'; }
function wp_enqueue_style($h, $src = '', $deps = array(), $ver = '') { $GLOBALS['__styles'][$h] = $src; }
function wp_enqueue_script($h, $src = '', $deps = array(), $ver = '', $extra = array()) { $GLOBALS['__scripts'][$h] = array($src, $extra); }
function wp_add_inline_script($h, $data, $position = 'after') { $GLOBALS['__inline'][$h] = $data; }
function wp_json_encode($data, $flags = 0) { return json_encode($data, $flags | JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE); }
function wp_unslash($value) { return $value; }
function sanitize_key($key) { return preg_replace('/[^a-z0-9_\-]/', '', strtolower($key)); }
function esc_html($text) { return htmlspecialchars((string) $text, ENT_QUOTES, 'UTF-8'); }
function esc_attr($text) { return htmlspecialchars((string) $text, ENT_QUOTES, 'UTF-8'); }
function esc_url($url) { return htmlspecialchars((string) $url, ENT_QUOTES, 'UTF-8'); }
function esc_html__($text, $domain = '') { return esc_html(__($text, $domain)); }
function esc_html_e($text, $domain = '') { echo esc_html__($text, $domain); }
function esc_attr_e($text, $domain = '') { echo esc_attr(__($text, $domain)); }
function get_locale() { return 'ro_RO'; }
function number_format_i18n($number) { return number_format((float) $number, 0, ',', '.'); }
function add_query_arg($key, $value, $url) { return $url . (strpos($url, '?') === false ? '?' : '&') . $key . '=' . rawurlencode($value); }

function shortcode_atts($pairs, $atts, $shortcode = '') {
    $atts = (array) $atts;
    $out = array();
    foreach ($pairs as $name => $default) {
        $out[$name] = array_key_exists($name, $atts) ? $atts[$name] : $default;
    }
    return $out;
}

/** Reads the real .mo, so the shipped translation is tested too. */
class Harness_MO {
    public $catalog = array();
    public function __construct($file) {
        $data = file_get_contents($file);
        $count = unpack('V', substr($data, 8, 4))[1];
        $keys = unpack('V', substr($data, 12, 4))[1];
        $values = unpack('V', substr($data, 16, 4))[1];
        for ($i = 0; $i < $count; $i++) {
            $kl = unpack('V', substr($data, $keys + $i * 8, 4))[1];
            $kp = unpack('V', substr($data, $keys + $i * 8 + 4, 4))[1];
            $vl = unpack('V', substr($data, $values + $i * 8, 4))[1];
            $vp = unpack('V', substr($data, $values + $i * 8 + 4, 4))[1];
            $this->catalog[substr($data, $kp, $kl)] = substr($data, $vp, $vl);
        }
    }
}

$GLOBALS['__mo'] = new Harness_MO(__DIR__ . '/../languages/shelter-map-ve-ro_RO.mo');

function __($text, $domain = '') {
    $catalog = $GLOBALS['__mo']->catalog;
    return isset($catalog[$text]) ? $catalog[$text] : $text;
}

function _n($single, $plural, $number, $domain = '') {
    $catalog = $GLOBALS['__mo']->catalog;
    $key = $single . "\0" . $plural;
    if (!isset($catalog[$key])) { return $number === 1 ? $single : $plural; }
    $forms = explode("\0", $catalog[$key]);
    // Romanian: nplurals=3
    $i = ($number == 1) ? 0 : ((($number == 0) || ($number % 100 > 0 && $number % 100 < 20)) ? 1 : 2);
    return isset($forms[$i]) ? $forms[$i] : $forms[count($forms) - 1];
}

class WP_Post { public $post_content = '[smve_map]'; }
$GLOBALS['__post'] = new WP_Post();
