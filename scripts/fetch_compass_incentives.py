#!/usr/bin/env python3
"""Archive every publicly listed Compass incentive and all detail fields."""
import csv,gzip,io,json,time,hashlib,threading
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
import requests
OUT=Path(__file__).resolve().parents[1]/'baltimore/incubation_history/enrichment/compass'
BASE='https://compass.maryland.gov/api/v1/incentives/'
LOCAL=threading.local()
def get(url):
 if not hasattr(LOCAL,'session'):LOCAL.session=requests.Session();LOCAL.session.headers['User-Agent']='LifeTech public funding research (compass archive)'
 for attempt in range(7):
  try:
   r=LOCAL.session.get(url,timeout=60)
   if r.status_code in (429,500,502,503,504):time.sleep(min(60,2**attempt));continue
   r.raise_for_status();return r
  except requests.RequestException:
   if attempt==6:raise
   time.sleep(min(30,2**attempt))
 raise RuntimeError('Retries exhausted: '+url)
def main():
 OUT.mkdir(parents=True,exist_ok=True)
 export=get(BASE+'csv/');export.encoding='utf-8-sig';(OUT/'source-export.csv').write_text(export.text)
 rows=list(csv.DictReader(io.StringIO(export.text)));slugs=[r['compass_link'].rsplit('/',1)[-1] for r in rows];assert len(set(slugs))==len(rows)
 first=get(BASE).json();assert first['count']==len(slugs),(first['count'],len(slugs))
 html=get('https://compass.maryland.gov/incentives/');html.encoding='utf-8';(OUT/'source-page.html').write_text(html.text)
 (OUT/'featured.json').write_text(json.dumps(get(BASE+'featured/').json(),ensure_ascii=False,indent=2)+'\n')
 archive=OUT/'source-details.jsonl';details={}
 if not archive.exists() and Path(str(archive)+'.gz').exists():archive.write_bytes(gzip.open(str(archive)+'.gz','rb').read())
 if archive.exists():
  for line in archive.read_text().splitlines():
   r=json.loads(line);details[r['slug']]=r
 pending=[slug for slug in slugs if slug not in details]
 def detail(slug):
  r=get(BASE+slug+'/').json();assert r['slug']==slug;return r
 print(json.dumps({'listed':len(rows),'already_archived':len(details),'pending':len(pending)}),flush=True)
 with archive.open('a') as f,ThreadPoolExecutor(max_workers=4) as pool:
  futures={pool.submit(detail,slug):slug for slug in pending}
  for done in as_completed(futures):
   r=done.result();f.write(json.dumps(r,ensure_ascii=False)+'\n');f.flush();details[r['slug']]=r
   if len(details)%100==0:print(json.dumps({'archived':len(details),'total':len(slugs)}),flush=True)
 assert set(slugs)<=set(details)
 # Sorted complete snapshot excludes stale records left in a resume archive.
 (OUT/'source-details.jsonl').write_text(''.join(json.dumps(details[s],ensure_ascii=False)+'\n' for s in sorted(slugs)))
 summary={'source':'https://compass.maryland.gov/incentives/','retrieved_date':'2026-10-06','listed_programs':len(slugs),'detail_records':len(slugs),'detail_fields':sorted({k for s in slugs for k in details[s]}),'detail_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'scope':'All publicly listed default-filter results and their detail endpoints; source UI/API excludes low-quality and discontinued entries.'}
 (OUT/'fetch-summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary),flush=True)
if __name__=='__main__':main()
