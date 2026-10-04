#!/usr/bin/env python3
"""Build a flat research queue; production writes stay in OrgPortal preview/apply."""
import argparse
import csv
import hashlib
import html
import json
import re
import sqlite3
from pathlib import Path
from urllib.parse import urlparse

RULES = [
    ('pitch_competition', r'pitch.*compet|venture.*compet|business.*compet|idea.*compet|competition day|shark.?tank|chesapitch'),
    ('demo_showcase', r'demo\s*day|(?:startup|start.up|founder|entrepreneur|venture|accelerator|incubator|biohealth|investor).*showcase|showcase.*pitch'),
    ('incubation_acceleration', r'\b(?:incubator|accelerator|pre-accelerator)\b'),
    ('pitch_practice', r'\bpitch(?:ing|es)?\b|chesapitch'),
]
EXCLUSIONS = re.compile(r'pitch.*(?:pints|hit.*run)|living labs as climate policy accelerators', re.I)
PROVIDERS = {'eventbrite.com', 'meetup.com', 'luma.com', 'lu.ma'}
# Explicit named presenters in archived descriptions. These are participation,
# never evidence of incubation. Quotes are checked on every run.
PRESENTERS = ['IPRights4All', 'ValiCor US', 'ACURE', 'N0S.AI', 'MiFido', 'Sentype',
              'Countacus', 'Nova Hospitality', 'Caldarium', 'Open Judgement Engineering']


def key(text):
    return hashlib.sha256(text.encode()).hexdigest()[:24]


def classify(title, description):
    if EXCLUSIONS.search(title):
        return 'excluded'
    for category, pattern in RULES:
        if re.search(pattern, title, re.I):
            return category
    if re.search(r'\baccelerators\b', title, re.I) and re.search(r'startup|founder', description, re.I):
        return 'program_workshop'
    # Descriptions recover competitions hidden behind generic event names.
    if re.search(r'pitch competition|demo day|startup showcase|venture competition', description, re.I):
        return 'description_match'
    return None


def export(db, table, directory):
    rows = db.execute(f'SELECT * FROM {table} ORDER BY 1')
    with (directory / f'{table}.csv').open('w', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow([column[0] for column in rows.description])
        writer.writerows(rows)


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, default=root / 'baltimore/event_history.report.json')
    parser.add_argument('--events', type=Path, default=root / 'baltimore/event_history.json')
    parser.add_argument('--output', type=Path, default=root / 'baltimore/incubation_history')
    args = parser.parse_args()
    report = json.loads(args.report.read_text())
    events = json.loads(args.events.read_text())
    provenance = {row['output_index']: row for row in report['events']}
    if len(events) != report['unique_events'] or set(provenance) != set(range(len(events))):
        raise ValueError('Report and event history do not align')
    args.output.mkdir(parents=True, exist_ok=True)
    # Build separately, then replace only this generated artifact.
    temporary = args.output / 'research.tmp.sqlite'
    temporary.unlink(missing_ok=True)
    db = sqlite3.connect(temporary)
    db.execute('PRAGMA foreign_keys=ON')
    db.executescript('''
    CREATE TABLE organizations (
      research_id TEXT PRIMARY KEY, name TEXT NOT NULL, city TEXT NOT NULL DEFAULT '',
      source_url TEXT NOT NULL DEFAULT '', portal_organization_id TEXT,
      review_status TEXT NOT NULL DEFAULT 'needs_identity_review');
    CREATE TABLE events (
      research_id TEXT PRIMARY KEY, output_index INTEGER NOT NULL UNIQUE, title TEXT NOT NULL,
      category TEXT NOT NULL, starts_at TEXT, source_url TEXT, organizer_label TEXT,
      organizer_source_url TEXT, organizer_review TEXT, city TEXT, description TEXT,
      first_seen_commit TEXT, latest_record_commit TEXT, latest_record_path TEXT,
      recipient_review TEXT NOT NULL);
    CREATE TABLE event_organizations (
      event_id TEXT NOT NULL REFERENCES events(research_id),
      organization_id TEXT NOT NULL REFERENCES organizations(research_id),
      role TEXT NOT NULL CHECK(role IN ('participant','accelerator','supporter')),
      evidence TEXT NOT NULL, PRIMARY KEY(event_id,organization_id,role));
    CREATE TABLE support_candidates (
      research_id TEXT PRIMARY KEY,
      sponsor_id TEXT NOT NULL REFERENCES organizations(research_id),
      recipient_id TEXT NOT NULL REFERENCES organizations(research_id),
      support_kind TEXT NOT NULL CHECK(support_kind IN ('acceleration','incubation')),
      event_id TEXT NOT NULL REFERENCES events(research_id), source_url TEXT NOT NULL,
      occurred_at TEXT NOT NULL, evidence TEXT NOT NULL,
      review_status TEXT NOT NULL DEFAULT 'needs_portal_id_and_evidence_review',
      UNIQUE(sponsor_id,recipient_id,support_kind,event_id), CHECK(sponsor_id != recipient_id));
    CREATE INDEX support_by_sponsor ON support_candidates(sponsor_id,recipient_id);
    CREATE INDEX support_by_recipient ON support_candidates(recipient_id,sponsor_id);
    CREATE INDEX events_by_category ON events(category,starts_at);
    ''')

    def organization(name, city='', source=''):
        identity = key(name.casefold() + '|' + city.casefold())
        db.execute('INSERT OR IGNORE INTO organizations(research_id,name,city,source_url) VALUES(?,?,?,?)',
                   (identity, name, city, source))
        return identity

    def associate(event_id, name, role, evidence, city='', source=''):
        oid = organization(name, city, source)
        db.execute('INSERT OR IGNORE INTO event_organizations VALUES(?,?,?,?)', (event_id, oid, role, evidence))
        return oid

    for index, event in enumerate(events):
        title = html.unescape(event.get('name') or '')
        description = html.unescape(event.get('description') or '')
        category = classify(title, description)
        if category is None:
            continue
        eid = key(str(index) + '|' + (event.get('url') or title))
        origin = event.get('source_url') or event.get('source') or ''
        label = event.get('org_name') or event.get('orgName') or ''
        hostname = urlparse(origin).hostname or ''
        ambiguous = not label or label in PROVIDERS or label == hostname
        city = (event.get('location') or {}).get('city') or event.get('city') or ''
        p = provenance[index]
        db.execute('INSERT INTO events VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                   (eid,index,title,category,event.get('startDate'),event.get('url'),label,origin,
                    'needs_organizer_review' if ambiguous else 'source_label_only',city,description,
                    p['first_seen_commit'],p['latest_record_commit'],p['latest_record_path'],
                    'named_participants' if any(n in description for n in PRESENTERS) or '• AidRx (' in description else 'needs_recipient_research'))
        if category == 'excluded':
            continue
        if title.startswith('Pitch Labs') and 'https://www.gingercybersecurity.com/' in description:
            associate(eid, 'Ginger Cybersecurity', 'participant', 'Kaitlin Seng: https://www.gingercybersecurity.com/')
        for name in PRESENTERS:
            if name in description and title.startswith('Pitch Labs'):
                line = next(line for line in description.splitlines() if name in line)
                associate(eid,name,'participant',line)
        # Strictly anchored cohort list: no guessing recipients from counts or speakers.
        if 'Techstars AI Health Baltimore' in title and 'Spring 2025 cohort' in description:
            sponsor = associate(eid,'Techstars AI Health Baltimore','accelerator',
                                'Techstars AI Health Baltimore Spring 2025 cohort', 'Baltimore', origin)
            for match in re.finditer(r'^• ([^\n(]+) \(([^\n]+)\)\s*$', description, re.M):
                name, location = match.groups()
                recipient = associate(eid,name.strip(),'participant',match.group(0).strip(),location)
                db.execute('INSERT INTO support_candidates(research_id,sponsor_id,recipient_id,support_kind,event_id,source_url,occurred_at,evidence) VALUES(?,?,?,?,?,?,?,?)',
                           (key(eid+'|'+recipient),sponsor,recipient,'acceleration',eid,event['url'],
                            event.get('startDate') or '', 'Spring 2025 cohort: '+match.group(0).strip()))
            for name in ['Johns Hopkins University','CareFirst BlueCross BlueShield','Brex']:
                line = next(line for line in description.splitlines() if name in line)
                associate(eid,name,'supporter',line)
        if 'Business Plan & Growth Readiness Incubator' in title:
            for name, role in [('Baltimore Development Corporation','accelerator'),('LISC','supporter'),('Verizon Small Business Digital Ready','supporter')]:
                if name in description:
                    associate(eid,name,role,description)
    db.commit()
    for table in ['events','organizations','event_organizations','support_candidates']:
        export(db, table, args.output)
    summary = {'source_report_sha256': hashlib.sha256(args.report.read_bytes()).hexdigest(),
               'source_events_sha256': hashlib.sha256(args.events.read_bytes()).hexdigest(),
               'events_scanned': len(events),
               'categories': dict(db.execute('SELECT category,count(*) FROM events GROUP BY category')),
               'organizations': db.execute('SELECT count(*) FROM organizations').fetchone()[0],
               'support_candidates': db.execute('SELECT count(*) FROM support_candidates').fetchone()[0],
               'production_writes': 0}
    (args.output / 'summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    assert not db.execute('PRAGMA foreign_key_check').fetchall()
    db.close()
    temporary.replace(args.output / 'research.sqlite')
    print(json.dumps(summary,indent=2))

if __name__ == '__main__':
    main()
