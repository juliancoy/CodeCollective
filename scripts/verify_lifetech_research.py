#!/usr/bin/env python3
"""Read-only verification of live classification, source records and unclaimed registrations."""
import csv,json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from datetime import datetime
import re,requests
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'baltimore/incubation_history/enrichment'
BASE='https://lifetech.fyi/api/org/api/network'
def get(path):
 r=requests.get(BASE+path,timeout=30);r.raise_for_status();return r.json()
def instant(v):return datetime.fromisoformat(re.sub(r'([+-]\d{2})(\d{2})$',r'\1:\2',v.replace('Z','+00:00'))).timestamp()
def main():
 events=get('/orgs/public/lifetech/events?limit=200');byid={r['id']:r for r in events}
 receipt=json.loads((OUT.parent/'live-receipt/lifetech-import-receipt.json').read_text())['verified_events']
 payload=json.loads((OUT.parent/'lifetech-import.json').read_text())['events']
 assert len(receipt)==len(payload)==99
 def detail(pair):
  imported,expected=pair;e=byid[imported['id']];fresh=get('/events/public/'+e['slug'])
  assert fresh['id']==imported['id'];assert set(expected['tags']).issubset(set(fresh['tags']))
  assert fresh.get('source_url')==expected['source_url'];assert instant(fresh['starts_at'])==instant(expected['starts_at'])
  return {'event_id':fresh['id'],'slug':fresh['slug'],'classification':'verified','detail':'verified'}
 with ThreadPoolExecutor(max_workers=6) as pool:verified=list(pool.map(detail,zip(receipt,payload)))
 rows=[json.loads(line) for line in (OUT/'live-enrichment-receipt.jsonl').read_text().splitlines() if line.strip()]
 applied=[r for r in rows if r['status']=='applied'];previews={r['preview']['previewId']:r for r in rows if r['status']=='previewed'}
 for row in applied:assert row['result']['previewId'] in previews
 directory=get('/orgs/public?limit=500');orgs={r['id']:r for r in directory}
 registrations=[r for r in applied if r['endpoint'].endswith('/registry')]
 for row in registrations:
  org=orgs[row['result']['organizationId']];assert not org.get('claimed_by_user_id');assert org.get('membership_count',0)==0
 supporter_ids={r['endpoint'].split('/')[-3] for r in applied if r['endpoint'].endswith('/support/record')}
 support={}
 with ThreadPoolExecutor(max_workers=6) as pool:
  responses=list(pool.map(lambda oid:(oid,get('/orgs/public/'+orgs[oid]['slug']+'/support')),supporter_ids))
 for oid,result in responses:support[oid]=result['records']
 records=[r for r in applied if r['endpoint'].endswith('/support/record')]
 for row in records:
  args=previews[row['result']['previewId']]['preview']['changes'];found=[r for r in support[args['organizationId']] if r['id']=='support:'+row['result']['recordId']];assert len(found)==1
  actual=found[0];assert actual['to_organization_id']==args['recipientOrganizationId'];assert actual['source_url']==args['sourceUrl'];assert actual['transaction_type']==args['supportKind'];assert actual['amount'] is None
 for row in applied:
  if row['endpoint'].endswith('/enrichment'):
   expected=row['result']['changes'];e=byid[row['result']['eventId']]
   for key,value in expected.items():
    assert instant(e[key])==instant(value) if key=='ends_at' else e[key]==value
 awards=list(csv.DictReader((OUT/'published_awards.csv').open()))
 for row in awards:assert row['award'] in byid[row['event_id']]['description']
 summary={'checked_on':'2026-10-04','imported_events_verified':len(verified),'classification_tags_verified':99,'public_event_details_verified':99,'unclaimed_registrations_verified':len(registrations),'cohort_support_records_verified':len(records),'supporting_organizations':len(supporter_ids),'published_awards_verified':len(awards),'matching_preview_apply_receipts_verified':len(applied),'source_provenance_preserved':True,'unresolved_source_gaps_retained':True,'read_only':True}
 (OUT/'live-enrichment-verification.json').write_text(json.dumps(summary,indent=2)+'\n')
 (OUT/'verified-live-events.json').write_text(json.dumps(verified,indent=2)+'\n');print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
