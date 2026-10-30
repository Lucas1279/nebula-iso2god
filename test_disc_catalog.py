import base64
import io
import json
import subprocess
import sys
import tarfile
import unittest
import zipfile
from pathlib import Path

from build_disc_catalog import detect_role

ROOT = Path(__file__).resolve().parent
CATALOG_PATH = ROOT / 'data/disc_catalog.json'


class DiscCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = json.loads(CATALOG_PATH.read_text(encoding='utf-8'))
        cls.records = cls.catalog['records']

    def test_catalogue_has_exact_keyed_identity_records(self):
        self.assertEqual(self.catalog['identityRecordCount'], len(self.records))
        self.assertGreaterEqual(len(self.records), 2500)
        for key, record in self.records.items():
            self.assertRegex(key, r'^[0-9A-F]{8}:[0-9A-F]{8}$')
            self.assertEqual(key, record['titleId'] + ':' + record['mediaId'])
            self.assertTrue(record['name'])

    def test_only_reviewed_explicit_roles_are_shipped(self):
        roles = [r.get('role') for r in self.records.values() if r.get('role')]
        self.assertTrue(set(roles) <= {'install', 'playable', 'unknown'})
        self.assertEqual(self.catalog['explicitRoleRecords'], sum(x in ('install', 'playable') for x in roles))
        self.assertEqual(self.catalog['roleConflicts'], sum(x == 'unknown' for x in roles))
        self.assertEqual(self.catalog['explicitRoleRecords'], 31)
        self.assertEqual(self.catalog['roleConflicts'], 0)

    def test_known_role_examples_and_cross_region_variants(self):
        # CoD Ghosts exact Media IDs cover the Japanese DAT role across distinct
        # region rows; role resolution at runtime still uses the exact pair.
        expected = {
            '415608FC:3CC5A411': 'playable',
            '415608FC:5C90116D': 'playable',
            '415608FC:56374F6E': 'install',
            '415608FC:6E412B07': 'install',
            '4D53084D:1235FA6A': 'install',  # Forza Motorsport 3 Disc 2
            '545408A7:0C48794E': 'install',  # GTA V Disc 1
            '555308B7:54A95DF1': 'playable',  # Watch_Dogs Disc 2
        }
        for key, role in expected.items():
            with self.subTest(key=key):
                self.assertEqual(self.records[key]['role'], role)

    def test_nonrole_identity_does_not_guess(self):
        # A well-known single-disc identity is recognized by Media ID but stays
        # role-unknown unless a source actually labels its disc role.
        self.assertNotIn('role', self.records['315A07D1:3AC236C5'])

    def test_generic_disc_number_and_goty_title_do_not_imply_playable(self):
        self.assertEqual(detect_role('Dishonored - Game of the Year Edition (Disc 2)'), (None, 2))
        self.assertEqual(detect_role('Example Game (Disc 2)'), (None, 2))
        self.assertEqual(detect_role('Example Game (Disc 2) (Install Disc)'), ('install', 2))

    def test_review_report_documents_unmatched_and_assignment_rows(self):
        report = (ROOT / 'data/disc_catalog_review.md').read_text(encoding='utf-8')
        self.assertIn('Automatic role assignments', report)
        self.assertIn('Unmatched Redump role-labeled entries', report)
        self.assertIn('415608FC | 3CC5A411', report)

    def test_regeneration_is_deterministic(self):
        before_json = CATALOG_PATH.read_bytes()
        before_report = (ROOT / 'data/disc_catalog_review.md').read_bytes()
        subprocess.run([sys.executable, str(ROOT / 'build_disc_catalog.py')], check=True, capture_output=True, text=True)
        self.assertEqual(CATALOG_PATH.read_bytes(), before_json)
        self.assertEqual((ROOT / 'data/disc_catalog_review.md').read_bytes(), before_report)

    def test_all_runtime_packages_ship_the_catalogue(self):
        expected = {
            'Nebula-ISO2GOD-Windows-Helper.zip': 'Nebula ISO2GOD Windows Helper/data/disc_catalog.json',
            'nebula-iso2god-timeout-fix.zip': 'NebulaISO2GOD-Mac-Timeout-ClickRun/data/disc_catalog.json',
            'NebulaISO2GOD-Full-GitHub-Pages-Build.zip': 'data/disc_catalog.json',
        }
        for archive, member in expected.items():
            with self.subTest(archive=archive), zipfile.ZipFile(ROOT / archive) as zf:
                self.assertIn(member, zf.namelist())
                self.assertEqual(json.loads(zf.read(member))['identityRecordCount'], 2577)

    def test_one_file_mac_launcher_embeds_catalogue(self):
        with zipfile.ZipFile(ROOT / 'Nebula-ISO2GOD-One-File-Fixed.zip') as zf:
            script = zf.read('Nebula ISO2GOD.command').decode('utf-8')
        lines = script.splitlines()
        start = next(i for i, line in enumerate(lines) if line.endswith("<<'NEBULA_EMBEDDED_DATA'")) + 1
        end = lines.index('NEBULA_EMBEDDED_DATA', start)
        payload = base64.b64decode(''.join(lines[start:end]))
        with tarfile.open(fileobj=io.BytesIO(payload), mode='r:gz') as tf:
            self.assertIn('data/disc_catalog.json', tf.getnames())
            embedded = json.load(tf.extractfile('data/disc_catalog.json'))
            self.assertEqual(embedded['identityRecordCount'], 2577)


if __name__ == '__main__':
    unittest.main()
