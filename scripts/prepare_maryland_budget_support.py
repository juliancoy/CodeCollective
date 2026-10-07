#!/usr/bin/env python3
"""Prepare flat, idempotent public-evidence inserts; never create payments.

Requires a read-only Wrangler organizations export via --organizations.
Downloads the official report, extracts only four organizational programs from
Appendix C, and preserves source rows. Appendix B repeats are never imported.
"""
import argparse, csv, hashlib, json, re, subprocess, tempfile
from pathlib import Path
from decimal import Decimal
import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'baltimore/incubation_history/enrichment/maryland_budget'
REPORT = 'https://energy.maryland.gov/Reports/FY25%20SEIF%20Volume%202_%20Appendices%20B%20and%20C%20-%20Appendix%20C-combined-compressed.pdf'
BUDGET = 'https://msa.maryland.gov/msa/mdmanual/25ind/html/71techb.html'
PROGRAMS = {
    'Energy Efficiency Equity Grant Program': 39,
    'Mechanical Insulation': 2,
    'Affordable Electrification Outreach Program': 4,
    'Higher Education Green Energy Initiatives': 11,
}
ALIASES = {
    'University of Maryland Baltimore': 'org-university-of-maryland-baltimore-um-ventures',
    'University of Maryland Baltimore County': 'org-university-of-maryland-baltimore-county',
    'Loyola University Maryland, Inc': 'registry-15b90573-63a1-4620-9bb7-38c38d74f9a8',
}
def key(s):
    return re.sub(r'[^a-z0-9]', '', re.sub(r'\b(inc|incorporated|llc)\b', '', s.lower()))
def sql(s):
    return 'NULL' if s is None else "'" + str(s).replace("'", "''") + "'"
def write_csv(name, rows):
    with (OUT/name).open('w') as f:
        w=csv.DictWriter(f, fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def main():
    p=argparse.ArgumentParser();p.add_argument('--organizations',type=Path,required=True)
    args=p.parse_args();OUT.mkdir(parents=True,exist_ok=True)
    existing=json.loads(args.organizations.read_text())[0]['results']
    byid={o['id']:o for o in existing};bykey={}
    for o in existing: bykey.setdefault(key(o['name']),[]).append(o)
    new={}
    def organization(name, category='ecosystem', website=REPORT):
        if name in ALIASES:
            assert ALIASES[name] in byid
            return ALIASES[name]
        matches=bykey.get(key(name),[])
        if len(matches)>1: raise ValueError('Ambiguous organization: '+name)
        if matches: return matches[0]['id']
        slug=re.sub(r'[^a-z0-9]+','-',name.lower()).strip('-')
        oid='md-budget:'+slug
        new[oid]={'id':oid,'name':name,'slug':slug,'description':'Public Maryland budget / SEIF evidence organization; no membership or permissions granted.','source_url':website,'tags':json.dumps([category,'LifeTech','Maryland budget research'])}
        return oid
    mea=organization('Maryland Energy Administration','state-government','https://energy.maryland.gov/')
    state=organization('State of Maryland','state-government','https://www.maryland.gov/')
    fund=organization('Maryland Strategic Energy Investment Fund','funding','https://energy.maryland.gov/Pages/Strategic-Energy-Investment-Fund-(SEIF)-.aspx')
    records=[]
    def add(**r):
        r['fiscal_year']=2025 if r['support_kind']=='transfer' else (int(re.search(r'FY(\d{4})',r['description'])[1]) if r['support_kind']=='terms' else '')
        r['record_class']='announced award' if r['support_kind']=='transfer' else (r['amount_label'] if r['support_kind']=='terms' else 'administration')
        identity='|'.join(str(r.get(k,'')) for k in ['from_organization_id','to_organization_id','description','amount','source_url','source_page','source_row'])
        records.append({'id':'md-budget:'+hashlib.sha256(identity.encode()).hexdigest()[:24],**r})
    with tempfile.TemporaryDirectory() as d:
        pdf=Path(d)/'report.pdf';txt=Path(d)/'report.txt'
        response=requests.get(REPORT,timeout=120);response.raise_for_status();pdf.write_bytes(response.content)
        subprocess.run(['pdftotext','-layout',str(pdf),str(txt)],check=True)
        pages=txt.read_text().split('\f');counts=dict.fromkeys(PROGRAMS,0)
        for page_no,page in enumerate(pages,1):
            if page_no<40: continue
            for row_no,line in enumerate(page.splitlines(),1):
                line=line.strip()
                for program in PROGRAMS:
                    m=re.match(r'^[MOPQ]\s+'+re.escape(program)+r'\s*(.*?)\s+\$([\d,]+\.\d{2})\s*$',line)
                    if not m: continue
                    name=m[1].strip();amount=str(Decimal(m[2].replace(',','')))
                    category='university' if program.startswith('Higher Education') else ('health' if 'Medical Center' in name else 'ecosystem')
                    recipient=organization(name,category)
                    counts[program]+=1
                    add(from_organization_id=mea,to_organization_id=recipient,from_label='Maryland Energy Administration',to_label=name,support_kind='transfer',amount=amount,currency='USD',amount_label='reported award',description=f'FY2025 SEIF award — {program}',occurred_at='',source_url=REPORT+f'#page={page_no}',source_page=page_no,source_row=row_no,evidence=f'Appendix C, PDF page {page_no}, row {row_no}: {line}',notes='Record class: announced award. Fiscal year: 2025 (2024-07-01 through 2025-06-30). Funding source: Strategic Energy Investment Fund (SEIF); administrator/awarding agency: MEA. Exact award date and payment/settlement are unverified. Appendix B duplicates and aggregate program totals excluded. Source program letter may be inconsistent; program name retained.',status='reported')
        assert counts==PROGRAMS,(counts,PROGRAMS)
    # Budget figures are agency-wide context, not recipient-level transfers.
    budget_response=requests.get(BUDGET,timeout=30);budget_response.raise_for_status()
    for fy,amount,classification in [(2020,25985582,'actual expenditure aggregate'),(2021,26974480,'actual expenditure aggregate'),(2022,21100021,'actual expenditure aggregate'),(2023,50754979,'actual expenditure aggregate'),(2024,54715816,'actual expenditure aggregate'),(2025,52610816,'actual expenditure aggregate'),(2026,53456649,'appropriation'),(2027,67793984,'appropriation')]:
        assert f'${amount:,}' in budget_response.text, f'Budget source changed: FY{fy}'
        add(from_organization_id=state,to_organization_id='org-tedco',from_label='State of Maryland',to_label='TEDCO',support_kind='terms',amount=str(amount),currency='USD',amount_label=classification,description=f'FY{fy} TEDCO total agency budget — {classification}',occurred_at='',source_url=BUDGET,source_page='',source_row='',evidence=f'Maryland State Archives budget table, T50T01, FY{fy} Total Funds: USD {amount:,}; classification: {classification}.',notes=f'Record class: {classification}. Fiscal year: {fy}. Agency-wide general/special/federal total; source does not identify individual payers or recipient grants. Context only: excluded from money-transfer graph; do not sum with fund components or recipient awards. Fiscal-year precision only; no payment date inferred.',status='reported')
    add(from_organization_id=mea,to_organization_id=fund,from_label='Maryland Energy Administration',to_label='Maryland Strategic Energy Investment Fund',support_kind='affiliation',amount=None,currency=None,amount_label='',description='MEA administers the Strategic Energy Investment Fund',occurred_at='',source_url='https://energy.maryland.gov/Pages/Strategic-Energy-Investment-Fund-(SEIF)-.aspx',source_page='',source_row='',evidence='Official SEIF page identifies MEA as administrator and monitor of SEIF-funded programs.',notes='Administrative relationship; no financial transfer or fund balance inferred.',status='reported')
    write_csv('organizations.csv',list(new.values()));write_csv('records.csv',records)
    statements=['-- Public evidence only; flat rows, no payments, memberships or permissions.']
    for o in new.values():
        cols=list(o);statements.append('INSERT INTO organizations ('+','.join(cols)+') VALUES ('+','.join(sql(o[k]) for k in cols)+') ON CONFLICT(id) DO NOTHING;')
    cols=[k for k in records[0] if k not in ('source_page','source_row','fiscal_year','record_class')]
    for r in records:
        statements.append('INSERT INTO organization_support_records ('+','.join(cols)+',created_at) VALUES ('+','.join(sql(r[k]) for k in cols)+",strftime('%Y-%m-%dT%H:%M:%fZ','now')) ON CONFLICT(id) DO NOTHING;")
    (OUT/'apply.sql').write_text('\n'.join(statements)+'\n')
    summary={'new_organizations':len(new),'reported_awards':sum(counts.values()),'award_total_usd':str(sum(Decimal(r['amount']) for r in records if r['support_kind']=='transfer')),'budget_context_records':8,'administrative_relationships':1,'settlements_created':0,'programs':counts,'source_report_sha256':hashlib.sha256(response.content).hexdigest()}
    (OUT/'preparation-summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary))
if __name__=='__main__':main()
