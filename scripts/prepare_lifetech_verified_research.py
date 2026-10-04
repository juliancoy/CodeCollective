#!/usr/bin/env python3
"""Regenerate flat, source-grounded research candidates; never writes to OrgPortal."""
import csv
import hashlib
import json
import sqlite3
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'baltimore/incubation_history/enrichment'
SOURCES={
 'techstars_spring':'https://www.techstars.com/newsroom/techstars-ai-health-baltimore-2025-class-announcement',
 'techstars_fall':'https://www.techstars.com/blog/impact/techstars-update-december-2025',
 'techstars_event':'https://ventures.jhu.edu/event/techstars-ai-health-baltimore-demo-day/',
 'loyola':'https://www.loyola.edu/news/2026/0309-baltipreneurs-accelerator-demo-day.html',
 'loyola_awards':'https://www.loyola.edu/join-us/baltipreneurs/demo-day/',
 'cyber':'https://howardcountyeda.org/business-resources/cyber-howard/cyber-cohort/',
 'ubalt_ai':'https://www.ubalt.edu/about/newsroom/business-today-cei-artificial-intelligence-accelerator-showcases-real-world-solutions.cfm',
 'newventure':'https://bwtech.umbc.edu/maryland-new-venture-cohort-6-celebrates-at-pitch-night-26/',
 'cbic':'https://entrepreneurship.umbc.edu/competitions/the-cangialosi-business-innovation-competition/2026-cbic/',
 'rise':'https://www.ubalt.edu/about/newsroom/ubaltnews-winners-announced-for-2026-rise-to-the-challenge-competition.cfm',
}
GROUPS=[
 ('Techstars AI Health Baltimore','2025 spring','2025-06-05','Techstars','acceleration','techstars_spring','AidRx|Behaivior|Compose Health|Embryoxite|Galen Health|Opal|Sloop|Valio'),
 ('Techstars AI Health Baltimore','2025 fall','2025-12-04','Techstars','acceleration','techstars_fall','Altrix|Birth Model|BlueStamp Health|CodaHx|Halsted AI|Hoopcare|Pense Health|PromptWrx|TechNovaTime'),
 ('Baltipreneurs','2026','2026-03-19','Loyola University Maryland','acceleration','loyola','ACC Industries|BioBuild|Cajou Creamery|Coach G Academy|Dr. Heather Lamb Consulting|Kinnected Care|Our House Baltimore|Rhodex|Rooted Rotisserie|Smooth Contracting LLC|Wight Tea Co.'),
 ('Cyber Howard','II','2026-01-27','Howard County Economic Development Authority','acceleration','cyber','Bolt Technologies, LLC|Insight Cyber Solutions LLC|Mimir Security Inc.|MKJHA Consulting, Inc.|Omegus Prime, LLC|TandT LLC|ThreatShareAI'),
 ('Cyber Howard','III','2026-07-16','Howard County Economic Development Authority','acceleration','cyber','Artemion|Cipher|CyborgUSA|Nunsys|Phanium|River|VigilVector'),
 ('UBalt AI-Enabled Business Accelerator','2026 inaugural','2026-03-17','University of Baltimore','acceleration','ubalt_ai','HealthLink360|SphereHub|Alektra Inc.|NextGenEdu|Brick Rose Exchange|Stacks Data|Pulse|Sommos'),
 ('Maryland NEW VENTURE','6','2026-05-11','bwtech@UMBC','program_participation','newventure','Esurgi, Inc.|PocketCardio|Think Happy. Live Happy.|iBraid|MicDots Global|VigilVector'),
]
def ident(name):return hashlib.sha256(name.casefold().encode()).hexdigest()[:24]
def write(name,cols,rows):
 with (OUT/name).open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=cols);w.writeheader();w.writerows(rows)
def main():
 events=json.loads((OUT.parent/'live-receipt/enrichment-baseline.json').read_text())
 entities={};relations=[];participation=[];awards=[];facts=[]
 def entity(name,kind='venture'):
  key=ident(name);entities.setdefault(key,dict(entity_id=key,name=name,entity_kind=kind,portal_org_id='',identity_status='needs_identity_match'));return key
 for program,cohort,date,supporter,kind,source,names in GROUPS:
  matched=[e for e in events if e['starts_at'][:10]==date and (('techstars' in e['title'].lower()) if program.startswith('Techstars') else ('cyber howard' in e['title'].lower()) if program=='Cyber Howard' else ('baltipreneur' in e['title'].lower()) if program=='Baltipreneurs' else ('ai-enabled' in e['title'].lower()) if program.startswith('UBalt') else ('new venture' in e['title'].lower()))]
  assert matched,(program,date)
  for name in names.split('|'):
   recipient=entity(name);giver=entity(supporter,'supporting_organization')
   relations.append(dict(recipient_entity_id=recipient,supporter_entity_id=giver,relationship_kind=kind,program=program,cohort=cohort,source_id=source,status='evidence_found_needs_portal_preview'))
   for e in matched:participation.append(dict(event_id=e['id'],entity_id=recipient,role='cohort_member',source_id=source,status='identity_match_required'))
 def award(date,name,label,amount,source):
  token={'cbic':'cangialosi','rise':'rise to the challenge','loyola_awards':'baltipreneurs'}[source]
  matched=[e for e in events if e['starts_at'][:10]==date and token in e['title'].lower()];assert len(matched)==1,(date,len(matched))
  awards.append(dict(event_id=matched[0]['id'],recipient_entity_id=entity(name),award=label,amount=amount,currency='USD' if amount else '',source_id=source,status='published_award_not_payment'))
 for name,label,amount in [('RepTrack Pro','Technology first',4000),('Quick Dx','Technology second',2000),('C3D Works','Technology third',1000),('Shamsa','Social impact first',4000),('Lay Your Bricks','Social impact second',2000),('Zen-Air','Social impact third',1000),('A-Eye Vision','Audience choice',300)]:award('2026-04-16',name,label,amount,'cbic')
 for name,label,amount in [('Totem Jou Publishing','Most promising business (shared $20,000 pool)',''),('Pharmynx','Most promising business (shared $20,000 pool)',''),("Keepin’ Up with the Jones’ Hair Care",'Existing business',5000),("K’Raw Juice",'Aspiring venture',2500),("K’Raw Juice",'PitchCreator Hustle',1000),('Steady Hands','Baltimore Fund',''),('BLUE DREAM','Most innovative',3000),('Totem Jou Publishing','Crowd favorite',1000)]:award('2026-05-06',name,label,amount,'rise')
 for name,label in [('ACC Industries','Impact'),('Rooted Rotisserie','Breakthrough'),('Rooted Rotisserie','Audience choice'),('Our House Baltimore','Peerless'),('BioBuild','Greyhound')]:award('2026-03-19',name,label,'','loyola_awards')
 for sponsor in ['TEDCO','PNC Bank','Gordon Feinblatt LLC','Command 31']:
  facts.append(dict(subject_entity_id=entity(sponsor,'supporting_organization'),field='sponsors_program',value='Baltipreneurs 2026',source_id='loyola_awards',status='program_support_only'))
 write('verified_sources.csv',['source_id','url','publisher_type','checked_on'],[dict(source_id=k,url=v,publisher_type='primary',checked_on='2026-10-04') for k,v in SOURCES.items()])
 write('entities.csv',list(next(iter(entities.values()))),entities.values())
 for filename,rows in [('cohort_relationship_candidates.csv',relations),('verified_event_participants.csv',participation),('published_awards.csv',awards),('organization_facts.csv',facts)]:write(filename,list(rows[0]),rows)
 conflicts=[dict(subject='Techstars spring 2025',issue='Announcement states nine then eight; eight companies named.',resolution='Use named list; total remains disputed.',source_id='techstars_spring'),dict(subject='Techstars December 2025 demo',issue='Pava listing header December 5 disagrees with body December 4; archive starts 17:30 while JHTV publishes 17:00.',resolution='JHTV corroborates December 4, 17:00-20:00; stage correction for review.',source_id='techstars_event'),dict(subject='UBalt Rise 2026 awards',issue='Earlier advertising says $30,000; recap says over $35,000; shared $20,000 award lacks individual allocations.',resolution='Use individual published awards; leave shared recipient amounts blank.',source_id='rise'),dict(subject='Maryland NEW VENTURE',issue='Two live records have identical date and similar title.',resolution='Flag possible duplicate; do not merge without portal review.',source_id='newventure'),dict(subject='Alektra Inc.',issue='Published link spelling differs from company name.',resolution='Leave website and legal identity unverified.',source_id='ubalt_ai')]
 write('conflicts.csv',list(conflicts[0]),conflicts)
 covered={r['event_id'] for r in participation}|{r['event_id'] for r in awards}
 write('event_research_coverage.csv',['event_id','title','status'],[dict(event_id=e['id'],title=e['title'],status='primary_evidence_found_partial' if e['id'] in covered else 'search_queue_prepared') for e in events])
 db=sqlite3.connect(OUT/'verified_research.sqlite');db.execute('PRAGMA foreign_keys=ON')
 for table,file in [('sources','verified_sources.csv'),('entities','entities.csv'),('relations','cohort_relationship_candidates.csv'),('participants','verified_event_participants.csv'),('awards','published_awards.csv'),('facts','organization_facts.csv'),('conflicts','conflicts.csv'),('coverage','event_research_coverage.csv')]:
  with (OUT/file).open() as f:
   reader=csv.DictReader(f);cols=reader.fieldnames;rows=list(reader)
  db.execute(f'DROP TABLE IF EXISTS {table}');db.execute(f'CREATE TABLE {table} ('+','.join(f'"{c}" TEXT' for c in cols)+')')
  db.executemany(f'INSERT INTO {table} VALUES ('+','.join('?' for c in cols)+')',[[r[c] for c in cols] for r in rows])
 db.commit();db.close()
 summary=dict(events_audited=len(events),events_with_primary_participant_or_award_evidence=len(covered),entities=len(entities),cohort_relationship_candidates=len(relations),published_awards=len(awards),primary_sources=len(SOURCES),live_writes=0)
 (OUT/'verified_summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary))
if __name__=='__main__':main()
