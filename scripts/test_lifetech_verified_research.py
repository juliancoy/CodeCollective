import csv
import importlib.util
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'baltimore/incubation_history/enrichment'
def rows(name):
 with (OUT/name).open() as f:return list(csv.DictReader(f))
class EvidenceIntegrity(unittest.TestCase):
 def test_references_and_complete_audit(self):
  entities={r['entity_id'] for r in rows('entities.csv')};sources={r['source_id'] for r in rows('verified_sources.csv')}
  coverage=rows('event_research_coverage.csv');self.assertEqual(len({r['event_id'] for r in coverage}),99)
  for r in rows('cohort_relationship_candidates.csv'):
   self.assertIn(r['recipient_entity_id'],entities);self.assertIn(r['supporter_entity_id'],entities);self.assertIn(r['source_id'],sources)
  for r in rows('verified_event_participants.csv'):
   self.assertIn(r['event_id'],{e['event_id'] for e in coverage});self.assertIn(r['entity_id'],entities)
 def test_awards_do_not_imply_payment_or_split_unknown_pool(self):
  awards=rows('published_awards.csv')
  self.assertTrue(all(r['status']=='published_award_not_payment' for r in awards))
  shared=[r for r in awards if 'shared' in r['award']];self.assertEqual(len(shared),2)
  self.assertTrue(all(r['amount']=='' for r in shared))
 def test_no_implicit_portal_identity_or_newventure_acceleration(self):
  self.assertTrue(all(not r['portal_org_id'] for r in rows('entities.csv')))
  relations=[r for r in rows('cohort_relationship_candidates.csv') if r['program']=='Maryland NEW VENTURE']
  self.assertEqual(len(relations),6);self.assertTrue(all(r['relationship_kind']=='program_participation' for r in relations))
if __name__=='__main__':unittest.main()
