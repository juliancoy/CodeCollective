#!/usr/bin/env python3
"""Record individually disclosed cash awards as reported support, not settlement."""
import csv,json,requests,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'baltimore/incubation_history/enrichment'
def read(n):
 with (OUT/n).open() as f:return list(csv.DictReader(f))
def main():
 env=ROOT.parent/'bmoremedtech/.env.pidp';values={k.strip():v.strip().strip('\"\'') for l in env.read_text().splitlines() if '=' in l and not l.lstrip().startswith('#') for k,v in [l.split('=',1)]}
 s=requests.Session();s.headers['Authorization']='Bearer '+values['PIDP_PAT'];base='https://lifetech.fyi/api/org/api/network'
 def request(method,path,data=None):
  for attempt in range(5):
   r=s.request(method,base+path,json=data,timeout=30)
   if r.status_code==429:time.sleep(15);continue
   r.raise_for_status();return r.json()
  raise RuntimeError('Rate limit persisted')
 ids={r['entity_id']:r['portal_organization_id'] for r in read('applied-portal-identities.csv')};entities={r['entity_id']:r['name'] for r in read('entities.csv')};sources={r['source_id']:r['url'] for r in read('verified_sources.csv')}
 issuers={'cbic':'org-university-of-maryland-baltimore-county','rise':'registry-a3cec895-ec6d-4cad-a2db-2cb174fcb5d2'};dates={'cbic':'2026-04-16','rise':'2026-05-06'}
 count=0
 with (OUT/'published-award-support-receipts.jsonl').open('a') as log:
  for award in read('published_awards.csv'):
   if not award['amount']:continue
   issuer=issuers[award['source_id']];recipient=ids[award['recipient_entity_id']];org=request('GET','/orgs/'+issuer);existing=request('GET','/orgs/public/'+org['slug']+'/support')['records']
   description='Published competition award: '+award['award']
   if any(r['to_organization_id']==recipient and r['description']==description and r['source_url']==sources[award['source_id']] for r in existing):continue
   args={'organizationId':issuer,'recipientOrganizationId':recipient,'supportKind':'transfer','amount':float(award['amount']),'currency':'USD','description':description,'occurredAt':dates[award['source_id']],'sourceUrl':sources[award['source_id']],'evidence':f"Official university announcement names {entities[award['recipient_entity_id']]} and an individual USD {award['amount']} award.",'notes':'Reported award announced by the university competition. Institution is the announcing/awarding organization, not a verified cash disburser. Payment and settlement are unverified. Do not sum with prize pools or repeat reports.','status':'reported'}
   preview=request('POST','/orgs/'+issuer+'/support/record',{**args,'confirm':False})
   assert preview['changes']['amount']==args['amount'] and preview['to']['id']==recipient and preview['from']['id']==issuer
   log.write(json.dumps({'status':'previewed','preview':preview})+'\n');log.flush()
   result=request('POST','/orgs/'+issuer+'/support/record',{**args,'confirm':True,'previewId':preview['previewId']})
   assert any(r['record_id']==result['recordId'] for r in result['result']['records'])
   log.write(json.dumps({'status':'applied','result':result})+'\n');log.flush();count+=1
 print(json.dumps({'reported_individual_cash_awards_applied':count,'settlements_created':0,'undisclosed_and_shared_awards_not_allocated':8}))
if __name__=='__main__':main()
