#!/usr/bin/env python3
"""Map every archived Compass field to flat rows and prepare repeat-safe SQL."""
import argparse,csv,gzip,hashlib,json,re,unicodedata
from urllib.parse import urlsplit
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'baltimore/incubation_history/enrichment/compass'
SOURCE='maryland_compass';RETRIEVED='2026-10-06';BASE='https://compass.maryland.gov/incentives/'
SCALAR={'id':'external_id','slug':'source_slug','agency':'agency_label','URL':'url','created_at':'source_created_at','updated_at':'source_updated_at'}
COLLECTIONS={'assistance_type','eligible_industries','eligible_counties','eligible_municipalities','eligible_regions','eligible_incentive_areas','eligible_organization_types','requirements_list','source_urls','attachment_urls','featured'}
def key(s):return re.sub(r'[^a-z0-9]','',unicodedata.normalize('NFKD',re.sub(r'\([^)]*\)','',s)).lower())
def q(v):
 if v is None:return 'NULL'
 if isinstance(v,bool):return str(int(v))
 return "'"+str(v).replace("'","''").replace('\r', "'||char(13)||'").replace('\x00', "'||char(0)||'")+"'"
def write_csv(name,rows):
 with (OUT/name).open('w') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def main():
 p=argparse.ArgumentParser();p.add_argument('--identities',type=Path,required=True);a=p.parse_args();archive_path=OUT/'source-details.jsonl'
 archive=[json.loads(l) for l in (archive_path.read_text().splitlines() if archive_path.exists() else gzip.open(str(archive_path)+'.gz','rt').read().splitlines())]
 summary=json.loads((OUT/'fetch-summary.json').read_text());assert len(archive)==summary['detail_records']==2868
 current=json.loads(a.identities.read_text());existing=current[0]['results'];classified={r['organization_id']:r for r in current[1]['results']};sourceids={r['external_id']:r['organization_id'] for r in current[2]['results']}
 existingids={r['id'] for r in existing};bykey={}
 for r in existing:bykey.setdefault(key(r['name']),[]).append(r)
 orgs={};entities={};agencyids={};ambiguous=[];sql=[];listings=[];properties=[];links=[];source_rows=[]
 def register(oid,name,slug,url,description,tags):
  orgs[oid]={'id':oid,'name':name,'slug':slug,'source_url':url,'description':description,'tags':json.dumps(tags)}
  return oid
 for name in sorted({r['agency'] for r in archive if r.get('agency')}):
  candidates=bykey.get(key(name),[])
  if name=='Maryland Technology Development Corporation (TEDCO)':oid='org-tedco'
  elif len(candidates)==1:oid=candidates[0]['id']
  elif len(candidates)>1:
   ambiguous.append({'agency_label':name,'candidates':' | '.join(r['id'] for r in candidates)});agencyids[name]=None;continue
  else:
   digest=hashlib.sha256(key(name).encode()).hexdigest()[:20];oid='compass-agency:'+digest
   # Identity is the administrator label reported by Compass, not verified legal incorporation.
   tags=['ecosystem','Compass listed administrator']
   if re.match(r'^Maryland (Department|State Department|Energy Administration|Higher Education Commission|State Arts Council)\b',name):tags=['state-government','State government','Compass listed administrator']
   sample=next(r for r in archive if r['agency']==name)
   register(oid,name,'compass-agency-'+digest,None,'Administrator listed by Maryland Community Compass. Original agency label retained; legal entity and jurisdiction are not independently verified.',tags)
  agencyids[name]=oid
 for r in archive:
  slug=r['slug'];name=r['program_name'];oid=sourceids.get(slug)
  # Reuse existing programs only when both name and primary URL agree.
  if not oid:
   candidates=[o for o in bykey.get(key(name),[]) if classified.get(o['id'],{}).get('entity_type') in ('program','funding_opportunity') and o.get('source_url','').rstrip('/')==str(r.get('URL','')).rstrip('/')]
   oid=candidates[0]['id'] if len(candidates)==1 else 'compass-program:'+str(r['id'])
  agency=agencyids.get(r.get('agency'));source_url=BASE+'#/incentive/'+slug
  primary=r.get('URL') or '';parsed=urlsplit(primary)
  primary=primary if parsed.scheme in ('http','https') and parsed.netloc and not parsed.username and not parsed.password else None
  register(oid,name,'compass-'+slug,primary,r.get('program_description') or 'Program listed by Maryland Community Compass.',['funding','Funding program','Maryland Compass'])
  if oid not in classified:entities[oid]={'organization_id':oid,'entity_type':'program','administering_organization_id':agency,'legal_entity_organization_id':None,'treasury_account_symbol':None,'source_url':source_url,'evidence':'Program identity and reported administrator supplied by Maryland Community Compass. Not a recipient award or a separately incorporated grantor.','reviewed_at':RETRIEVED}
  listing_id='compass:'+str(r['id']);listing={'id':listing_id,'source':SOURCE,'organization_id':oid,'agency_organization_id':agency,'compass_url':source_url}
  for field,value in r.items():
   if field not in COLLECTIONS:listing[SCALAR.get(field,field)]=value
  listing['external_id']=str(listing['external_id']);listing['retrieved_at']=RETRIEVED;listing['source_sha256']=hashlib.sha256(json.dumps(r,sort_keys=True,ensure_ascii=False).encode()).hexdigest();listings.append(listing)
  def flatten(field,value,position=0):
   if isinstance(value,dict):
    if not value:properties.append({'listing_id':listing_id,'field':field,'position':position,'value':None,'value_type':'empty_object'})
    for k,v in value.items():flatten(field+'.'+k,v)
   elif isinstance(value,list):
    if not value:properties.append({'listing_id':listing_id,'field':field,'position':position,'value':None,'value_type':'empty_array'})
    for i,v in enumerate(value):flatten(field,v,i)
   else:properties.append({'listing_id':listing_id,'field':field,'position':position,'value':str(value).lower() if isinstance(value,bool) else (str(value) if value is not None else None),'value_type':'null' if value is None else ('boolean' if isinstance(value,bool) else ('number' if isinstance(value,(int,float)) else 'string'))})
  for field in COLLECTIONS:flatten(field,r[field])
  source_rows.append({'source':SOURCE,'external_id':slug,'organization_id':oid})
  if agency and agency!=oid:
   links.append({'id':'compass-admin:'+str(r['id']),'from_organization_id':agency,'to_organization_id':oid,'from_label':r['agency'],'to_label':name,'support_kind':'terms','description':'Compass-listed program offering: '+name,'source_url':source_url,'evidence':'Compass agency field: '+r['agency'],'notes':'Program directory relationship, not funding paid or awarded. Status, limits, eligibility, contacts, deadlines and original sources are retained in funding_program_listings and funding_program_properties.','status':'reported'})
 def insert(table,r,update=False):
  stmt='INSERT INTO '+table+' ('+','.join(r)+') VALUES ('+','.join(q(v) for v in r.values())+')'
  if update:stmt+=' ON CONFLICT(id) DO UPDATE SET '+','.join(k+'=excluded.'+k for k in r if k!='id')
  else:stmt+=' ON CONFLICT DO NOTHING'
  sql.append(stmt+';')
 for r in orgs.values():insert('organizations',r)
 for r in entities.values():insert('funding_entities',r)
 for r in source_rows:insert('organization_source_identities',r)
 for r in listings:insert('funding_program_listings',r,True)
 for r in listings:sql.append('DELETE FROM funding_program_properties WHERE listing_id='+q(r['id'])+';')
 for r in properties:insert('funding_program_properties',r)
 for r in links:
  row={**r,'created_at':RETRIEVED};insert('organization_support_records',row)
 for name,data in [('organizations.csv',list(orgs.values())),('program-listings.csv',listings),('program-properties.csv',properties),('program-context.csv',links)]:write_csv(name,data)
 if ambiguous:write_csv('ambiguous-administrators.csv',ambiguous)
 (OUT/'apply.sql').write_text('\n'.join(sql)+'\n')
 info={'program_listings':len(listings),'program_property_rows':len(properties),'administrator_labels':len(agencyids),'unresolved_ambiguous_administrators':len(ambiguous),'new_organization_ids':len(set(orgs)-existingids),'new_program_entity_ids':len(entities),'program_context_records':len(links),'award_or_payment_records_created':0,'source_fields_preserved':summary['detail_fields']}
 (OUT/'import-summary.json').write_text(json.dumps(info,indent=2)+'\n');print(json.dumps(info))
if __name__=='__main__':main()
