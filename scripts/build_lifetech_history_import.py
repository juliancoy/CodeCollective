#!/usr/bin/env python3
"""Prepare selected archived events for OrgPortal's authorized calendar ingest."""
import argparse
import csv
import hashlib
import html
import importlib.util
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin

ROOT = Path(__file__).resolve().parents[1]


def instant(value):
    if not value:
        return ''
    return datetime.fromisoformat(value.replace('Z', '+00:00')).timestamp()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--events', type=Path, default=ROOT / 'baltimore/event_history.json')
    parser.add_argument('--inventory', type=Path, default=ROOT / 'baltimore/incubation_history/events.csv')
    parser.add_argument('--live-snapshot', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--portal-dir', type=Path, default=ROOT.parent / 'OrgPortal')
    args = parser.parse_args()
    sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location('portal_feed', args.portal_dir / 'org-worker/scripts/push_org_network_feed.py')
    feed = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(feed)
    events = json.loads(args.events.read_text())
    live = json.loads(args.live_snapshot.read_text())[0]['results']
    known = {(row['source_url'], instant(row['starts_at'])): row for row in live if row['source_url'] and row['starts_at']}
    category_tags = {'pitch_competition': 'Pitch Competition', 'demo_showcase': 'Demo Day / Showcase',
                     'incubation_acceleration': 'Incubation / Acceleration', 'pitch_practice': 'Pitch Practice',
                     'description_match': 'Startup Event', 'program_workshop': 'Accelerator Workshop'}
    prepared, manifest = {}, []
    with args.inventory.open(newline='') as stream:
        for row in csv.DictReader(stream):
            if row['category'] == 'excluded':
                continue
            event = events[int(row['output_index'])]
            city = row['city'] or 'baltimore'
            organizer_source = feed.normalize_url(event.get('source_url') or event.get('source'))
            start = feed.normalize_datetime_value(event.get('startDate'))
            end = feed.normalize_datetime_value(event.get('endDate') or event.get('endTime'))
            # The archive contains some malformed end times. Do not invent a duration.
            if end and start and instant(end) < instant(start):
                end = None
            source = feed.normalize_url(event.get('url'))
            tags = feed.normalize_tags(event.get('tags'), city)
            tags = sorted(set(tags + ['Entrepreneurship', 'LifeTech', 'life-tech-event-history', category_tags[row['category']]]))
            image = event.get('imageUrl')
            image = urljoin('https://codecollective.us/', image) if image else None
            item = {'title': html.unescape(event['name']).strip(), 'description': html.unescape(event.get('description') or ''),
                    'starts_at': start, 'ends_at': end, 'location': feed.render_location(event.get('location')),
                    'source_url': source, 'host_org_source_url': organizer_source,
                    'host_org_name': row['organizer_label'] if row['organizer_review']=='source_label_only' else None,
                    'image_url': image, 'tags': tags, 'city': city,
                    'links': [{'id': 'archive-evidence', 'url': f"https://github.com/juliancoy/CodeCollective/blob/{row['latest_record_commit']}/{row['latest_record_path']}",
                               'label': 'Archived event evidence', 'title': 'Original calendar snapshot'}]}
            old = known.get((source, instant(start)))
            item['ingest_key'] = old['ingest_key'] if old else feed.build_ingest_key(item)
            identity = (source or item['title'].casefold(), instant(start))
            if identity in prepared:
                # One real occurrence may appear in multiple archive records.
                prepared[identity]['tags'] = sorted(set(prepared[identity]['tags'] + tags))
                item = prepared[identity]
            else:
                prepared[identity] = item
            manifest.append({'output_index': int(row['output_index']), 'ingest_key': item['ingest_key'],
                             'title': item['title'], 'starts_at': start, 'category': row['category'],
                             'existing_event_id': old['id'] if old else None,
                             'first_seen_commit': row['first_seen_commit'], 'latest_record_commit': row['latest_record_commit']})
    payload = {'source': 'CodeCollective pitch event history', 'organization_slugs': ['lifetech'],
               'preserve_existing': True, 'organizations': [], 'events': list(prepared.values())}
    args.output.write_text(json.dumps(payload, indent=2)+'\n')
    args.output.with_suffix('.manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print(json.dumps({'archive_records':len(manifest),'event_occurrences':len(prepared),
                      'existing_event_matches':sum(bool(row['existing_event_id']) for row in manifest),
                      'new_event_occurrences':sum(item['ingest_key'] not in {row['ingest_key'] for row in live} for item in prepared.values()),
                      'payload_sha256':hashlib.sha256(args.output.read_bytes()).hexdigest()},indent=2))

if __name__ == '__main__':
    main()
