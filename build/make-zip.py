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
