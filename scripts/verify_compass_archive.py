#!/usr/bin/env python3
"""Compare every source field against its imported flat SQLite representation."""
import argparse,gzip,json,sqlite3,collections
from pathlib import Path
OUT=Path(__file__).resolve().parents[1]/'baltimore/incubation_history/enrichment/compass'
ALIASES={'id':'external_id','slug':'source_slug','agency':'agency_label','URL':'url','created_at':'source_created_at','updated_at':'source_updated_at'}
COLLECTIONS={'assistance_type','eligible_industries','eligible_counties','eligible_municipalities','eligible_regions','eligible_incentive_areas','eligible_organization_types','requirements_list','source_urls','attachment_urls','featured'}
def decode(r):
 t=r['value_type'];v=r['value']
 return None if t=='null' else ([] if t=='empty_array' else ({} if t=='empty_object' else (float(v) if t=='number' else (v=='true' if t=='boolean' else v))))
def main():
 p=argparse.ArgumentParser();p.add_argument('database');a=p.parse_args();db=sqlite3.connect(a.database);db.row_factory=sqlite3.Row
 listings={r['external_id']:dict(r) for r in db.execute("SELECT * FROM funding_program_listings WHERE source='maryland_compass'")};props=collections.defaultdict(list)
 for r in db.execute('SELECT * FROM funding_program_properties ORDER BY listing_id,field,position'):props[r['listing_id']].append(dict(r))
 checked=0
 archive=OUT/'source-details.jsonl'
 for line in (archive.read_text().splitlines() if archive.exists() else gzip.open(str(archive)+'.gz','rt').read().splitlines()):
  original=json.loads(line);stored=listings[str(original['id'])];attributes=props[stored['id']]
  for field,value in original.items():
   if field not in COLLECTIONS:
    actual=stored[ALIASES.get(field,field)]
    if field=='id':actual=int(actual)
   elif field!='featured' or not isinstance(value,dict):
    selected=[r for r in attributes if r['field']==field]
    if isinstance(value,list):actual=[] if selected[0]['value_type']=='empty_array' else [decode(r) for r in selected]
    else:actual=decode(selected[0])
   else:
    actual={}
    for r in attributes:
     if not r['field'].startswith('featured.'):continue
     path=r['field'].split('.')[1:];target=actual
     for segment in path[:-1]:target=target.setdefault(segment,{})
     target[path[-1]]=decode(r)
   assert actual==value,(original['slug'],field,actual,value)
   checked+=1
 result={'programs_verified':len(listings),'source_fields_compared':checked,'all_fields_match':True};(OUT/'roundtrip-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
if __name__=='__main__':main()
