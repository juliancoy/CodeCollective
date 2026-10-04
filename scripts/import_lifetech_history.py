#!/usr/bin/env python3
"""Run the prepared import through the existing authorized OrgPortal interface."""
import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlparse


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--payload', type=Path, required=True)
    parser.add_argument('--portal-dir', type=Path, required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args()
    payload = json.loads(args.payload.read_text())
    if payload.get('organization_slugs') != ['lifetech'] or payload.get('preserve_existing') is not True or payload.get('organizations'):
        raise ValueError('Unexpected collection or import options')
    url = os.environ['ORG_BACKEND_INGEST_URL'].strip()
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.hostname not in ['codecollective.us', 'org-codecollective.jcloiacon.workers.dev', 'lifetech.fyi'] or not parsed.path.endswith('/api/network/ingest/calendar'):
        raise ValueError('Unexpected production ingest destination')
    token = os.environ['ORG_BACKEND_INGEST_TOKEN'].strip()
    if not token:
        raise ValueError('Missing production calendar ingest credential')
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    spec = importlib.util.spec_from_file_location('portal_feed', args.portal_dir / 'org-worker/scripts/push_org_network_feed.py')
    feed = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(feed)
    events = payload['events']
    if len(events)!=99 or len({event['ingest_key'] for event in events})!=99:
        raise ValueError('Expected exactly 99 distinct reviewed event records')
    results=[]
    for index, chunk in enumerate(feed.chunks(events,10),1):
        result=feed.post_payload(url,token,{**payload,'events':chunk})
        if result.get('ok') is not True or result.get('events')!=len(chunk):
            raise RuntimeError(f'Incomplete batch {index}')
        results.append({'batch':index,'events':result['events']})
        args.receipt.write_text(json.dumps({'batches':results,'imported_events':sum(row['events'] for row in results)},indent=2)+'\n')
        print(f'Imported batch {index}: {result["events"]} events')
    # Verify every event is in LifeTech's collection and has its first-class detail.
    import requests
    origin='https://lifetech.fyi/api/org'
    response=requests.get(origin+'/api/network/orgs/public/lifetech/events',params={'limit':200},timeout=30)
    response.raise_for_status()
    rows=response.json()
    by_key={(row.get('source_url'),row.get('starts_at')):row for row in rows}
    verified=[]
    from datetime import datetime
    from zoneinfo import ZoneInfo
    def instant(value):
        if not value: return None
        import re
        value=re.sub(r'([+-]\d{2})(\d{2})$',r'\1:\2',value.replace('Z','+00:00'))
        parsed=datetime.fromisoformat(value)
        if parsed.tzinfo is None: parsed=parsed.replace(tzinfo=ZoneInfo('America/New_York'))
        return parsed.timestamp()
    for event in events:
        matches=[row for row in rows if row.get('source_url')==event['source_url'] and instant(row.get('starts_at'))==instant(event['starts_at'])]
        if len(matches)!=1: raise RuntimeError(f'Expected one LifeTech record for {event["title"]}; got {len(matches)}')
        row=matches[0]
        if not set(event['tags']).issubset(set(row['tags'])): raise RuntimeError(f'Tags missing for {event["title"]}')
        detail=requests.get(origin+'/api/network/events/public/'+row['slug'],timeout=30)
        detail.raise_for_status()
        if detail.json().get('id')!=row['id']: raise RuntimeError('Event detail mismatch')
        verified.append({'id':row['id'],'slug':row['slug'],'url':'https://lifetech.fyi/events/'+row['slug']})
    args.receipt.write_text(json.dumps({'batches':results,'imported_events':len(events),'verified_events':verified},indent=2)+'\n')
    print(f'Verified {len(verified)} first-class events in the live LifeTech collection')

if __name__=='__main__':
    main()
