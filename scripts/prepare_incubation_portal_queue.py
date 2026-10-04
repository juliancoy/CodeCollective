#!/usr/bin/env python3
"""Resolve reviewed history candidates to existing OrgPortal IDs, without writing to the portal."""
import argparse
import csv
import json
import sqlite3
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, default=root / 'baltimore/incubation_history/research.sqlite')
    parser.add_argument('--identities', type=Path, required=True,
                        help='Reviewed CSV: research_id,portal_organization_id')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    db = sqlite3.connect(f'{args.database.resolve().as_uri()}?mode=ro', uri=True)
    db.row_factory = sqlite3.Row
    identities = {}
    with args.identities.open(newline='') as stream:
        for row in csv.DictReader(stream):
            rid, pid = row['research_id'], row['portal_organization_id'].strip()
            if rid in identities:
                raise ValueError(f'Duplicate research identity: {rid}')
            if not db.execute('SELECT 1 FROM organizations WHERE research_id=?', (rid,)).fetchone():
                raise ValueError(f'Unknown research identity: {rid}')
            if pid:
                identities[rid] = pid
    queue, unresolved = [], []
    for row in db.execute('SELECT * FROM support_candidates ORDER BY research_id'):
        source = identities.get(row['sponsor_id'])
        recipient = identities.get(row['recipient_id'])
        if not source or not recipient:
            unresolved.append(row['research_id'])
            continue
        if source == recipient:
            raise ValueError('Sponsor and recipient cannot map to the same organization')
        queue.append({'candidate_id': row['research_id'], 'tool': 'preview_organization_support', 'arguments': {
            'organizationId': source, 'recipientOrganizationId': recipient,
            'supportKind': row['support_kind'], 'description': 'Named participant in Techstars AI Health Baltimore Spring 2025 cohort',
            'occurredAt': row['occurred_at'], 'sourceUrl': row['source_url'], 'evidence': row['evidence'],
            'notes': 'Archived cohort evidence; occurredAt is the showcase date, not the start of support.',
            'status': 'reported',
        }})
    args.output.write_text(''.join(json.dumps(item)+'\n' for item in queue))
    print(json.dumps({'ready_for_preview': len(queue), 'unresolved_candidate_ids': unresolved, 'production_writes': 0}, indent=2))
    db.close()

if __name__ == '__main__':
    main()
