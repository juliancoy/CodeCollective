"""Import the reviewed public event using OrgPortal's existing scoped feed credential."""
import json, os
from pathlib import Path
import requests
payload = json.loads(Path('baltimore/amplify-medtech/pitch-event.json').read_text())
assert len(payload['events']) == 1 and not payload['organizations']
event = payload['events'][0]
assert event['ingest_key'] == 'eventbrite:1998508613060'
assert len(set(event['support_record_ids'])) == 5
origin = 'https://lifetech.fyi/api/org/api/network'
token = os.environ['ORG_BACKEND_INGEST_TOKEN'].strip()
if not token:
    raise RuntimeError('Production calendar ingestion credential is missing')
response = requests.post(origin+'/ingest/calendar', json=payload, headers={'Authorization':'Bearer '+token}, timeout=60)
response.raise_for_status()
assert response.json().get('events') == 1, response.text
response = requests.get(origin+'/orgs/public/amplify-medtech/events',timeout=30)
response.raise_for_status()
rows = [row for row in response.json() if row['source_url']==event['source_url']]
assert len(rows) == 1, 'Expected one canonical hosted event'
canonical = rows[0]
url = 'https://lifetech.fyi/events/'+canonical['slug']
assert requests.get(origin+'/events/public/'+canonical['slug'], timeout=30).status_code == 200
response = requests.get(origin+'/orgs/public/amplify-medtech/support', timeout=30)
response.raise_for_status()
linked = []
for row in response.json()['records']:
    if row['record_id'] not in event['support_record_ids']:
        continue
    links = [item for item in json.loads(row['provenance_json']) if item.get('eventId')==canonical['id']]
    assert len(links)==1 and links[0]['eventUrl']==url, 'Canonical support link missing'
    linked.append(row['record_id'])
assert len(linked)==5
Path('amplify-pitch-event-receipt.json').write_text(json.dumps({'eventId':canonical['id'],'eventUrl':url,'linkedSupportRecords':linked},indent=2)+'\n')
print('Verified first-class event and five support links: '+url)
