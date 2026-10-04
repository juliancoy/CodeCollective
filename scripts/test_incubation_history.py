import csv
import importlib.util
import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('history', ROOT / 'scripts/prepare_incubation_history.py')
HISTORY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HISTORY)


class HistoryTests(unittest.TestCase):
    def test_classification_preserves_boundary(self):
        self.assertEqual(HISTORY.classify('MLB Pitch, Hit, and Run', ''), 'excluded')
        self.assertEqual(HISTORY.classify('Pitch & Pints Block Party', ''), 'excluded')
        self.assertIsNone(HISTORY.classify('Accelerate drug discovery', ''))
        self.assertEqual(HISTORY.classify('Business Innovation Competition', ''), 'pitch_competition')
        self.assertEqual(HISTORY.classify('Maryland Student Venture Showcase', ''), 'demo_showcase')
        self.assertEqual(HISTORY.classify('Hacking AI Accelerators', 'AI startup founders'), 'program_workshop')

    def test_actual_inventory_and_portal_queue(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            subprocess.run([sys.executable, str(ROOT / 'scripts/prepare_incubation_history.py'), '--output', temp], check=True, capture_output=True)
            db = sqlite3.connect(directory / 'research.sqlite')
            self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
            self.assertFalse(db.execute('PRAGMA foreign_key_check').fetchall())
            names = {r[0] for r in db.execute('SELECT o.name FROM support_candidates s JOIN organizations o ON o.research_id=s.recipient_id')}
            self.assertEqual(names, {'AidRx','Behaivior','Compose Health','Embryoxite','Galen Health','Opal','Sloop','Valio'})
            self.assertFalse(db.execute("SELECT 1 FROM support_candidates s JOIN events e ON e.research_id=s.event_id WHERE e.title LIKE 'Pitch Labs%'").fetchall())
            identities = directory / 'identities.csv'
            with identities.open('w', newline='') as stream:
                writer = csv.writer(stream)
                writer.writerow(['research_id','portal_organization_id'])
                writer.writerows((rid, 'test-only-'+rid) for rid, in db.execute('SELECT research_id FROM organizations'))
            output = directory / 'queue.jsonl'
            subprocess.run([sys.executable, str(ROOT / 'scripts/prepare_incubation_portal_queue.py'), '--database', str(directory / 'research.sqlite'), '--identities', str(identities), '--output', str(output)], check=True, capture_output=True)
            queue = [json.loads(line) for line in output.read_text().splitlines()]
            self.assertEqual(len(queue), 8)
            self.assertTrue(all(item['tool']=='preview_organization_support' and 'confirm' not in item['arguments'] for item in queue))
            # Validate candidate payloads against the current upstream Zod schema.
            subprocess.run(['node','--import','tsx','--input-type=module','-e',
                "import {readFileSync} from 'node:fs'; import {supportSchema} from './src/organizationSupport.ts'; for(const line of readFileSync(process.argv[1],'utf8').trim().split('\\n')) supportSchema.parse(JSON.parse(line).arguments);",str(output)],
                cwd=ROOT.parent / 'OrgPortal/org-worker', check=True, capture_output=True)
            db.close()

    def test_portal_support_schema_is_flat_and_enforces_identity(self):
        db = sqlite3.connect(':memory:')
        db.execute('PRAGMA foreign_keys=ON')
        migrations = ROOT.parent / 'OrgPortal/org-worker/migrations'
        db.executescript((migrations / '0002_org_event_directories.sql').read_text())
        db.executescript((migrations / '0057_organization_support.sql').read_text())
        db.execute("INSERT INTO organizations(id,name,slug) VALUES('a','Accelerator','accelerator'),('b','Company','company')")
        insert = "INSERT INTO organization_support_records(id,from_organization_id,to_organization_id,from_label,to_label,support_kind,description,source_url,created_at) VALUES(?,?,?,?,?,'acceleration','Cohort','https://example.org','2025-06-05')"
        db.execute(insert, ('edge','a','b','Accelerator','Company'))
        self.assertEqual(db.execute('SELECT * FROM organization_support_edges').fetchall(), [('a','b')])
        with self.assertRaises(sqlite3.IntegrityError):
            db.execute(insert, ('self','a','a','Accelerator','Accelerator'))
        with self.assertRaises(sqlite3.IntegrityError):
            db.execute(insert, ('missing','a','missing','Accelerator','Missing'))
        db.execute("UPDATE organization_support_records SET status='voided',void_reason='Incorrect' WHERE id='edge'")
        self.assertEqual(db.execute('SELECT * FROM organization_support_edges').fetchall(), [])
        db.close()


if __name__ == '__main__':
    unittest.main()
