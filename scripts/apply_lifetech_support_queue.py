#!/usr/bin/env python3
"""Apply explicitly reviewed support calls through OrgPortal preview/apply receipts."""
import argparse
import json
import os
from pathlib import Path
import requests

def validate_preview(preview,args):
 if preview.get('operation')!='record' or preview.get('from',{}).get('id')!=args['organizationId'] or preview.get('to',{}).get('id')!=args['recipientOrganizationId']:
  raise ValueError('Preview endpoints differ from reviewed request')
 changes=preview.get('changes',{})
 for key,value in args.items():
  if changes.get(key)!=value:raise ValueError(f'Preview changed {key}')
 if not preview.get('previewId'):raise ValueError('Preview receipt missing')

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--queue',type=Path,required=True);p.add_argument('--receipt',type=Path,required=True);p.add_argument('--env-file',type=Path);p.add_argument('--base-url',default='https://lifetech.fyi/api/org');a=p.parse_args()
 rows=[json.loads(line) for line in a.queue.read_text().splitlines() if line.strip()]
 if any(r.get('identity_review_required',True) for r in rows):raise ValueError('Review identity matches before submitting the queue')
 if not rows:raise ValueError('No reviewed calls available')
 if a.receipt.exists():raise ValueError('Existing receipt found; inspect before retrying')
 credentials={}
 if a.env_file:
  for line in a.env_file.read_text().splitlines():
   if '=' in line and not line.lstrip().startswith('#'):
    key,value=line.split('=',1);credentials[key.strip()]=value.strip().strip("\"'")
 token=os.environ.get('ORGPORTAL_ACCESS_TOKEN',credentials.get('PIDP_PAT','')).strip()
 if not token:raise ValueError('Connect authorized OrgPortal/PIdP identity; ORGPORTAL_ACCESS_TOKEN is required')
 session=requests.Session();session.headers['Authorization']='Bearer '+token
 with a.receipt.open('x') as log:
  for r in rows:
   args=r['arguments'];endpoint=a.base_url.rstrip('/')+r['endpoint']
   # Avoid recording duplicate historical evidence on repeat attempts.
   listing=session.get(a.base_url.rstrip('/')+'/api/network/orgs/public/'+args['organizationId']+'/support',timeout=30)
   # Public route expects slug, so read it from the matched organization record.
   org=session.get(a.base_url.rstrip('/')+'/api/network/orgs/'+args['organizationId'],timeout=30)
   if org.ok:
    slug=org.json().get('slug')
    if slug:listing=session.get(a.base_url.rstrip('/')+'/api/network/orgs/public/'+slug+'/support',timeout=30)
   if not listing.ok:raise ValueError('Cannot verify existing evidence; refusing duplicate-risk write')
   existing=listing.json().get('records',[])
   if len(existing)>=500:raise ValueError('Existing evidence truncated; review before applying')
   if any(x.get('to_organization_id')==args['recipientOrganizationId'] and x.get('source_url')==args['sourceUrl'] and x.get('description')==args['description'] for x in existing):
    log.write(json.dumps({'candidate_id':r['candidate_id'],'status':'already_present'})+'\n');log.flush();continue
   response=session.post(endpoint,json={**args,'confirm':False},timeout=30);response.raise_for_status();preview=response.json();validate_preview(preview,args)
   log.write(json.dumps({'candidate_id':r['candidate_id'],'status':'previewed','preview':preview})+'\n');log.flush()
   response=session.post(endpoint,json={**args,'confirm':True,'previewId':preview['previewId']},timeout=30);response.raise_for_status()
   log.write(json.dumps({'candidate_id':r['candidate_id'],'status':'applied','result':response.json()})+'\n');log.flush()
if __name__=='__main__':main()
