#!/usr/bin/env python3
"""Register existing sourced federal research and flat administration links.
No ledger payments, memberships or permission grants. Conflict-safe SQL output.
"""
import argparse,csv,json,re,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'baltimore/incubation_history/enrichment/federal_portal'
def key(s):return re.sub(r'[^a-z0-9]','',s.lower())
def q(v):return 'NULL' if v is None else "'"+str(v).replace("'","''")+"'"
def main():
 p=argparse.ArgumentParser();p.add_argument('--organizations',type=Path,required=True);a=p.parse_args();OUT.mkdir(parents=True,exist_ok=True)
 snapshot=json.loads((ROOT.parent/'OrgPortal/web/public/ecosystem-data/ecosystem-relationships.json').read_text())
 evidence=[r for r in snapshot['relationships'] if r['id'].startswith('research-federal')];assert len(evidence)==32
 existing=json.loads(a.organizations.read_text())[0]['results'];bykey={}
 for o in existing:bykey.setdefault(key(o['name']),[]).append(o)
 orgs={};mapping={};sql=[]
 aliases={'federal-recipient-umd-college-park':'md-budget:university-of-maryland-college-park','research-tedco':'org-tedco'}
 def register(o):
  matches=bykey.get(key(o['name']),[])
  if len(matches)>1:raise ValueError('Ambiguous identity: '+o['name'])
  oid=aliases.get(o['id']) or (matches[0]['id'] if matches else 'federal-portal:'+o['id'])
  mapping[o['id']]=oid
  category=o.get('category','general');tags=[category,'LifeTech','Federal evidence research']
  if category=='federal-government':tags.append('Federal government')
  if category=='state-government':tags.append('State government')
  if o.get('program'):tags.append('Funding program')
  image=o.get('imageUrl');image=None if image and ('X-Amz-' in image or 'Token=' in image) else image
  row={'id':oid,'name':o['name'],'slug':re.sub(r'[^a-z0-9]+','-',o['name'].lower()).strip('-'),'description':o.get('relevance','Public federal government or funding-program identity; administrative links do not imply financial transfers.'),'source_url':o['website'],'image_url':image,'tags':json.dumps(tags)}
  orgs[oid]=row
  sql.append('INSERT INTO organizations ('+','.join(row)+') VALUES ('+','.join(q(v) for v in row.values())+') ON CONFLICT(id) DO NOTHING;')
  if category=='federal-government':sql.append("UPDATE organizations SET tags=json_insert(tags,'$[#]','Federal government') WHERE id="+q(oid)+" AND NOT EXISTS (SELECT 1 FROM json_each(organizations.tags) WHERE value='Federal government');")
 endpoints={r[k] for r in evidence for k in ('source','target')}
 for o in snapshot['organizations']:
  if o['id'] in endpoints or o.get('category')=='federal-government':register(o)
 register({'id':'usa','name':'United States Federal Government','category':'federal-government','website':'https://www.usa.gov/agency-index'})
 records=[]
 def record(r, imported=False):
  row={'id':('bmoremedtech:'+r['id']) if imported else ('federal-portal:'+r['id']),'from_organization_id':mapping[r['source']],'to_organization_id':mapping[r['target']],'from_label':r.get('sourceLabel',orgs[mapping[r['source']]]['name']),'to_label':r.get('targetLabel',orgs[mapping[r['target']]]['name']),'support_kind':r['kind'],'amount':r.get('amount'),'currency':r.get('currency'),'amount_label':r.get('amountLabel',''),'description':r['description'],'occurred_at':r.get('date',''),'source_url':r['sourceUrl'],'evidence':r.get('evidence','Primary public source identifies the government, agency or program relationship.'),'notes':r.get('notes','Administrative relationship only; no monetary flow or appropriation inferred.'),'status':'reported'}
  if imported:row['notes']+=' Original research identity: '+r['id']+'. Public graph keeps its existing static evidence edge and excludes this duplicate import via the established bmoremedtech prefix.'
  records.append(row)
  sql.append('INSERT INTO organization_support_records ('+','.join(row)+',created_at) VALUES ('+','.join(q(v) for v in row.values())+",strftime('%Y-%m-%dT%H:%M:%fZ','now')) ON CONFLICT(id) DO NOTHING;")
 for r in evidence:record(r,True)
 for agency in ['nsf','sba','doe','dod','nasa','commerce','usda','treasury','hhs']:
  record({'id':'usa-'+agency,'source':'usa','target':'federal-'+agency,'kind':'affiliation','description':'U.S. federal government department or independent agency','sourceUrl':'https://www.usa.gov/agency-index'})
 programs=[
 ('ssbci','State Small Business Credit Initiative (SSBCI)','federal-treasury','https://home.treasury.gov/policy-issues/small-business-programs/state-small-business-credit-initiative-ssbci'),
 ('sbop','SSBCI Small Business Opportunity Program (SBOP)','program-ssbci','https://home.treasury.gov/news/press-releases/jy2566'),
 ('fast','Federal and State Technology Partnership Program (FAST)','federal-sba','https://www.tedcomd.com/press-release/tedco-announces-accepting-federal-and-state-technology-partnership-program-grant'),
 ('step','State Trade Expansion Program (STEP)','federal-sba','https://www.sba.gov/loans/additional-funding-opportunities/grants/'),
 ('phep','Public Health Emergency Preparedness (PHEP)','federal-cdc','https://www.cdc.gov/readiness/php/data-research/maryland-funding.html'),
 ('phig','Public Health Infrastructure Grant (PHIG)','federal-cdc','https://www.cdc.gov/infrastructure-phig/php/funding-profiles/state-and-territories.html'),
 ('cersi','Centers of Excellence in Regulatory Science and Innovation (CERSI)','federal-fda','https://www.fda.gov/science-research/advancing-regulatory-science/centers-excellence-regulatory-science-and-innovation-cersis'),
 ('super','ARPA-E SUPER Program','federal-arpa-e','https://arpa-e.energy.gov/programs-and-initiatives/search-all-projects/modular-design-and-additive-manufacturing-interlocking-superinsulation-panel-bio-based-feedstock-autonomous-construction'),
 ('qlci','NSF Quantum Leap Challenge Institutes','federal-nsf','https://research.umd.edu/news/umd-leads-new-25m-nsf-quantum-leap-challenge-institute-robust-quantum-simulation')]
 for pid,name,parent,url in programs:
  register({'id':'program-'+pid,'name':name,'category':'federal-government','website':url,'program':True})
  record({'id':'program-'+pid,'source':parent,'target':'program-'+pid,'kind':'affiliation','description':'Federal funding program administration','sourceUrl':url})
 # Nonfinancial links expose program participation without repeating award amounts.
 for pid,recipient,url in [('sbop','research-tedco',programs[1][3]),('fast','research-tedco',programs[2][3]),('step','research-maryland-commerce',programs[3][3]),('phep','federal-recipient-md-health',programs[4][3]),('phig','federal-recipient-md-health',programs[5][3]),('cersi','federal-recipient-umd-cersi',programs[6][3]),('cersi','federal-recipient-jhu-cersi',programs[6][3]),('super','federal-recipient-umd-college-park',programs[7][3]),('qlci','federal-recipient-rqs',programs[8][3])]:
  record({'id':pid+'-'+recipient,'source':'program-'+pid,'target':recipient,'kind':'affiliation','description':'Documented federal program participation','sourceUrl':url,'notes':'Program participation only; monetary evidence remains on the original agency-to-recipient award. Do not count this link as another award.'})
 for name,rows in [('organizations.csv',list(orgs.values())),('records.csv',records)]:
  with (OUT/name).open('w') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 (OUT/'apply.sql').write_text('\n'.join(sql)+'\n')
 summary={'federal_agencies':17,'government_root':1,'funding_programs':9,'existing_research_records_registered':32,'new_administrative_links':27,'total_records':len(records),'new_organization_ids':len(set(orgs)-{o['id'] for o in existing}),'settlements_created':0,'snapshot_sha256':hashlib.sha256(json.dumps(snapshot,sort_keys=True).encode()).hexdigest()}
 (OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary))
if __name__=='__main__':main()
