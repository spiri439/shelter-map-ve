<?php
/**
 * Print the shortcode's rendered markup, for build/make-screenshots.py.
 *
 * Usage: php build/render-markup.php [county-slug]
 */
require __DIR__ . '/../tests/wp-harness.php';
require __DIR__ . '/../shelter-map.php';

if (isset($argv[1]) && $argv[1] !== '') {
    $_GET['county'] = $argv[1];
}

echo call_user_func($GLOBALS['__shortcodes']['smve_map'], array());
