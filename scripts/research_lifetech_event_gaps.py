#!/usr/bin/env python3
"""Audit every imported event and collect sourced, flat enrichment candidates."""
import argparse
import csv
import difflib
import hashlib
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode, urlparse
import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
FIELDS = ['description','ends_at','location','image_url','host_org_name']
PROVIDERS = {'eventbrite.com','meetup.com','luma.com','lu.ma','api.lu.ma','tedcomd.com','members.mdtechcouncil.com'}


def write_csv(path, columns, rows):
    with path.open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=columns)
        writer.writeheader();writer.writerows(rows)


def normalized(value):
    return re.sub(r'[^a-z0-9]+',' ',str(value or '').casefold()).strip()


def instant(value):
    if not value:return None
    value=re.sub(r'([+-]\d{2})(\d{2})$',r'\1:\2',value.replace('Z','+00:00'))
    date=datetime.fromisoformat(value)
    if date.tzinfo is None:return None
    return date.timestamp()


def schema_events(value):
    if isinstance(value,list):
        for child in value:yield from schema_events(child)
    elif isinstance(value,dict):
        kind=value.get('@type',[]);kind=[kind] if isinstance(kind,str) else kind
        if any(str(item).endswith('Event') for item in kind):yield value
        if '@graph' in value:yield from schema_events(value['@graph'])


def location_text(location):
    if isinstance(location,str):return location
    if not isinstance(location,dict):return ''
    address=location.get('address')
    if isinstance(address,dict):address=', '.join(str(address.get(k) or '') for k in ['streetAddress','addressLocality','addressRegion','postalCode','addressCountry'] if address.get(k))
    return ', '.join(str(item) for item in [location.get('name'),address] if item)


def fetch_source(url):
    row={'source_url':url,'final_url':'','http_status':'','retrieved_at':datetime.now(timezone.utc).isoformat(),
         'content_sha256':'','page_title':'','source_excerpt':'','fetch_status':''}
    objects=[]
    try:
        with requests.get(url,timeout=(5,12),stream=True,headers={'User-Agent':'LifeTech event research (public source verification)'}) as response:
            row['http_status']=response.status_code;row['final_url']=response.url
            if response.status_code!=200:
                row['fetch_status']='unavailable';return row,objects
            if 'html' not in response.headers.get('content-type',''):
                row['fetch_status']='non_html';return row,objects
            content=bytearray()
            for chunk in response.iter_content(16384):
                content.extend(chunk)
                if len(content)>1500000:break
            row['content_sha256']=hashlib.sha256(content).hexdigest()
            soup=BeautifulSoup(bytes(content),'html.parser')
            row['page_title']=soup.title.get_text(' ',strip=True)[:250] if soup.title else ''
            description=soup.find('meta',attrs={'name':'description'}) or soup.find('meta',attrs={'property':'og:description'})
            if description:row['source_excerpt']=' '.join(description.get('content','').split()[:20])
            for node in soup.find_all('script',attrs={'type':'application/ld+json'}):
                try:objects.extend(schema_events(json.loads(node.string or node.get_text())))
                except (ValueError,TypeError):continue
            row['fetch_status']='structured_events_found' if objects else 'no_structured_event_data'
    except requests.RequestException as error:
        row['fetch_status']='fetch_failed:'+type(error).__name__
    return row,objects


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline',type=Path,default=ROOT/'baltimore/incubation_history/live-receipt/enrichment-baseline.json')
    parser.add_argument('--output',type=Path,default=ROOT/'baltimore/incubation_history/enrichment')
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    events=json.loads(args.baseline.read_text());tasks=[];sources=[];candidates=[]
    for event in events:
        gaps=[field for field in FIELDS if not event.get(field)]
        desc=event.get('description') or ''
        if desc and (normalized(desc)==normalized(event['title']) or len(desc)<100):gaps.append('description_detail')
        host=event.get('host_org_name') or ''
        if host in PROVIDERS or host.startswith('Luma User ') or host.startswith('Google Developer Group Chapter '):gaps.append('organizer_identity')
        for field in gaps+['named_participants','supporter_relationships']:
            query=f'"{event["title"]}" {str(event.get("starts_at") or "")[:10]} '+('cohort companies participants' if field=='named_participants' else 'sponsors supporting organizations' if field=='supporter_relationships' else field.replace('_',' '))
            tasks.append({'event_id':event['id'],'event_slug':event['slug'],'title':event['title'],'starts_at':event.get('starts_at'),
                          'field':field,'query':query,'search_url':'https://www.google.com/search?'+urlencode({'q':query}),'status':'needs_research'})
    urls=sorted({event['source_url'] for event in events if event.get('source_url')})
    indexed={}
    with ThreadPoolExecutor(max_workers=6) as executor:
        pending={executor.submit(fetch_source,url):url for url in urls}
        for future in as_completed(pending):
            source,objects=future.result();sources.append(source);indexed[source['source_url']]=objects
            if len(sources)%15==0:print(f'Checked {len(sources)}/{len(urls)} source pages',flush=True)
    for event in events:
        for obj in indexed.get(event.get('source_url'),[]):
            score=difflib.SequenceMatcher(None,normalized(event['title']),normalized(obj.get('name'))).ratio()
            try:date_match=instant(event.get('starts_at'))==instant(obj.get('startDate')) and instant(obj.get('startDate')) is not None
            except (ValueError,TypeError):date_match=False
            if score<.55:continue
            organizer=obj.get('organizer') or {};organizer=organizer[0] if isinstance(organizer,list) and organizer else organizer
            image=obj.get('image');image=image[0] if isinstance(image,list) and image else image
            if isinstance(image,dict):image=image.get('url') or image.get('contentUrl')
            proposed={'starts_at':obj.get('startDate'),'ends_at':obj.get('endDate'),'location':location_text(obj.get('location')),
                      'image_url':image,'host_org_name':organizer.get('name') if isinstance(organizer,dict) else organizer}
            for field,value in proposed.items():
                if not isinstance(value,str) or not value.strip() or value==event.get(field):continue
                candidates.append({'event_id':event['id'],'event_slug':event['slug'],'field':field,'current_value':event.get(field) or '',
                                   'proposed_value':value,'source_url':event['source_url'],'evidence_type':'Event JSON-LD',
                                   'title_similarity':round(score,3),'start_instant_matches':date_match,
                                   'review_status':'needs_review' if date_match else 'needs_date_or_identity_review'})
    write_csv(args.output/'research_tasks.csv',['event_id','event_slug','title','starts_at','field','query','search_url','status'],tasks)
    write_csv(args.output/'sources.csv',list(sources[0]) if sources else ['source_url'],sorted(sources,key=lambda row:row['source_url']))
    write_csv(args.output/'event_field_candidates.csv',['event_id','event_slug','field','current_value','proposed_value','source_url','evidence_type','title_similarity','start_instant_matches','review_status'],candidates)
    summary={'events_audited':len(events),'original_source_pages_checked':len(urls),'source_fetch_results':{},'research_tasks':len(tasks),
             'structured_field_candidates':len(candidates),'live_writes':0}
    for row in sources:summary['source_fetch_results'][row['fetch_status']]=summary['source_fetch_results'].get(row['fetch_status'],0)+1
    (args.output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
