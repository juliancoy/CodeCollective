#!/usr/bin/env python3
"""Release sibling Git repositories using their existing production deployment paths."""
import argparse
import datetime as dt
import fcntl
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys

DEFAULT_ROOT = Path(__file__).resolve().parents[2]


def git(repo, *args, check=True):
    result = subprocess.run(['git', '-C', str(repo), *args], text=True, capture_output=True)
    if check and result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return result.stdout.strip()


def discover(root):
    repos = {p.resolve() for p in root.iterdir() if p.is_dir() and (p / '.git').exists()}
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
        if repo.name == 'OrgPortal':
            for part in ['org-worker', 'chat-worker']:
                self.run(repo, part + '-test', 'npm', '--prefix', part, 'test')
                self.run(repo, part + '-types', 'npm', '--prefix', part, 'run', 'typecheck')
            self.run(repo, 'web-test', 'npm', '--prefix', 'web', 'test')
            self.run(repo, 'ecosystem-test', 'npm', '--prefix', 'web', 'run', 'test:ecosystem')
            self.run(repo / 'web', 'route-tests', 'node', '--test', *sorted(map(str, (repo / 'web/tests/unit').glob('*.test.mjs'))))
            self.run(repo, 'web-build', 'npm', '--prefix', 'web', 'run', 'build')
        elif repo.name == 'CodeCollective':
            self.run(repo, 'release-script-test', 'python3', 'tests/test_push_all.py')
            self.run(repo, 'worker-test', 'node', '--test', *sorted(map(str, (repo / 'cloudflare').glob('*.test.mjs'))))
            self.run(repo, 'agenda-test', 'npm', '--prefix', 'calendar-next-app', 'test')
            self.run(repo, 'agenda-build', 'npm', '--prefix', 'calendar-next-app', 'run', 'build')
            self.run(repo, 'rowhome-test', 'npm', '--prefix', 'r8-rowhome', 'test', '--', '--maxWorkers=2')
        elif repo.name.lower() == 'pidp':
            self.run(repo, 'python-test', 'python3', '-m', 'pytest', 'tests/test_mcp_authorization.py', 'tests/test_retention.py')
            self.run(repo, 'worker-test', 'npm', '--prefix', 'serverless', 'test')
            self.run(repo, 'worker-types', 'npm', '--prefix', 'serverless', 'run', 'typecheck')
        elif repo.name == 'bmoremedtech':
            self.run(repo, 'build', 'npm', 'run', 'build')
        elif repo.name == 'Deism':
            self.run(repo, 'build', 'python3', 'export.py')
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
        backup = self.folder / f'{database}-before-migration.sql'
        self.run(repo, database + '-backup', 'npx', '--no-install', 'wrangler', 'd1', 'export', database, '--config', config, '--remote', '--output', str(backup))
        self.run(repo, database + '-migrate', 'npx', '--no-install', 'wrangler', 'd1', 'migrations', 'apply', database, '--config', config, '--remote')

    def deploy(self, changed):
        by_name = {p.name: p for p in discover(self.root)}
        # Identity is released separately, with its current production variables retained.
        pidp = next((p for p in changed if p.name.lower() == 'pidp'), None)
        if pidp:
            worker = pidp / 'serverless'
            self.run(worker, 'dry-run', 'npm', 'run', 'deploy:serverless', '--', '--dry-run', '--skip-migrations', '--keep-vars')
            self.migrate(worker, 'pidp')
            self.run(worker, 'deploy', 'npm', 'run', 'deploy:serverless', '--', '--skip-migrations', '--keep-vars')
        portal = by_name.get('OrgPortal')
        collective = by_name.get('CodeCollective')
        if portal in changed:
            for part, database in [('chat-worker', 'chat'), ('org-worker', 'org')]:
                worker = portal / part
                self.run(worker, 'dry-run', 'npx', '--no-install', 'wrangler', 'deploy', '--dry-run', '--keep-vars')
                if part == 'org-worker':
                    self.migrate(worker, 'org-journal', 'journal.wrangler.jsonc')
                self.migrate(worker, database)
                self.run(worker, 'deploy', 'npx', '--no-install', 'wrangler', 'deploy', '--keep-vars')
            if not collective:
                raise RuntimeError('OrgPortal frontend requires its sibling CodeCollective repository')
        if collective and (collective in changed or portal in changed or by_name.get('r8-rowhome') in changed):
            self.env['ORGPORTAL_DIR'] = str(portal)
            self.run(collective, 'site-dry-run', './deploy.sh', '--component', 'site', '--target', 'prod', '--dry-run')
            self.run(collective, 'site-deploy', './deploy.sh', '--component', 'site', '--target', 'prod', '--skip-build')
        medtech = by_name.get('bmoremedtech')
        if medtech in changed:
            self.run(medtech, 'medtech-deploy', 'npm', 'run', 'deploy')
            self.run(medtech, 'lifetech-build', 'npm', 'run', 'build:lifetech')
            self.run(medtech, 'lifetech-deploy', 'npm', 'run', 'deploy:lifetech')
        deism = by_name.get('Deism')
        if deism in changed:
            self.run(deism, 'deploy', 'npm', 'run', 'deploy:cloudflare', '--', '--branch', 'dev')
        for repo in changed:
            if repo.name not in {'CodeCollective', 'OrgPortal', 'PIdP', 'pidp', 'bmoremedtech', 'Deism', 'r8-rowhome'}:
                print(f'[{repo.name}] No production deployment configured; committed and pushed only.', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', nargs='?', type=Path, default=DEFAULT_ROOT)
    parser.add_argument('--message', default='Release reviewed workspace changes')
    parser.add_argument('--dry-run', action='store_true', help='Show the plan without fetching, staging, pushing or deploying')
    parser.add_argument('--skip-deploy', action='store_true', help='Validate, commit and push only')
    parser.add_argument('--deploy-all', action='store_true', help='Redeploy configured applications even if Git is clean')
    args = parser.parse_args()
    root = args.directory.resolve()
    if not root.is_dir():
        parser.error('directory must exist')
    repos = discover(root)
    initial = {p: state(p) for p in repos}
    for repo, s in initial.items():
        print(f'{repo.relative_to(root)}: branch={s["branch"] or "detached"}, dirty={s["dirty"]}, ahead={s["ahead"]}, behind={s["behind"]}', flush=True)
    if args.dry_run:
        print('Plan: commit children before parents; merge upstream without rewriting history; validate; push; deploy identity, chat, organization and shared frontend in order.')
        return 0
    # Serialize releases in this workspace, but do not disturb another active release.
    with (root / '.push-all.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        folder = root / '.local-releases' / dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        folder.mkdir(parents=True, mode=0o700)
        release = Release(root, folder)
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
                    if not s['branch']:
                        raise RuntimeError(f'{repo}: build modified a detached checkout')
                    release.run(repo, 'generated-check', 'git', 'diff', '--check', 'HEAD')
                    release.run(repo, 'generated-stage', 'git', 'add', '-A')
                    release.run(repo, 'generated-commit', 'git', 'commit', '-m', 'Update generated release assets')
                    changed.add(repo)
                if s['branch']:
                    release.run(repo, 'push', 'git', 'push', *([] if s['upstream'] else ['--set-upstream']), s['remote'], f'HEAD:{s["remote_ref"]}')
            (folder / 'repositories.json').write_text(json.dumps({str(p): state(p) for p in repos}, indent=2) + '\n')
            if not args.skip_deploy:
                release.deploy(changed)
            print(f'Release completed. Logs and commit manifest: {folder}', flush=True)
        except (RuntimeError, OSError) as error:
            print(f'Release stopped: {error}\nLogs: {folder}', file=sys.stderr, flush=True)
            return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
