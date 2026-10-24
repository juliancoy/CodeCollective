#!/usr/bin/env python3
"""Release sibling Git repositories using their existing production deployment paths."""
import argparse
import datetime as dt
import fcntl
import hashlib
import json
import os
import shutil
from pathlib import Path
import shlex
import subprocess
import sys
import time
import urllib.request

DEFAULT_ROOT = Path(__file__).resolve().parents[2]


def git(repo, *args, check=True):
    result = subprocess.run(['git', '-C', str(repo), *args], text=True, capture_output=True)
    if check and result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return result.stdout.strip()


def discover(root):
    repos = {p.resolve() for p in root.iterdir() if p.is_dir() and (p / '.git').exists()}
    if (root / '.git').exists():
        repos.add(root)
    pending = list(repos)
    while pending:
        repo = pending.pop()
        modules = repo / '.gitmodules'
        if not modules.exists():
            continue
        for line in git(repo, 'config', '-f', str(modules), '--get-regexp', r'^submodule\..*\.path$', check=False).splitlines():
            child = (repo / line.split(None, 1)[1]).resolve()
            if (child / '.git').exists() and child not in repos:
                repos.add(child)
                pending.append(child)
    # Commit initialized children before their parent pointer.
    return sorted(repos, key=lambda p: (-len(p.parts), str(p)))


def state(repo):
    branch = git(repo, 'branch', '--show-current')
    upstream = git(repo, 'rev-parse', '--abbrev-ref', '@{upstream}', check=False)
    remote = git(repo, 'config', f'branch.{branch}.remote', check=False) or 'origin'
    remote_ref = git(repo, 'config', f'branch.{branch}.merge', check=False) or f'refs/heads/{branch}'
    ahead = behind = 0
    if upstream:
        behind, ahead = map(int, git(repo, 'rev-list', '--left-right', '--count', f'{upstream}...HEAD').split())
    return dict(branch=branch, upstream=upstream, remote=remote, remote_ref=remote_ref,
                dirty=bool(git(repo, 'status', '--porcelain')), ahead=ahead, behind=behind,
                commit=git(repo, 'rev-parse', 'HEAD'))


class Release:
    def __init__(self, root, folder):
        self.root, self.folder = root, folder
        self.records = []
        self.env = {**os.environ, 'CI': '1', 'STRICT_TS': '1'}
        self.env.setdefault('VITE_CACHE_DIR', str(folder / 'vite-cache'))
        self.checkouts = {}
        self.reviewed_migrations = set()
        self.distributed_url = 'http://127.0.0.1:8089'
        self.distributed_timeout = 7200

    def distributed(self):
        if not (self.root / 'lan-monitor').is_dir():
            return
        base = self.distributed_url.rstrip('/')
        def request(path, body=None):
            headers = {'Origin': base, 'Content-Type': 'application/json'}
            req = urllib.request.Request(base + path, headers=headers,
                data=json.dumps(body).encode() if body is not None else None)
            with urllib.request.urlopen(req, timeout=30) as response:
                return json.load(response)
        expected = {name: git(self.root / name, 'rev-parse', 'HEAD') for name in ('.', 'OrgPortal', 'PIdP')}
        current = request('/api/distributed-tests')
        deadline = time.monotonic() + self.distributed_timeout
        while current.get('running'):
            refs = (current.get('run') or {}).get('repositories', {})
            if all(refs.get(name, {}).get('commit') == sha for name, sha in expected.items()):
                break
            print('[global-tests] Waiting for the existing run before starting the release revisions', flush=True)
            if time.monotonic() >= deadline:
                raise RuntimeError('Existing global test run did not finish before the release timeout')
            time.sleep(5)
            current = request('/api/distributed-tests')
        if not current.get('running'):
            current = request('/api/distributed-tests/start', {'force': False})
        ident = current['run']['id']
        print(f'[global-tests] Waiting for {ident}: {base}/api/distributed-tests?id={ident}', flush=True)
        previous = None
        while True:
            current = request('/api/distributed-tests?id=' + ident)
            run = current.get('run') or {}
            jobs = [job for host in run.get('hosts', []) for job in host.get('jobs', {}).values()]
            progress = (run.get('status'), sum(j.get('status') in {'passed', 'reused'} for j in jobs), len(jobs))
            if progress != previous:
                print(f'[global-tests] {ident}: {progress[0]}, {progress[1]}/{progress[2]} suites passed/reused', flush=True)
                previous = progress
            if run.get('status') in {'passed', 'failed', 'partial', 'stopped', 'interrupted'}:
                refs = run.get('repositories', {})
                matched = all(refs.get(name, {}).get('commit') == sha for name, sha in expected.items())
                success = run.get('status') == 'passed' and matched and bool(jobs) and all(j.get('status') in {'passed', 'reused'} for j in jobs)
                (self.folder / 'global-tests.json').write_text(json.dumps({'id': ident, 'status': run.get('status'), 'revisionsMatch': matched,
                    'expected': expected, 'suiteCount': len(jobs), 'excludedHosts': run.get('excluded_hosts', []), 'passed': success}, indent=2) + '\n')
                if not success:
                    raise RuntimeError(f'Global distributed tests did not pass for the release revisions: {ident}')
                return
            if time.monotonic() >= deadline:
                raise RuntimeError(f'Global distributed tests timed out; run {ident} remains available in the dashboard')
            time.sleep(5)

    def checkout(self, repo):
        if repo in self.checkouts:
            return self.checkouts[repo]
        name = 'BmoreMedTech' if repo.name.lower() == 'bmoremedtech' else repo.name
        target = self.folder / 'checkouts' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        self.run(repo, 'release-checkout', 'git', 'worktree', 'add', '--detach', str(target), git(repo, 'rev-parse', 'HEAD'))
        self.checkouts[repo] = target
        return target

    def credentials(self):
        if self.env.get('CLOUDFLARE_API_TOKEN') and self.env.get('CLOUDFLARE_ACCOUNT_ID'):
            return
        sys.path.insert(0, str(self.root / 'scripts'))
        from recovery import cf_token, environment
        values = environment()
        self.env.setdefault('CLOUDFLARE_API_TOKEN', cf_token())
        self.env.setdefault('CLOUDFLARE_ACCOUNT_ID', values.get('CLOUDFLARE_ACCOUNT_ID') or values.get('R2_ACCOUNT_ID') or '')
        if not self.env['CLOUDFLARE_ACCOUNT_ID']:
            raise RuntimeError('Cloudflare account ID is required')

    def run(self, repo, label, *command):
        print(f'[{repo.name}] {label}: {shlex.join(map(str, command))}', flush=True)
        log = self.folder / f'{len(self.records):03d}-{repo.name}-{label}.log'
        record = dict(repo=str(repo), phase=label, command=list(map(str, command)), log=str(log))
        self.records.append(record)
        with log.open('w') as output:
            result = subprocess.run(command, cwd=repo, env=self.env, stdout=output, stderr=subprocess.STDOUT)
        record['exit_code'] = result.returncode
        self.save()
        if result.returncode:
            # Keep full logs on disk; command output may contain private diagnostics.
            raise RuntimeError(f'{repo.name} {label} failed; inspect {log}')

    def save(self):
        (self.folder / 'commands.json').write_text(json.dumps(self.records, indent=2) + '\n')

    def validate(self, repo):
        self.run(repo, 'diff-check', 'git', 'diff', '--check', 'HEAD')
        if repo == self.root and (repo / 'peer-worker/package.json').exists():
            self.run(repo, 'workspace-test', 'python3', '-m', 'unittest', 'discover', '-s', 'tests')
            self.run(repo / 'lan-monitor', 'lan-test', 'npm', 'test')
            self.run(repo / 'lan-monitor', 'lan-python-test', 'python3', '-m', 'unittest', 'discover', '-s', 'tests')
            self.run(repo / 'peer-worker', 'peer-test', 'npm', 'test')
            self.run(repo / 'peer-worker', 'peer-types', 'npm', 'run', 'typecheck')
            self.run(repo, 'peer-browser', 'python3', 'scripts/check_peer_browser.py')
        elif repo.name == 'OrgPortal':
            self.run(repo, 'test-catalog', 'node', 'scripts/build-test-catalog.mjs')
            self.run(self.root, 'portal-check', 'python3', 'run.py', '--release', 'check')
            self.run(repo, 'chat-test', 'npm', '--prefix', 'chat-worker', 'test')
            self.run(repo, 'chat-types', 'npm', '--prefix', 'chat-worker', 'run', 'typecheck')
            self.run(repo, 'ecosystem-test', 'npm', '--prefix', 'web', 'run', 'test:ecosystem')
        elif repo.name == 'CodeCollective':
            self.run(repo, 'release-script-test', 'python3', 'tests/test_push_all.py')
            self.run(repo, 'worker-test', 'node', '--test', *sorted(map(str, (repo / 'cloudflare').glob('*.test.mjs'))))
            self.run(repo, 'agenda-test', 'npm', '--prefix', 'calendar-next-app', 'test')
            self.run(repo, 'agenda-build', 'npm', '--prefix', 'calendar-next-app', 'run', 'build')
            self.run(repo, 'rowhome-test', 'npm', '--prefix', 'r8-rowhome', 'test', '--', '--maxWorkers=2')
        elif repo.name.lower() == 'pidp':
            self.run(repo, 'python-test', 'python3', '-c',
                "import os,sys,tempfile,pathlib,pytest; root=pathlib.Path.cwd(); sys.path.insert(0,str(root)); "
                "scratch=tempfile.TemporaryDirectory(); os.chdir(scratch.name); "
                "raise SystemExit(pytest.main([str(root/'tests/test_mcp_authorization.py'), str(root/'tests/test_retention.py')]))")
            self.run(repo, 'worker-test', 'npm', '--prefix', 'serverless', 'test')
            self.run(repo, 'worker-types', 'npm', '--prefix', 'serverless', 'run', 'typecheck')
        elif repo.name.lower() == 'bmoremedtech':
            self.run(repo, 'build', 'npm', 'run', 'build')
        elif repo.name == 'Deism':
            self.run(repo, 'export-syntax', 'python3', '-m', 'py_compile', 'export.py')
        elif (repo / 'package.json').exists():
            scripts = json.loads((repo / 'package.json').read_text()).get('scripts', {})
            for command in ['test', 'build']:
                if command in scripts:
                    self.run(repo, command, 'npm', 'run', command)
        else:
            print(f'[{repo.name}] No configured application check; Git checks completed.', flush=True)

    def migrate(self, repo, database, config='wrangler.jsonc'):
        # Inspect pending migrations and export a restricted recovery copy before applying any.
        label = database + '-pending'
        self.run(repo, label, 'npx', '--no-install', 'wrangler', 'd1', 'migrations', 'list', database, '--config', config, '--remote')
        log = self.folder / self.records[-1]['log']
        if 'No migrations to apply' in log.read_text():
            return
        import re
        pending = set(re.findall(r'\b\d{4}_[A-Za-z0-9_]+\.sql\b', log.read_text()))
        if not pending or not pending.issubset(self.reviewed_migrations):
            raise RuntimeError(f'{database}: review pending migrations and pass each --reviewed-migration explicitly')
        backup = self.folder / f'{database}-before-migration.sql'
        self.run(repo, database + '-backup', 'npx', '--no-install', 'wrangler', 'd1', 'export', database, '--config', config, '--remote', '--output', str(backup))
        self.run(repo, database + '-migrate', 'npx', '--no-install', 'wrangler', 'd1', 'migrations', 'apply', database, '--config', config, '--remote')

    def deploy(self, changed):
        self.credentials()
        by_name = {p.name: p for p in discover(self.root)}
        # Identity is released separately, with its current production variables retained.
        pidp = next((p for p in changed if p.name.lower() == 'pidp'), None)
        if pidp:
            worker = self.checkout(pidp) / 'serverless'
            (worker / 'node_modules').symlink_to(pidp / 'serverless/node_modules', target_is_directory=True)
            self.run(worker, 'dry-run', 'npm', 'run', 'deploy:serverless', '--', '--dry-run', '--skip-migrations', '--keep-vars')
            self.migrate(worker, 'pidp')
            self.run(worker, 'deploy', 'npm', 'run', 'deploy:serverless', '--', '--skip-migrations', '--keep-vars')
        portal = by_name.get('OrgPortal')
        collective = by_name.get('CodeCollective')
        if portal and (portal in changed or collective in changed or any(p.name.lower() == 'bmoremedtech' for p in changed)):
            self.checkout(portal)
        if portal in changed:
            frozen = self.checkout(portal)
            self.migrate(portal / 'org-worker', 'org-journal', 'journal.wrangler.jsonc')
            self.migrate(portal / 'org-worker', 'org')
            self.migrate(portal / 'chat-worker', 'chat')
            self.run(self.root, 'portal-build', 'python3', 'run.py', '--release', 'build', '--release-checkout', str(frozen))
            self.run(self.root, 'portal-deploy', 'python3', 'run.py', '--release', 'deploy', '--release-checkout', str(frozen))
            worker = frozen / 'chat-worker'
            (worker / 'node_modules').symlink_to(portal / 'chat-worker/node_modules', target_is_directory=True)
            self.run(worker, 'chat-metadata', 'npm', 'run', 'build:metadata')
            self.run(worker, 'chat-deploy', 'npx', '--no-install', 'wrangler', 'deploy', '--keep-vars', '--message', git(portal, 'rev-parse', 'HEAD'))
        if collective and (collective in changed or by_name.get('r8-rowhome') in changed):
            frozen = self.checkout(collective)
            for name in ['node_modules', 'calendar-next-app/node_modules']:
                (frozen / name).symlink_to(collective / name, target_is_directory=True)
            nested = frozen / 'r8-rowhome'
            if nested.exists(): nested.rmdir()
            nested.symlink_to(collective / 'r8-rowhome', target_is_directory=True)
            self.run(frozen, 'site-dry-run', './deploy.sh', '--component', 'site', '--target', 'prod', '--dry-run')
            self.run(frozen, 'site-deploy', './deploy.sh', '--component', 'site', '--target', 'prod', '--skip-build')
        medtech = next((p for p in changed if p.name.lower() == 'bmoremedtech'), None)
        if medtech:
            frozen = self.checkout(medtech)
            (frozen / 'node_modules').symlink_to(medtech / 'node_modules', target_is_directory=True)
            shutil.copytree(medtech / 'dist', frozen / 'dist', dirs_exist_ok=True)
            self.run(frozen, 'medtech-deploy', 'npm', 'run', 'deploy', '--', '--keep-vars', '--message', git(medtech, 'rev-parse', 'HEAD'))
            self.run(frozen, 'lifetech-build', 'npm', 'run', 'build:lifetech')
            self.run(frozen, 'lifetech-deploy', 'npm', 'run', 'deploy:lifetech', '--', '--keep-vars', '--message', git(medtech, 'rev-parse', 'HEAD'))
        deism = by_name.get('Deism')
        if deism in changed:
            frozen = self.checkout(deism)
            (frozen / 'node_modules').symlink_to(deism / 'node_modules', target_is_directory=True)
            self.run(frozen, 'build', 'python3', 'export.py')
            account = self.env['CLOUDFLARE_ACCOUNT_ID']
            req = urllib.request.Request(f'https://api.cloudflare.com/client/v4/accounts/{account}/pages/projects/deism', headers={'Authorization': 'Bearer ' + self.env['CLOUDFLARE_API_TOKEN']})
            with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req, timeout=30) as response:
                branch = json.load(response)['result']['production_branch']
            self.run(frozen, 'deploy', 'npx', '--no-install', 'wrangler', 'pages', 'deploy', 'build', '--project-name', 'deism', '--branch', branch)
        if self.root in changed and (self.root / 'peer-worker/package.json').exists():
            frozen = self.checkout(self.root) / 'peer-worker'
            (frozen / 'node_modules').symlink_to(self.root / 'peer-worker/node_modules', target_is_directory=True)
            self.run(frozen, 'peer-deploy', 'npm', 'run', 'deploy', '--', '--keep-vars', '--message', git(self.root, 'rev-parse', 'HEAD'))
        for repo in changed:
            if repo != self.root and repo.name not in {'CodeCollective', 'OrgPortal', 'PIdP', 'pidp', 'BmoreMedTech', 'bmoremedtech', 'Deism', 'r8-rowhome'}:
                print(f'[{repo.name}] No production deployment configured; committed and pushed only.', flush=True)
        self.verify(changed, by_name)

    def verify(self, changed, by_name):
        targets = []
        if by_name.get('OrgPortal') in changed:
            sha = git(by_name['OrgPortal'], 'rev-parse', 'HEAD')
            targets += [('https://orgportal.cc/health', sha), ('https://orgportal.cc/api/org/health', sha),
                        ('https://chat-codecollective.jcloiacon.workers.dev/health', sha)]
        pidp = next((p for p in changed if p.name.lower() == 'pidp'), None)
        if pidp: targets.append(('https://orgportal.cc/pidp/health', git(pidp, 'rev-parse', 'HEAD')))
        if by_name.get('CodeCollective') in changed: targets.append(('https://codecollective.us/', None))
        if any(p.name.lower() == 'bmoremedtech' for p in changed): targets += [('https://lifetech.fyi/', None), ('https://medtech.social/', None)]
        if by_name.get('Deism') in changed: targets.append(('https://deism.church/', None))
        if self.root in changed: targets.append(('https://organization-archive-peers.jcloiacon.workers.dev/health', None))
        results = []
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        for url, expected in targets:
            for attempt in range(12):
                try:
                    req = urllib.request.Request(url + ('?release=' + expected if expected else ''), headers={'User-Agent': 'OrgPortal-CLI/0.1', 'Cache-Control': 'no-cache'})
                    with opener.open(req, timeout=30) as response: raw = response.read(4 * 1024 * 1024); status = response.status
                    if expected:
                        data = json.loads(raw)
                        if data.get('commit') != expected or data.get('dirty') is not False: raise RuntimeError('Published revision mismatch')
                    if status != 200: raise RuntimeError('Public URL failed')
                    break
                except Exception:
                    if attempt == 11: raise RuntimeError('Live verification failed: ' + url)
                    time.sleep(5)
            results.append({'url': url, 'status': status, 'commit': expected})
        if self.root in changed:
            url = 'https://organization-archive-peers.jcloiacon.workers.dev/peer.js?release=' + git(self.root, 'rev-parse', 'HEAD')
            with opener.open(urllib.request.Request(url, headers={'User-Agent': 'OrgPortal-CLI/0.1'}), timeout=30) as response: raw = response.read(2 * 1024 * 1024)
            expected = (self.checkout(self.root) / 'peer-worker/public/peer.js').read_bytes()
            if hashlib.sha256(raw).digest() != hashlib.sha256(expected).digest(): raise RuntimeError('Hosted WebRTC client differs from released source')
            results.append({'url': url, 'sourceHashMatches': True})
        (self.folder / 'verification.json').write_text(json.dumps(results, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', nargs='?', type=Path, default=DEFAULT_ROOT)
    parser.add_argument('--message', default='Release reviewed workspace changes')
    parser.add_argument('--dry-run', action='store_true', help='Show the plan without fetching, staging, pushing or deploying')
    parser.add_argument('--skip-deploy', action='store_true', help='Validate, commit and push only')
    parser.add_argument('--deploy-all', action='store_true', help='Redeploy configured applications even if Git is clean')
    parser.add_argument('--reviewed-migration', action='append', default=[], help='An explicitly reviewed pending migration filename; repeat for each')
    parser.add_argument('--distributed-url', default='http://127.0.0.1:8089', help='Existing global distributed-test coordinator')
    parser.add_argument('--distributed-timeout', type=int, default=7200)
    args = parser.parse_args()
    root = args.directory.resolve()
    if not root.is_dir():
        parser.error('directory must exist')
    repos = discover(root)
    # Independent checkouts of one origin must publish one history, not race two
    # diverging commits. Prefer its dirty checkout; refresh clean aliases afterward.
    groups = {}
    for repo in repos:
        origin = git(repo, 'remote', 'get-url', 'origin', check=False)
        key = (origin.lower().removesuffix('.git'), state(repo)['branch']) if origin else (str(repo), '')
        groups.setdefault(key, []).append(repo)
    aliases = []
    selected = []
    for group in groups.values():
        dirty = [repo for repo in group if state(repo)['dirty']]
        if len(dirty) > 1:
            raise RuntimeError('Multiple dirty checkouts share an origin; reconcile their changes before release: ' + ', '.join(map(str, dirty)))
        primary = dirty[0] if dirty else group[0]
        selected.append(primary)
        aliases.extend(repo for repo in group if repo != primary)
    repos = [repo for repo in repos if repo in selected]
    initial = {p: state(p) for p in repos}
    for repo, s in initial.items():
        print(f'{repo.relative_to(root)}: branch={s["branch"] or "detached"}, dirty={s["dirty"]}, ahead={s["ahead"]}, behind={s["behind"]}', flush=True)
    if args.dry_run:
        print('Plan: review Git changes, commit existing branches, reconcile upstream, validate, push, run the global distributed suite, then deploy each owning repository from reviewed commits. No migrations without explicit review.')
        return 0
    # Serialize releases in this workspace, but do not disturb another active release.
    with (root / '.push-all.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        folder = root / '.local-releases' / dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        folder.mkdir(parents=True, mode=0o700)
        release = Release(root, folder)
        release.reviewed_migrations = set(args.reviewed_migration)
        release.distributed_url = args.distributed_url
        release.distributed_timeout = args.distributed_timeout
        changed = set()
        try:
            for repo in repos:
                s = state(repo)
                if not s['branch']:
                    if s['dirty']:
                        raise RuntimeError(f'{repo}: dirty detached checkout needs a branch')
                    continue
                if s['dirty'] or s['ahead'] or s['behind'] or args.deploy_all:
                    changed.add(repo)
                release.run(repo, 'fetch', 'git', 'fetch', '--prune', s['remote'])
                if s['upstream'] and git(repo, 'rev-parse', s['upstream']) != s['commit']:
                    changed.add(repo)
                if s['dirty']:
                    files = git(repo, 'ls-files', '--modified', '--deleted', '--others', '--exclude-standard', '-z').split('\0') + git(repo, 'diff', '--cached', '--name-only', '-z').split('\0')
                    for name in filter(None, files):
                        leaf = Path(name).name.lower()
                        if ((leaf.startswith('.env') and not leaf.endswith(('.example', '.sample', '.template'))) or
                                Path(name).suffix.lower() in {'.pem', '.key', '.p12', '.pfx', '.sqlite', '.sqlite3', '.db', '.har'} or
                                leaf in {'credentials.json', 'secrets.json', 'id_rsa', 'id_ed25519'}):
                            raise RuntimeError('Exclude sensitive/runtime file before publication: ' + str(repo / name))
                    release.run(repo, 'diff-check', 'git', 'diff', '--check', 'HEAD')
                    release.run(repo, 'stage', 'git', 'add', '-A')
                    release.run(repo, 'commit', 'git', 'commit', '-m', args.message)
                if s['upstream']:
                    release.run(repo, 'merge', 'git', 'merge', '--no-edit', s['upstream'])
            for repo in repos:
                if repo in changed:
                    release.validate(repo)
            # Build generators may update tracked data. Validate before recording those updates.
            for repo in repos:
                s = state(repo)
                if s['dirty']:
                    paths = git(repo, 'diff', '--name-only', 'HEAD').splitlines()
                    allowed = (['assets/data/'] if repo.name.lower() == 'bmoremedtech' else
                               ['web/src/data/test-status-catalog.json'] if repo.name == 'OrgPortal' else [])
                    if not paths or any(not any(path.startswith(prefix) for prefix in allowed) for path in paths) or git(repo, 'ls-files', '--others', '--exclude-standard'):
                        raise RuntimeError(f'{repo}: new source edits appeared during checks; review them before restarting the release')
                    if not s['branch']:
                        raise RuntimeError(f'{repo}: build modified a detached checkout')
                    release.run(repo, 'generated-check', 'git', 'diff', '--check', 'HEAD')
                    release.run(repo, 'generated-stage', 'git', 'add', '-A')
                    release.run(repo, 'generated-commit', 'git', 'commit', '-m', 'Update generated release assets')
                    changed.add(repo)
                if s['branch']:
                    release.run(repo, 'push', 'git', 'push', *([] if s['upstream'] else ['--set-upstream']), s['remote'], f'HEAD:{s["remote_ref"]}')
            for repo in aliases:
                if state(repo)['dirty']:
                    raise RuntimeError(f'{repo}: alias changed during release; do not overwrite it')
                release.run(repo, 'alias-fetch', 'git', 'fetch', 'origin')
                release.run(repo, 'alias-refresh', 'git', 'merge', '--ff-only', '@{upstream}')
            (folder / 'repositories.json').write_text(json.dumps({str(p): state(p) for p in repos}, indent=2) + '\n')
            release.distributed()
            if not args.skip_deploy:
                release.deploy(changed)
            print(f'Release completed. Logs and commit manifest: {folder}', flush=True)
        except (RuntimeError, OSError) as error:
            print(f'Release stopped: {error}\nLogs: {folder}', file=sys.stderr, flush=True)
            return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
