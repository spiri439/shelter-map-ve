#!/usr/bin/env python3
"""Write languages/shelter-map-ve-ro_RO.po and .mo.

There is no msgfmt in this environment, so the .mo is assembled directly. The
format is GNU gettext, little-endian: a 28-byte header, then a key table and a
value table of 8 bytes per entry, then the strings themselves.

Romanian has three plural forms, and from 20 upwards the noun takes "de"
("4.538 de adăposturi"), which is why the third form exists at all.
"""

import os
import struct

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEST = os.path.join(ROOT, 'languages')
DOMAIN = 'shelter-map-ve'

HEADER = (
    'Project-Id-Version: Vlad Enterprises Shelter Map 1.0.0\n'
    'Report-Msgid-Bugs-To: https://github.com/spiri439/shelter-map-ve/issues\n'
    'Last-Translator: nextdoorentertainment\n'
    'Language-Team: Romanian\n'
    'Language: ro\n'
    'MIME-Version: 1.0\n'
    'Content-Type: text/plain; charset=UTF-8\n'
    'Content-Transfer-Encoding: 8bit\n'
    'Plural-Forms: nplurals=3; plural=(n==1 ? 0 : (n==0 || (n%100>0 && n%100<20)) ? 1 : 2);\n'
    'X-Domain: shelter-map-ve\n'
)

SINGULAR = [
    ('The map could not be loaded. Please reload the page.',
     'Harta nu a putut fi încărcată. Reîncarcă pagina, te rugăm.'),
    ('Directions', 'Navighează'),
    ('Sector %s', 'Sectorul %s'),
    ('%s away from you', 'la %s de tine'),
    ('Nearest shelter to you', 'Cel mai apropiat adăpost de tine'),
    ('Your position', 'Poziția ta'),
    ('Finding your position…', 'Se caută poziția ta…'),
    ('Could not determine your position. Check that location access is allowed.',
     'Nu am putut afla poziția ta. Verifică dacă ai permis accesul la locație.'),
    ('No shelter matches your search.', 'Niciun adăpost nu corespunde căutării.'),
    ('1 shelter', '1 adăpost'),
    ('%s shelters', '%s adăposturi'),
    ('All counties', 'Toate județele'),
    ('All sectors', 'Toate sectoarele'),
    ('County', 'Județ'),
    ('Sector', 'Sector'),
    ('Search by address or name', 'Caută după adresă sau denumire'),
    ('e.g. Main Street', 'ex. Bd. Timișoara'),
    ('Nearest to me', 'Cel mai apropiat de mine'),
    ('Loading the map…', 'Se încarcă harta…'),
    ('Civil protection shelter map', 'Harta adăposturilor de protecție civilă'),
    ('Shelters in %1$s (%2$s)', 'Adăposturi în %1$s (%2$s)'),
    ('← All counties', '← Toate județele'),
    ('Shelters by county', 'Adăposturi pe județe'),
]

PLURAL = [
    (('%s civil protection shelter', '%s civil protection shelters'),
     ('%s adăpost de protecție civilă',
      '%s adăposturi de protecție civilă',
      '%s de adăposturi de protecție civilă')),
]


def po_escape(value):
    return (value.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n'))


def write_po(path):
    lines = ['msgid ""', 'msgstr ""']
    for line in HEADER.rstrip('\n').split('\n'):
        lines.append('"%s\\n"' % po_escape(line))
    lines.append('')
    for source, target in SINGULAR:
        lines += ['msgid "%s"' % po_escape(source),
                  'msgstr "%s"' % po_escape(target), '']
    for (one, many), forms in PLURAL:
        lines += ['msgid "%s"' % po_escape(one),
                  'msgid_plural "%s"' % po_escape(many)]
        for i, form in enumerate(forms):
            lines.append('msgstr[%d] "%s"' % (i, po_escape(form)))
        lines.append('')
    with open(path, 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(lines))


def write_mo(path):
    entries = [('', HEADER)] + list(SINGULAR)
    for (one, many), forms in PLURAL:
        entries.append((one + '\x00' + many, '\x00'.join(forms)))
    entries.sort(key=lambda kv: kv[0].encode('utf-8'))

    keys = [k.encode('utf-8') for k, _ in entries]
    values = [v.encode('utf-8') for _, v in entries]
    count = len(entries)

    key_table_offset = 28
    value_table_offset = key_table_offset + 8 * count
    strings_offset = value_table_offset + 8 * count

    key_table, value_table, blob = [], [], b''
    cursor = strings_offset
    for key in keys:
        key_table.append((len(key), cursor))
        blob += key + b'\x00'
        cursor += len(key) + 1
    for value in values:
        value_table.append((len(value), cursor))
        blob += value + b'\x00'
        cursor += len(value) + 1

    mo = struct.pack('<Iiiiiii', 0x950412de, 0, count,
                     key_table_offset, value_table_offset, 0, 0)
    for length, offset in key_table + value_table:
        mo += struct.pack('<ii', length, offset)
    mo += blob

    with open(path, 'wb') as fh:
        fh.write(mo)
    return len(mo)


def main():
    os.makedirs(DEST, exist_ok=True)
    po = os.path.join(DEST, '%s-ro_RO.po' % DOMAIN)
    mo = os.path.join(DEST, '%s-ro_RO.mo' % DOMAIN)
    write_po(po)
    size = write_mo(mo)
    print('%s: %d B' % (os.path.basename(po), os.path.getsize(po)))
    print('%s: %d B' % (os.path.basename(mo), size))

    # Read it back, so a broken write cannot ship.
    import gettext
    with open(mo, 'rb') as fh:
        catalog = gettext.GNUTranslations(fh)
    assert catalog.gettext('County') == 'Județ', 'translation did not load'
    assert catalog.ngettext('%s civil protection shelter',
                            '%s civil protection shelters', 4538) \
        == '%s de adăposturi de protecție civilă', 'wrong plural form'
    print('verified: singular and 20+ plural both resolve')


if __name__ == '__main__':
    main()
