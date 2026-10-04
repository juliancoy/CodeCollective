#!/usr/bin/env python3
"""Apply reviewed public research through OrgPortal permissions and preview receipts."""
import argparse,csv,json,re,time
from pathlib import Path
from datetime import datetime
from collections import Counter,defaultdict
import requests
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'baltimore/incubation_history/enrichment'
def read(name):
 with (OUT/name).open() as f:return list(csv.DictReader(f))
def norm(name):return re.sub(r'[^a-z0-9]','',name.casefold())
def instant(v):return datetime.fromisoformat(re.sub(r'([+-]\d{2})(\d{2})$',r'\1:\2',v.replace('Z','+00:00'))).timestamp()
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--env-file',type=Path,required=True);p.add_argument('--apply',action='store_true');a=p.parse_args()
 values={k.strip():v.strip().strip('\"\'') for l in a.env_file.read_text().splitlines() if '=' in l and not l.lstrip().startswith('#') for k,v in [l.split('=',1)]}
 s=requests.Session();s.headers['Authorization']='Bearer '+values['PIDP_PAT'];base='https://lifetech.fyi/api/org'
 def call(method,path,body=None):
  # Honor the upstream rate limit without replaying uncertain mutation requests.
  for attempt in range(5):
   r=s.request(method,base+path,json=body,timeout=40)
   if r.status_code==429:
    print('Portal rate limit: waiting 20 seconds',flush=True);time.sleep(20);continue
   if not r.ok:raise RuntimeError(f'{method} {path}: {r.status_code} {r.text[:150]}')
   return r.json()
  raise RuntimeError('Portal rate limit persisted')
 logpath=OUT/'live-enrichment-receipt.jsonl'
 log=logpath.open('a') if a.apply else None
 def record(row):
  if log:log.write(json.dumps(row)+'\n');log.flush()
 def apply(path,args,expected):
  preview=call('POST',path,{**args,'confirm':False})
  for key,value in expected.items():
   if preview.get(key)!=value:raise ValueError('Preview differs from reviewed changes: '+key)
  record(dict(endpoint=path,status='previewed',preview=preview))
  result=call('POST',path,{**args,'confirm':True,'previewId':preview['previewId']})
  record(dict(endpoint=path,status='applied',result=result));return result
 assert call('GET','/admin/me')['is_admin'],'Master admin access required'
 sources={r['source_id']:r['url'] for r in read('verified_sources.csv')}
 entities={r['entity_id']:r for r in read('entities.csv')};relations=read('cohort_relationship_candidates.csv');awards=read('published_awards.csv')
 provenance={}
 for r in relations:
  for key in ['recipient_entity_id','supporter_entity_id']:provenance.setdefault(r[key],r['source_id'])
 for r in awards:provenance.setdefault(r['recipient_entity_id'],r['source_id'])
 directory=json.loads((OUT/'identity-directory-snapshot.json').read_text());ids={};registry=[]
 for eid,source in provenance.items():
  e=entities[eid];name=e['name'];found=[o for o in directory if norm(o['name'])==norm(name)]
  fresh=call('GET','/api/network/orgs/public?q='+requests.utils.quote(name,safe='')+'&limit=100')
  found=list({o['id']:o for o in found+fresh if norm(o['name'])==norm(name)}.values())
  if len(found)>1:raise ValueError('Ambiguous identity: '+name)
  if found:ids[eid]=found[0]['id'];continue
  description='Named venture in a published '+('competition award announcement.' if source in ['cbic','rise','loyola_awards'] else 'program cohort list.') if e['entity_kind']=='venture' else 'Supporting organization identified in the published program record.'
  args=dict(name=name,description=description,sourceUrl=sources[source],tags=['LifeTech','Entrepreneurship','Venture' if e['entity_kind']=='venture' else 'Supporting Organization'])
  registry.append(dict(entity_id=eid,arguments=args))
 if registry or not (OUT/'reviewed-registration-plan.jsonl').exists():
  (OUT/'reviewed-registration-plan.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in registry))
 if not a.apply:print(json.dumps({'registrations_prepared':len(registry),'existing_identity_matches':len(ids),'relationships':len(relations),'live_writes':0}));return
 for row in registry:
  result=apply('/api/network/orgs/registry',row['arguments'],{'operation':'register'})
  ids[row['entity_id']]=result['organizationId']
 (OUT/'applied-portal-identities.csv').write_text('entity_id,portal_organization_id\n'+''.join(f'{k},{v}\n' for k,v in ids.items()))
 dates={'2025 spring':'2025-06-05','2025 fall':'2025-12-04','II':'2026-01-27','III':'2026-07-16','2026 inaugural':'2026-03-17','2026':'2026-03-19','6':'2026-05-11'}
 supports={};support_count=0
 for row in relations:
  giver=ids[row['supporter_entity_id']];recipient=ids[row['recipient_entity_id']]
  if giver not in supports:
   org=call('GET','/api/network/orgs/'+giver);supports[giver]=call('GET','/api/network/orgs/public/'+org['slug']+'/support')['records']
  kind='services' if row['relationship_kind']=='program_participation' else row['relationship_kind']
  description=f"{row['program']} cohort {row['cohort']}"
  if any(r.get('to_organization_id')==recipient and r.get('description')==description and r.get('source_url')==sources[row['source_id']] for r in supports[giver]):continue
  args=dict(organizationId=giver,recipientOrganizationId=recipient,supportKind=kind,description=description,occurredAt=dates[row['cohort']],sourceUrl=sources[row['source_id']],evidence=f"Publisher identifies {entities[row['recipient_entity_id']]['name']} as a member of this cohort.",notes='Historical reported participation. Showcase date is not support start. No monetary amount or ownership is asserted.'+(' Services means the documented cohort education and mentorship; acceleration is not inferred.' if kind=='services' else ''),status='reported')
  result=apply('/api/network/orgs/'+giver+'/support/record',args,{'operation':'record'})
  if not any(r.get('id') in [result['recordId'],'support:'+result['recordId']] for r in result['result']['records']):raise ValueError('Support write failed verification')
  supports[giver]=result['result']['records'];support_count+=1
 events=call('GET','/api/network/orgs/public/lifetech/events?limit=200');byid={e['id']:e for e in events};updates={};field_sources={}
 for row in read('event_field_candidates.csv'):
  e=byid.get(row['event_id']);field=row['field']
  if not e or field not in ['ends_at','location','image_url'] or e.get(field) or row['start_instant_matches']!='True' or float(row['title_similarity'])<0.95 or row['source_url']!=e.get('source_url'):continue
  if field=='ends_at' and instant(row['proposed_value'])<=instant(e['starts_at']):continue
  updates.setdefault(e['id'],{})[field]=row['proposed_value'];field_sources[e['id']]=row['source_url']
 # Publish award facts as event metadata, never as payments or invented incubation.
 grouped=defaultdict(list)
 for award in awards:grouped[award['event_id']].append(award)
 for event_id,items in grouped.items():
  e=byid[event_id];source=sources[items[0]['source_id']];heading='Published competition awards (payment not verified):'
  if heading in (e.get('description') or ''):continue
  lines=[heading]+[entities[r['recipient_entity_id']]['name']+' — '+r['award']+(f" — USD {r['amount']}" if r['amount'] else '') for r in items]+['Source: '+source]
  updates.setdefault(event_id,{})['description']=((e.get('description') or '')+'\n\n'+'\n'.join(lines)).strip();field_sources[event_id]=source
 enriched=0
 for event_id,changes in updates.items():
  apply('/api/network/events/'+event_id+'/enrichment',dict(sourceUrl=field_sources[event_id],changes=changes),{'operation':'enrich','eventId':event_id})
  e=byid[event_id];fresh=call('GET','/api/network/events/public/'+e['slug'])
  for key,value in changes.items():
   if key=='ends_at':assert instant(fresh[key])==instant(value)
   else:assert fresh[key]==value
  enriched+=1
 applied=[json.loads(line) for line in logpath.read_text().splitlines() if line.strip() and json.loads(line)['status']=='applied']
 totals=Counter(row['endpoint'].split('/')[-1] for row in applied)
 summary=dict(registrations_applied=totals['registry'],matched_research_identities=len(ids),cohort_support_records_applied=totals['record'],events_enriched=totals['enrichment'],published_awards_in_event_metadata=len(awards),live_writes=len(applied))
 (OUT/'live-enrichment-summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2));log.close()
if __name__=='__main__':main()
