#!/usr/bin/env python3
"""Verified daily database and ecosystem-source backup; never restores production."""
import datetime, fcntl, gzip, hashlib, json, os, pathlib, shutil, sqlite3, subprocess, tarfile, tempfile
root=pathlib.Path(__file__).resolve().parents[1]
org=root.parent/'OrgPortal'
worker=org/'org-worker'
backup_root=pathlib.Path(os.environ.get('ECOSYSTEM_BACKUP_DIR',str(pathlib.Path.home()/'.local/share/codecollective-backups')))
bucket=os.environ.get('ECOSYSTEM_BACKUP_BUCKET','codecollective-ecosystem-backups')
os.umask(0o077);backup_root.mkdir(parents=True,exist_ok=True)
lock=(backup_root/'.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
now=datetime.datetime.now(datetime.timezone.utc);stamp=now.strftime('%Y-%m-%dT%H-%M-%SZ')
node=os.environ.get('ECOSYSTEM_NODE',str(pathlib.Path.home()/'.nvm/versions/node/v24.16.0/bin/node'))
wrangler=[node,str(worker/'node_modules/wrangler/bin/wrangler.js')]
def run(args):
 result=subprocess.run(args,cwd=worker,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=600)
 if result.returncode:raise RuntimeError(f'Backup command failed ({result.returncode}); signed download URLs are withheld')
with tempfile.TemporaryDirectory(prefix='.pending-',dir=backup_root) as tmp:
 temp=pathlib.Path(tmp);sql=temp/'production.sql'
 if os.environ.get('ECOSYSTEM_RESUME_EXPORT'):shutil.copyfile(os.environ['ECOSYSTEM_RESUME_EXPORT'],sql)
 else:run(wrangler+['d1','export','org','--remote','--output',str(sql)])
 # A successful export alone is not restore proof. Rebuild a disposable SQLite DB.
 connection=sqlite3.connect(temp/'restore-check.sqlite')
 connection.executescript('BEGIN;\n'+sql.read_text()+'\nCOMMIT;')
 result=connection.execute('PRAGMA integrity_check').fetchone()[0]
 if result!='ok':raise RuntimeError('Backup failed SQLite integrity check')
 tables={row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
 required={'organizations','events','organization_support_records','ledger_transactions'}
 if not required<=tables:raise RuntimeError('Backup is missing required transactional tables')
 counts={table:connection.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0] for table in sorted(required)}
 connection.close()
 local_backups=[]
 # SQLite's backup API takes a consistent copy even while Wrangler is running.
 containers=json.loads(subprocess.check_output(['docker','ps','-q'],text=True).strip() and subprocess.check_output(['docker','inspect',*subprocess.check_output(['docker','ps','-q'],text=True).split()],text=True) or '[]')
 for container in containers:
  mounts=container.get('Mounts',[])
  if not any(m['Destination']=='/app' and pathlib.Path(m['Source']).resolve()==worker.resolve() for m in mounts):continue
  if not any(m['Destination']=='/app/.wrangler' for m in mounts):continue
  code="""import {DatabaseSync,backup} from 'node:sqlite';import fs from 'node:fs';import path from 'node:path';
const folder=fs.mkdtempSync('/tmp/orgportal-ecosystem-backup-');
async function scan(dir){for(const entry of fs.readdirSync(dir,{withFileTypes:true})){const file=path.join(dir,entry.name);if(entry.isDirectory())await scan(file);else if(entry.name.endsWith('.sqlite')){const src=new DatabaseSync(file,{readOnly:true});try{await backup(src,path.join(folder,entry.name))}finally{src.close()}}}}
await scan('/app/.wrangler');console.log(folder);"""
  folder=subprocess.check_output(['docker','exec',container['Id'],'node','--disable-warning=ExperimentalWarning','--input-type=module','-e',code],text=True).strip()
  if not folder.startswith('/tmp/orgportal-ecosystem-backup-') or '/' in folder.removeprefix('/tmp/'):raise RuntimeError('Invalid container backup path')
  copied=temp/container['Name'].strip('/');copied.mkdir()
  subprocess.run(['docker','cp',container['Id']+':'+folder+'/.',str(copied)],check=True,stdout=subprocess.DEVNULL)
  subprocess.run(['docker','exec',container['Id'],'node','-e',"require('fs').rmSync(process.argv[1],{recursive:true})",folder],check=True)
  for source in copied.glob('*.sqlite'):
   target=temp/(container['Name'].strip('/')+'-'+source.name);source.rename(target)
   dst=sqlite3.connect(target)
   try:
    if dst.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise RuntimeError('Local SQLite backup failed integrity check')
   finally:dst.close()
   local_backups.append(target)

 sources=list((org/'web/public/ecosystem-data').glob('*.json'))
 sources+=list((root/'data/code-collective-history').glob('*.json'))
 sources+=list(root.glob('*/event_history.json'))+list(root.glob('*/manual_events.json'))+list(root.glob('*/upcoming_events.json'))+list(root.glob('upcoming_events.json'))
 manifest={'createdAt':now.isoformat(),'database':'org','restoreCheck':'SQLite integrity_check passed','rowCounts':counts,'files':{str(p.relative_to(root.parent)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},'sqlSha256':hashlib.sha256(sql.read_bytes()).hexdigest(),'localSqliteCopies':[p.name for p in local_backups]}
 (temp/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
 archive=backup_root/(stamp+'.tar.gz')
 with tarfile.open(archive,'w:gz') as tar:
  tar.add(sql,arcname='production.sql');tar.add(temp/'manifest.json',arcname='manifest.json')
  for local in local_backups:tar.add(local,arcname='local-sqlite/'+local.name)
  for source in sources:tar.add(source,arcname='sources/'+str(source.relative_to(root.parent)))
 digest=hashlib.sha256(archive.read_bytes()).hexdigest()
 run(wrangler+['r2','object','put',bucket+'/'+archive.name,'--file',str(archive),'--remote'])
 downloaded=temp/'r2-verification.tar.gz'
 run(wrangler+['r2','object','get',bucket+'/'+archive.name,'--file',str(downloaded),'--remote'])
 if hashlib.sha256(downloaded.read_bytes()).hexdigest()!=digest:raise RuntimeError('Off-device backup hash verification failed')
 receipt={'createdAt':now.isoformat(),'archive':str(archive),'r2Object':bucket+'/'+archive.name,'sha256':digest,'restoreCheck':manifest['restoreCheck'],'rowCounts':counts,'localSqliteCopies':[p.name for p in local_backups],'offDeviceHashVerified':True}
 (backup_root/'latest-success.json').write_text(json.dumps(receipt,indent=2)+'\n')
 print(json.dumps(receipt))
