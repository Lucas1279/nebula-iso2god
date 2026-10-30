#!/usr/bin/env python3
"""Build a reviewable Xbox 360 Redump inventory and exact XEX role catalogue.

The complete Redump inventory is kept separate from the runtime XEX crosswalk.
Redump title+disc joins are audit candidates only; only explicit Redump role
labels joined to a concrete Title ID + Media ID pair can set an automatic role.
Unlabelled or conflicting items stay unknown for the in-app role chooser.
"""
from __future__ import annotations
import csv
import json
import re
import zipfile
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CSV_PATH = ROOT / 'data/xbox360-gamelist.csv'
DAT_PATH = ROOT / 'data/redump-xbox360-dat.zip'
OUT_PATH = ROOT / 'data/disc_catalog.json'
INVENTORY_PATH = ROOT / 'data/redump_inventory.json'
REPORT_PATH = ROOT / 'data/disc_catalog_review.md'

DISC_RE = re.compile(r'\b(?:disc|disk|dvd)\s*[-_ ]?\s*(\d+)\b', re.I)
PAREN_RE = re.compile(r'\(([^)]*)\)')
INSTALL_LABEL = re.compile(r'^(?:content\s+install(?:ation)?(?:\s+disc)?|install(?:ation)?(?:\s+disc)?|install[- ]multiplayer|additional content packs install disc)$', re.I)
PLAYABLE_LABEL = re.compile(r'^(?:game disc|play disc|game|play|single[- ]play|red dead redemption single player|undead nightmare and multiplayer)$', re.I)


def norm_title(value: str) -> str:
    """Conservative lexical normalization; never performs fuzzy matching."""
    value = PAREN_RE.sub(' ', value)
    value = re.sub(r'\b(?:disc|disk|dvd)\s*[-_ ]?\s*\d+\b', ' ', value, flags=re.I)
    return re.sub(r'[^a-z0-9]+', '', value.casefold())


def detect_role(name: str) -> tuple[str | None, int | None, str | None]:
    disc_nums = {int(m.group(1)) for m in DISC_RE.finditer(name)}
    disc = next(iter(disc_nums)) if len(disc_nums) == 1 else None
    parts = [part.strip() for part in PAREN_RE.findall(name)]
    role = evidence = None
    if disc is not None:
        disc_part = next((i for i, part in enumerate(parts) if DISC_RE.search(part)), None)
        if disc_part is not None and disc_part + 1 < len(parts):
            evidence = parts[disc_part + 1]
            if INSTALL_LABEL.fullmatch(evidence):
                role = 'install'
            elif PLAYABLE_LABEL.fullmatch(evidence):
                role = 'playable'
            else:
                evidence = None
    # Explicit single-disc installer naming is accepted for identity in the
    # inventory, but without a disc number it cannot be joined to an XEX role.
    if role is None and re.search(r'\binstallation disc\b\s*$', name, re.I):
        role, evidence = 'install', 'Installation Disc'
    return role, disc, evidence


def read_csv_rows():
    rows = []
    with CSV_PATH.open(encoding='utf-8-sig', newline='') as fh:
        for row in csv.DictReader(fh):
            title_id = (row.get('Title ID') or '').strip().upper()
            media_id = (row.get('Media ID') or '').strip().upper()
            if not re.fullmatch(r'[0-9A-F]{8}', title_id):
                continue
            if not re.fullmatch(r'[0-9A-F]{8}', media_id):
                media_id = ''
            game = (row.get('Game Name') or '').strip()
            nums = {int(m.group(1)) for m in DISC_RE.finditer(game)}
            rows.append({
                'titleId': title_id,
                'mediaId': media_id,
                'name': game,
                'region': (row.get('Region') or '').strip(),
                'discNumber': next(iter(nums)) if len(nums) == 1 else None,
            })
    return rows


def read_redump_inventory():
    with zipfile.ZipFile(DAT_PATH) as archive:
        dat_name = next(n for n in archive.namelist() if n.lower().endswith('.dat'))
        xml = archive.read(dat_name)
    root = ET.fromstring(xml)
    version = (root.findtext('./header/date') or root.findtext('./header/version') or '').strip()
    entries = []
    for game in root.findall('./game'):
        name = (game.get('name') or '').strip()
        role, disc, evidence = detect_role(name)
        rom = game.find('./rom')
        entry = {'name': name}
        if disc is not None:
            entry['discNumber'] = disc
        if role:
            entry['role'] = role
            entry['roleEvidence'] = evidence
        if rom is not None:
            if rom.get('name'):
                entry['fileName'] = rom.get('name')
            for source, target in [('size', 'size'), ('crc', 'crc32'), ('md5', 'md5'), ('sha1', 'sha1')]:
                if rom.get(source):
                    entry[target] = rom.get(source).lower() if target in ('crc32', 'md5', 'sha1') else int(rom.get(source))
        entries.append(entry)
    entries.sort(key=lambda x: (x['name'].casefold(), x.get('sha1', '')))
    return entries, version


def main():
    rows = read_csv_rows()
    inventory, dat_version = read_redump_inventory()
    redump_entry_count = len(inventory)

    identities: dict[str, dict] = {}
    collisions = []
    for row in rows:
        if not row['mediaId']:
            continue
        key = row['titleId'] + ':' + row['mediaId']
        previous = identities.get(key)
        if previous is None:
            identities[key] = {**row, 'regions': [row['region']] if row['region'] else []}
        else:
            if norm_title(previous['name']) != norm_title(row['name']):
                collisions.append((key, previous['name'], row['name']))
            if row['region'] and row['region'] not in previous['regions']:
                previous['regions'].append(row['region'])

    by_title_disc = defaultdict(list)
    for row in rows:
        if row['mediaId'] and row['discNumber']:
            by_title_disc[(norm_title(row['name']), row['discNumber'])].append(row)

    # Attach candidate keys for audit only. They do not influence runtime role
    # decisions unless the Redump record has one explicit role label.
    joins = defaultdict(set)
    matched_source = defaultdict(list)
    unmatched = []
    candidate_entry_count = 0
    candidate_identity_keys = set()
    role_labeled_entries = 0
    for entry in inventory:
        role = entry.get('role')
        disc = entry.get('discNumber')
        candidate_rows = by_title_disc.get((norm_title(entry['name']), disc), []) if disc else []
        keys = sorted({r['titleId'] + ':' + r['mediaId'] for r in candidate_rows})
        if keys:
            entry['candidateIdentityKeys'] = keys
            candidate_entry_count += 1
            candidate_identity_keys.update(keys)
        if not role:
            continue
        role_labeled_entries += 1
        if not disc:
            unmatched.append((entry['name'], role, 'no explicit disc number'))
            continue
        if not keys:
            unmatched.append((entry['name'], role, 'no exact title/disc crosswalk'))
            continue
        for key in keys:
            joins[key].add(role)
            matched_source[key].append(entry['name'])

    conflicts = []
    for key, roles in joins.items():
        record = identities.get(key)
        if not record:
            continue
        if len(roles) == 1:
            record['role'] = next(iter(roles))
            record['roleSource'] = 'Redump role label; exact normalized title + disc-number crosswalk'
        else:
            record['role'] = 'unknown'
            conflicts.append((key, record['name'], sorted(roles), matched_source[key]))
            record['roleSource'] = 'conflicting Redump labels; manual chooser required'

    ordered = {key: identities[key] for key in sorted(identities)}
    role_count = sum(r.get('role') in ('install', 'playable') for r in ordered.values())
    source_redump = {
        'name': 'Redump Xbox 360 DAT via redump.info',
        'url': 'https://redump.info/datfile/XBOX360',
        'archive': 'redump-xbox360-dat.zip',
        'datVersion': dat_version,
        'entryCount': redump_entry_count,
    }
    source_gamelist = {
        'name': 'IronRingX Xbox 360 game list',
        'url': 'https://github.com/IronRingX/xbox360-gamelist',
        'file': 'xbox360-gamelist.csv',
        'upstreamCommit': '32aae7abeff7ed47969786309739444eb5397731',
    }
    meta = {
        'schemaVersion': 1,
        'generatedFrom': [source_redump, source_gamelist],
        'identityRecordCount': len(ordered),
        'distinctTitleIdCount': len({r['titleId'] for r in ordered.values()}),
        'explicitRoleRecords': role_count,
        'roleConflicts': len(conflicts),
        'redumpInventoryFile': 'redump_inventory.json',
        'note': 'The full Redump inventory is separate. Candidate title+disc joins are for audit; runtime identity uses exact XEX Title ID + Media ID. A missing role stays unknown; never infer from disc number alone.',
        'records': ordered,
    }
    OUT_PATH.write_text(json.dumps(meta, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')

    inventory_doc = {
        'schemaVersion': 1,
        'generatedFrom': source_redump,
        'entryCount': redump_entry_count,
        'explicitRoleLabelEntryCount': role_labeled_entries,
        'entriesWithTitleDiscCandidates': candidate_entry_count,
        'distinctCandidateIdentityKeys': len(candidate_identity_keys),
        'note': 'Candidate identity keys are audit leads from exact normalized title+disc-number joins, not conclusive identity mappings or runtime matches. Explicit Redump role labels are separately reviewed and joined to exact XEX Title ID + Media ID records; runtime selection still requires that exact pair.',
        'entries': inventory,
    }
    INVENTORY_PATH.write_text(json.dumps(inventory_doc, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')

    role_records = [r for r in ordered.values() if r.get('role') in ('install', 'playable')]
    report = [
        '# Xbox 360 disc catalogue build review', '',
        f'- Redump DAT snapshot: {dat_version}; complete inventory entries: {redump_entry_count}.',
        f'- CSV source rows parsed: {len(rows)}; exact Title ID + Media ID identities: {len(ordered)} across {meta["distinctTitleIdCount"]} Title IDs.',
        f'- Full inventory entries with title+disc candidate joins (audit only): {candidate_entry_count}; distinct candidate identity keys: {len(candidate_identity_keys)}.',
        f'- Redump entries with explicit role terms: {role_labeled_entries}.',
        f'- Automatic exact role records: {role_count}; conflicting role identities: {len(conflicts)}.',
        f'- Explicitly labeled Redump entries not joined: {len(unmatched)}.',
        '', '## Automatic role assignments (review before shipping)', '',
        '| Title ID | Media ID | Game-list name | Region(s) | Disc | Role | Redump label(s) |',
        '|---|---|---|---|---:|---|---|',
    ]
    for key, rec in ordered.items():
        if rec.get('role') in ('install', 'playable'):
            role_names = '; '.join(sorted(set(matched_source[key])))
            report.append(f'| {rec["titleId"]} | {rec["mediaId"]} | {rec["name"]} | {", ".join(rec["regions"])} | {rec.get("discNumber") or "?"} | {rec["role"]} | {role_names} |')
    report += ['', '## Conflicts (must remain unknown)', '', '| Key | Name | Candidate roles | Source labels |', '|---|---|---|---|']
    for key, name, roles, sources in conflicts:
        report.append(f'| {key} | {name} | {", ".join(roles)} | {"; ".join(sorted(set(sources)))} |')
    report += ['', '## Unmatched Redump role-labeled entries', '', '| Label | Role | Reason |', '|---|---|---|']
    for name, role, reason in unmatched:
        report.append(f'| {name} | {role} | {reason} |')
    REPORT_PATH.write_text('\n'.join(report) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in meta.items() if k != 'records'}, indent=2))
    print(json.dumps({k: v for k, v in inventory_doc.items() if k != 'entries'}, indent=2))
    print('Review:', REPORT_PATH)

if __name__ == '__main__':
    main()
