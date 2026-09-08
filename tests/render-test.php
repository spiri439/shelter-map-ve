<?php
/**
 * Renders the shortcode against the harness and asserts what matters.
 *
 * Usage: php tests/render-test.php
 */

require __DIR__ . '/wp-harness.php';
require __DIR__ . '/../shelter-map.php';

$failures = 0;

function check($label, $actual, $expected = true) {
    global $failures;
    $ok = ($expected === true) ? (bool) $actual : ($actual === $expected);
    if (!$ok) { $failures++; }
    printf("  [%s] %-46s %s\n", $ok ? 'ok' : 'FAIL', $label,
        ($expected === true) ? '' : var_export($actual, true));
}

$render = $GLOBALS['__shortcodes']['smve_map'];

echo "ASSETS\n";
call_user_func($GLOBALS['__hooks']['wp_enqueue_scripts'][0]);
check('stylesheet enqueued', isset($GLOBALS['__styles']['smve-shelter-map']));
check('script enqueued', isset($GLOBALS['__scripts']['smve-shelter-map']));
check('deferred', $GLOBALS['__scripts']['smve-shelter-map'][1]['strategy'], 'defer');
$config = json_decode(trim(str_replace(
    array('window.SMVEConfig = ', ';'), '', $GLOBALS['__inline']['smve-shelter-map'])), true);
check('config decodes', is_array($config));
check('config is translated', $config['text']['navigate'], 'Navighează');
check('no Bucharest string in config', !isset($config['text']['bucharest']));
check('locale passed as BCP 47', $config['locale'], 'ro-RO');

echo "\nDEFAULT RENDER\n";
$html = call_user_func($render, array());
preg_match('#<p class="smve-total">(.*?)</p>#s', $html, $m);
$total = trim(html_entity_decode(strip_tags($m[1])));
check('Romanian 20+ plural', $total, '4.538 de adăposturi de protecție civilă');
check('42 county links', preg_match_all('#\?county=[a-z-]+#', $html), 42);
check('map container present', strpos($html, 'data-smve-map') !== false);
check('controls start hidden', strpos($html, 'data-smve-controls hidden') !== false);

echo "\nSINGLE COUNTY (?county=cluj)\n";
$_GET['county'] = 'cluj';
$html = call_user_func($render, array('height' => 700));
preg_match('#<h2 class="smve-county-title">(.*?)</h2>#s', $html, $m);
check('heading', trim(preg_replace('#\s+#', ' ', html_entity_decode(strip_tags($m[1])))),
    'Adăposturi în Cluj (198)');
check('198 list items', preg_match_all('#<span class="smve-name">#', $html), 198);
check('198 directions links', preg_match_all('#google\.com/maps/dir#', $html), 198);
check('height applied', strpos($html, 'height: 700px') !== false);
check('data-county passed to JS', strpos($html, 'data-county="Cluj"') !== false);

echo "\nBAD INPUT\n";
foreach (array('../../../etc/passwd', 'nonexistent', '', 'cluj/../bucuresti', 'alba;drop') as $value) {
    $_GET['county'] = $value;
    $html = call_user_func($render, array());
    check('falls back for ' . var_export($value, true),
        strpos($html, 'smve-counties') !== false);
}
// sanitize_key() lower-cases, so an upper-case slug is a legitimate hit.
$_GET['county'] = 'CLUJ';
$html = call_user_func($render, array());
check('upper-case slug resolves', strpos($html, 'Cluj (198)') !== false);

echo "\nESCAPING\n";
$_GET['county'] = 'bucuresti';
$html = call_user_func($render, array());
check('1172 Bucharest items', preg_match_all('#<span class="smve-name">#', $html), 1172);
check('no raw < inside names', !preg_match('#<span class="smve-name">[^<]*<(?!/span)#', $html));
// Six shelter names carry a literal ampersand; they must come out encoded.
check('ampersands encoded', preg_match_all('#<span class="smve-name">[^<]*&amp;[^<]*</span>#', $html), 2);
check('no bare ampersand in names', !preg_match('#<span class="smve-name">[^<]*&(?!amp;|\#|lt;|gt;|quot;)#', $html));
check('every list item has a directions link',
    preg_match_all('#<span class="smve-name">#', $html),
    preg_match_all('#class="smve-navigate"#', $html));

echo "\n";
if ($failures) {
    printf("%d check(s) FAILED\n", $failures);
    exit(1);
}
echo "all checks passed\n";
