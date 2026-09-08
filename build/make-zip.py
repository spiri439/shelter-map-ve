#!/usr/bin/env python3
"""Package the plugin into dist/shelter-map-ve.zip, ready to upload.

Everything at the repo root is the plugin; the paths listed in .distignore are
development-only and stay out. Inside the archive every file sits under a
shelter-map-ve/ directory, which is what WordPress expects.
"""

import os
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SLUG = 'shelter-map-ve'
DIST = os.path.join(ROOT, 'dist', '%s.zip' % SLUG)

# Exactly what belongs at the plugin root. Anything else is a mistake: a stray
# Plugin Check export once rode along into a release this way, and Plugin Check
# then flagged its own report as an unexpected file in the plugin.
ALLOWED_ROOT_FILES = {
    'shelter-map.php',
    'shelter-map.js',
    'shelter-map.css',
    'readme.txt',
    'LICENSE',
    'pin-shelter.png',
}
ALLOWED_ROOT_DIRS = {'languages', 'vendor', 'data'}


def excluded():
    path = os.path.join(ROOT, '.distignore')
    names = set()
    if os.path.exists(path):
        with open(path, encoding='utf-8') as fh:
            for line in fh:
                line = line.strip()
                if line and not line.startswith('#'):
                    names.add(line)
    return names


def verify(collected):
    """Refuse to package anything unexpected at the plugin root."""
    problems = []
    for rel in collected:
        parts = rel.replace(os.sep, '/').split('/')
        if len(parts) == 1:
            if parts[0] not in ALLOWED_ROOT_FILES:
                problems.append('unexpected file at plugin root: %s' % parts[0])
        elif parts[0] not in ALLOWED_ROOT_DIRS:
            problems.append('unexpected directory at plugin root: %s/' % parts[0])
    missing = ALLOWED_ROOT_FILES - set(collected)
    problems += ['missing from plugin root: %s' % name for name in sorted(missing)]
    if problems:
        raise SystemExit('Refusing to package.\n  ' + '\n  '.join(sorted(set(problems)))
                         + '\nAdd it to .distignore, or move it out of the plugin root.')


def main():
    skip = excluded()
    os.makedirs(os.path.dirname(DIST), exist_ok=True)

    collected = []
    for base, dirs, files in os.walk(ROOT):
        rel_base = os.path.relpath(base, ROOT)
        if rel_base == '.':
            rel_base = ''
            dirs[:] = sorted(d for d in dirs if d not in skip)
        else:
            dirs[:] = sorted(dirs)
        for name in sorted(files):
            rel = os.path.join(rel_base, name) if rel_base else name
            if rel.replace(os.sep, '/').split('/')[0] in skip or rel in skip:
                continue
            collected.append(rel)

    verify(collected)

    with zipfile.ZipFile(DIST, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for rel in collected:
            zf.write(os.path.join(ROOT, rel),
                     '%s/%s' % (SLUG, rel.replace(os.sep, '/')))

    raw = sum(os.path.getsize(os.path.join(ROOT, r)) for r in collected)
    print('%s' % os.path.relpath(DIST, ROOT))
    print('  files: %d | uncompressed: %.0f KB | archive: %.0f KB' % (
        len(collected), raw / 1024, os.path.getsize(DIST) / 1024))
    for rel in collected:
        if '/' not in rel.replace(os.sep, '/'):
            print('  root: %s' % rel)


if __name__ == '__main__':
    main()
