#!/usr/bin/env python3
"""Classify imported public evidence without upgrading it to paid/obligated."""
import csv,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'baltimore/incubation_history/enrichment';OUT=BASE/'funding_model'
def rows(p):return list(csv.DictReader(p.open()))
def q(v):return 'NULL' if v is None or v=='' else "'"+str(v).replace("'","''")+"'"
def main():
 OUT.mkdir(parents=True,exist_ok=True);sql=[];entities=[];facts=[];awards=[]
 federal=rows(BASE/'federal_portal/organizations.csv');md=rows(BASE/'maryland_budget/organizations.csv')
 byname={r['name']:r['id'] for r in federal+md}
 def entity(oid,kind,admin,url,evidence):
  r={'organization_id':oid,'entity_type':kind,'administering_organization_id':admin,'legal_entity_organization_id':oid if kind in ('government','agency') else None,'treasury_account_symbol':None,'source_url':url,'evidence':evidence,'reviewed_at':'2026-10-06'};entities.append(r)
 for r in federal:
  if 'Federal government' not in json.loads(r['tags']):continue
  entity(r['id'],'government' if r['name']=='United States Federal Government' else ('program' if 'Funding program' in json.loads(r['tags']) else 'agency'),None,r['source_url'],'Registered public federal government, agency or program identity; program is not a separately incorporated grantor.')
 entity(byname['State of Maryland'],'government',None,'https://www.maryland.gov/','State government identity.')
 mea=byname['Maryland Energy Administration'];seif=byname['Maryland Strategic Energy Investment Fund']
 entity(mea,'agency',None,'https://energy.maryland.gov/','MEA administers the SEIF.')
 entity(seif,'statutory_fund',mea,'https://mgaleg.maryland.gov/mgawebsite/Laws/StatuteText?article=gsg&section=9-20B-05&enactments=false','State Government Article 9-20B-05 establishes the Strategic Energy Investment Fund; MEA administers the fund.')
 entity('org-tedco','agency',None,'https://msa.maryland.gov/msa/mdmanual/25ind/html/71techb.html','Maryland Technology Development Corporation, budget code T50T01.')
 imported=rows(BASE/'federal_portal/records.csv')+rows(BASE/'maryland_budget/records.csv')
 programs={
 'FAST':'Federal and State Technology Partnership Program (FAST)',
 'State Trade Expansion':'State Trade Expansion Program (STEP)',
 'SSBCI SBOP':'SSBCI Small Business Opportunity Program (SBOP)',
 'SUPER':'ARPA-E SUPER Program',
 'Quantum Leap':'NSF Quantum Leap Challenge Institutes',
 'CERSI':'Centers of Excellence in Regulatory Science and Innovation (CERSI)',
 'Public Health Emergency':'Public Health Emergency Preparedness (PHEP)',
 'Public Health Infrastructure':'Public Health Infrastructure Grant (PHIG)'}
 for r in imported:
  amount=float(r['amount']) if r['amount'] else None;currency=r['currency'] or None
  kind='administration' if r['support_kind'] not in ('transfer','terms') else ('reported_award' if r['support_kind']=='transfer' else 'program_ceiling')
  scope='institution' if kind=='administration' else 'award';measurement='not_applicable' if kind=='administration' else ('ceiling' if kind=='program_ceiling' else 'cumulative')
  fy=None;basis=None;start=None;end=None;program=None;fund=None;award=None
  if r['id'].startswith('md-budget:'):
   if r['support_kind']=='terms':kind='appropriation' if 'appropriation' in r['description'] else 'agency_expenditure';scope='agency';measurement='period_total'
   if kind!='administration':fy=int(re.search(r'FY(\d{4})',r['description'])[1]);basis='maryland';start=f'{fy-1}-07-01';end=f'{fy}-06-30'
   if r['support_kind']=='transfer':fund=seif
  else:
   for needle,name in programs.items():
    if needle in r['description']:program=byname[name];break
   if 'Public Health' in r['description']:scope='program';measurement='period_total'
   if r['occurred_at'].startswith('FY'):fy=int(r['occurred_at'][2:]);basis='federal';start=f'{fy-1}-10-01';end=f'{fy}-09-30'
   match=re.search(r'(OMA-2120757|2024-67023-42841|2024-38821-42091)',r['description'])
   if match:
    award='award:'+match[1];awards.append({'id':award,'awarding_agency_id':r['from_organization_id'],'award_identifier':match[1],'recipient_organization_id':r['to_organization_id'],'recipient_uei':None,'assistance_listing_number':None,'source_url':r['source_url'],'evidence':'Identifier explicitly stated in the imported primary-source award description.'})
  agency=r['from_organization_id'] if any(e['organization_id']==r['from_organization_id'] and e['entity_type']=='agency' for e in entities) else None
  facts.append({'id':'fact:'+r['id'],'support_record_id':r['id'],'fact_type':kind,'scope':scope,'amount':amount,'currency':currency,'measurement':measurement,'fiscal_year':fy,'fiscal_year_basis':basis,'period_start':start,'period_end':end,'reporting_date':None,'administering_agency_id':agency,'program_organization_id':program,'fund_organization_id':fund,'account_organization_id':None,'award_id':award,'included_in_fact_id':None,'supersedes_fact_id':None,'source_url':r['source_url'],'evidence':r['evidence']+' '+r['notes'],'reviewed_at':'2026-10-06'})
 # Administrative program links supply exact administrators; root is not a payer.
 for r in imported:
  if r['description']=='Federal funding program administration':
   for e in entities:
    if e['organization_id']==r['to_organization_id']:e['administering_organization_id']=r['from_organization_id']
 for name,table,data in [('entities.csv','funding_entities',entities),('awards.csv','funding_awards',awards),('facts.csv','funding_facts',facts)]:
  with (OUT/name).open('w') as f:w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
  for r in data:sql.append('INSERT INTO '+table+' ('+','.join(r)+') VALUES ('+','.join(q(v) for v in r.values())+') ON CONFLICT DO NOTHING;')
 (OUT/'backfill.sql').write_text('\n'.join(sql)+'\n')
 summary={'typed_entities':len(entities),'identified_awards':len(awards),'classified_facts':len(facts),'obligations_inferred':0,'disbursements_inferred':0,'treasury_accounts_inferred':0}
 (OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary))
if __name__=='__main__':main()
