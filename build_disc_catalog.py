#!/usr/bin/env python3
"""Reproducibly build the offline Xbox 360 disc identity/role catalogue.

Identity comes from IronRingX/xbox360-gamelist; explicit role labels come only
from the Redump DAT. Fuzzy joins are deliberately not used: title + disc number
must agree after conservative normalization. Ambiguous role conflicts are emitted
as unknown and are never resolved by guessing.
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
REPORT_PATH = ROOT / 'data/disc_catalog_review.md'

DISC_RE = re.compile(r'\b(?:disc|disk|dvd)\s*[-_ ]?\s*(\d+)\b', re.I)
PAREN_RE = re.compile(r'\(([^)]*)\)')
# Interpret role words only in the annotation immediately after an explicit
# disc number. This avoids false hits such as "Game of the Year" in a title,
# or generic Disc 2 labels that do not specify whether the disc is playable.
INSTALL_LABEL = re.compile(r'^(?:content\s+install(?:ation)?(?:\s+disc)?|install(?:ation)?(?:\s+disc)?|install[- ]multiplayer|additional content packs install disc)$', re.I)
PLAYABLE_LABEL = re.compile(r'^(?:game disc|play disc|game|play|single[- ]play|red dead redemption single player|undead nightmare and multiplayer)$', re.I)


def norm_title(value: str) -> str:
    # Keep only the title's lexical core. Parenthetical region, revision, disc,
    # language, and edition annotations are not used as independent evidence.
    value = PAREN_RE.sub(' ', value)
    value = re.sub(r'\b(?:disc|disk|dvd)\s*[-_ ]?\s*\d+\b', ' ', value, flags=re.I)
    value = re.sub(r'[^a-z0-9]+', '', value.casefold())
    return value


def detect_role(name: str) -> tuple[str | None, int | None]:
    disc_nums = {int(m.group(1)) for m in DISC_RE.finditer(name)}
    disc = next(iter(disc_nums)) if len(disc_nums) == 1 else None
    parts = [part.strip() for part in PAREN_RE.findall(name)]
    role = None
    if disc is not None:
        disc_part = next((i for i, part in enumerate(parts) if DISC_RE.search(part)), None)
        if disc_part is not None and disc_part + 1 < len(parts):
            label = parts[disc_part + 1]
            if INSTALL_LABEL.fullmatch(label):
                role = 'install'
            elif PLAYABLE_LABEL.fullmatch(label):
                role = 'playable'
    # Some single-disc installation media are named as such without a
    # (Disc N) annotation. Accept that explicit suffix only for install media.
    if role is None and re.search(r'\binstallation disc\b\s*$', name, re.I):
        role = 'install'
    return role, disc


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
                'titleId': title_id, 'mediaId': media_id,
                'name': game, 'region': (row.get('Region') or '').strip(),
                'discNumber': next(iter(nums)) if len(nums) == 1 else None,
            })
    return rows


def read_redump_games():
    with zipfile.ZipFile(DAT_PATH) as archive:
        dat_name = next(n for n in archive.namelist() if n.lower().endswith('.dat'))
        xml = archive.read(dat_name)
    root = ET.fromstring(xml)
    games = []
    for game in root.findall('.//game'):
        name = game.get('name') or ''
        role, disc = detect_role(name)
        if role:
            games.append({'name': name, 'role': role, 'discNumber': disc})
    return games


def main():
    rows = read_csv_rows()
    games = read_redump_games()
    # Deduplicate exact XEX identity keys, retaining all source variants.
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

    # Conservative title + disc-number join from explicitly labeled Redump names.
    # The crosswalk may have multiple regional Media IDs; retain the role only
    # when every joined release label for that exact XEX identity agrees.
    joins = defaultdict(set)
    matched_source = defaultdict(list)
    unmatched = []
    by_title_disc = defaultdict(list)
    for row in rows:
        if row['mediaId'] and row['discNumber']:
            by_title_disc[(norm_title(row['name']), row['discNumber'])].append(row)
    for game in games:
        if not game['discNumber']:
            unmatched.append((game['name'], game['role'], 'no explicit disc number'))
            continue
        title_key = norm_title(game['name'])
        # Redump game's title normalization strips all parenthetical metadata;
        # game-list suffixes are treated equivalently.
        candidates = by_title_disc.get((title_key, game['discNumber']), [])
        if not candidates:
            unmatched.append((game['name'], game['role'], 'no exact title/disc crosswalk'))
            continue
        for row in candidates:
            key = row['titleId'] + ':' + row['mediaId']
            joins[key].add(game['role'])
            matched_source[key].append(game['name'])

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

    # Stable output and explicit provenance/limitations.
    ordered = {key: identities[key] for key in sorted(identities)}
    meta = {
        'schemaVersion': 1,
        'generatedFrom': [
            {'name': 'Redump Xbox 360 DAT', 'url': 'http://redump.org/datfile/xbox360/', 'archive': 'redump-xbox360-dat.zip', 'datVersion': '2026-06-15'},
            {'name': 'IronRingX Xbox 360 game list', 'url': 'https://github.com/IronRingX/xbox360-gamelist', 'file': 'xbox360-gamelist.csv', 'upstreamCommit': '32aae7abeff7ed47969786309739444eb5397731'},
        ],
        'identityRecordCount': len(ordered),
        'recordsWithMediaId': len(ordered),
        'explicitRoleRecords': sum(r.get('role') in ('install', 'playable') for r in ordered.values()),
        'roleConflicts': len(conflicts),
        'note': 'Offline crosswalk, not universal coverage. A missing role means unknown; never infer from disc number alone. Exact XEX Title ID + Media ID matches are used at runtime.',
        'records': ordered,
    }
    OUT_PATH.write_text(json.dumps(meta, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')

    # Human review artifact for every automatically proposed role assignment.
    report = [
        '# Xbox 360 disc catalogue build review', '',
        f'- CSV source rows parsed: {len(rows)}; exact Title ID + Media ID records: {len(ordered)}.',
        f'- Redump games with explicit role terms: {len(games)}.',
        f'- Automatically joined role records: {meta["explicitRoleRecords"]}; conflicting role identities: {len(conflicts)}.',
        f'- Labeled Redump entries not joined: {len(unmatched)}.',
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
    print('Review:', REPORT_PATH)

if __name__ == '__main__':
    main()
