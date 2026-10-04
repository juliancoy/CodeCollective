#!/usr/bin/env python3
"""Match evidence to public portal records and prepare permission-checked support calls."""
import csv
from datetime import datetime
import hashlib
import json
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import requests
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'baltimore/incubation_history/enrichment'
BASE='https://lifetech.fyi/api/org/api/network'
def read(name):
 with (OUT/name).open() as f:return list(csv.DictReader(f))
def write(name,rows,cols):
 with (OUT/name).open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=cols);w.writeheader();w.writerows(rows)
def norm(name):return re.sub(r'[^a-z0-9]','',name.casefold())
def main():
 entities=read('entities.csv');directory=json.loads((OUT/('identity-directory-snapshot.json' if (OUT/'identity-directory-snapshot.json').exists() else 'live-organizations.json')).read_text())
 def lookup(e):
  if any(norm(o['name'])==norm(e['name']) for o in directory):return []
  r=requests.get(BASE+'/orgs/public',params={'q':e['name'],'limit':100},timeout=30);r.raise_for_status();return r.json()
 with ThreadPoolExecutor(max_workers=6) as pool:
  for found in pool.map(lookup,entities):directory.extend(found)
 by_id={o['id']:o for o in directory};directory=list(by_id.values())
 (OUT/'identity-directory-snapshot.json').write_text(json.dumps(directory,indent=2)+'\n')
 matched={};identities=[]
 for e in entities:
  exact=[o for o in directory if norm(o['name'])==norm(e['name'])]
  status='exact_name_requires_identity_review' if len(exact)==1 else 'ambiguous' if exact else 'not_found'
  if len(exact)==1:matched[e['entity_id']]=exact[0]
  identities.append(dict(entity_id=e['entity_id'],research_name=e['name'],portal_organization_id=exact[0]['id'] if len(exact)==1 else '',portal_name=exact[0]['name'] if len(exact)==1 else '',status=status))
 write('portal_identity_matches.csv',identities,list(identities[0]))
 sources={r['source_id']:r['url'] for r in read('verified_sources.csv')}
 dates={'2025 spring':'2025-06-05','2025 fall':'2025-12-04','II':'2026-01-27','III':'2026-07-16','2026 inaugural':'2026-03-17','2026':'2026-03-19','6':'2026-05-11'}
 queue=[];pending=[]
 for r in read('cohort_relationship_candidates.csv'):
  giver=matched.get(r['supporter_entity_id']);recipient=matched.get(r['recipient_entity_id'])
  reasons=[]
  if not giver:reasons.append('supporter_identity_unresolved')
  if not recipient:reasons.append('recipient_identity_unresolved')
  if r['relationship_kind']=='program_participation':reasons.append('relationship_kind_requires_review')
  key=hashlib.sha256(json.dumps(r,sort_keys=True).encode()).hexdigest()[:24]
  if reasons:
   pending.append(dict(candidate_id=key,**r,blocking_reasons=';'.join(reasons)));continue
  args=dict(organizationId=giver['id'],recipientOrganizationId=recipient['id'],supportKind=r['relationship_kind'],description=f"{r['program']} cohort {r['cohort']}",occurredAt=dates[r['cohort']],sourceUrl=sources[r['source_id']],evidence=f"Primary publisher names {recipient['name']} as a member of {r['program']} cohort {r['cohort']}.",notes='Date is associated showcase date, not support start. Public historical evidence; no monetary amount or ownership claim.',status='reported')
  queue.append(dict(candidate_id=key,endpoint=f"/api/network/orgs/{giver['id']}/support/record",arguments=args,identity_review_required=True))
 (OUT/'support-apply-queue.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in queue))
 write('pending_support_candidates.csv',pending,['candidate_id',*read('cohort_relationship_candidates.csv')[0].keys(),'blocking_reasons'])
 manifest=json.loads((OUT.parent/'lifetech-import.manifest.json').read_text())
 if isinstance(manifest,dict):print('manifest keys',list(manifest));manifest=manifest.get('events',manifest.get('records',[]))
 tags={'pitch_competition':'Pitch Competition','demo_showcase':'Demo Day / Showcase','incubation_acceleration':'Incubation / Acceleration','pitch_practice':'Pitch Practice','description_match':'Startup Event','program_workshop':'Accelerator Workshop'}
 events=json.loads((OUT/'live-events.json').read_text());checks=[]
 payload=json.loads((OUT.parent/'lifetech-import.json').read_text())['events']
 by_key={e['ingest_key']:e for e in payload}
 for row in manifest:
  def instant(value):
   value=re.sub(r'([+-]\d{2})(\d{2})$',r'\1:\2',value.replace('Z','+00:00'))
   return datetime.fromisoformat(value).timestamp()
  item=by_key[row['ingest_key']]
  found=[e for e in events if e.get('source_url')==item['source_url'] and instant(e['starts_at'])==instant(item['starts_at'])]
  expected=tags[row['category']]
  checks.append(dict(title=row['title'],category=row['category'],expected_tag=expected,event_id=found[0]['id'] if len(found)==1 else '',status='verified' if len(found)==1 and expected in found[0]['tags'] and 'LifeTech' in found[0]['tags'] else 'needs_review'))
 write('live_classification_audit.csv',checks,['title','category','expected_tag','event_id','status'])
 summary=dict(exact_name_matches=len(matched),research_entities=len(entities),support_calls_prepared=len(queue),support_candidates_pending=len(pending),classification_verified=sum(r['status']=='verified' for r in checks),classification_review=sum(r['status']!='verified' for r in checks),live_writes=0,write_blocker='Authenticated .env.pidp identity denied manage permission for checked supporting organizations (HTTP 403).' )
 (OUT/'apply-preparation-summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
