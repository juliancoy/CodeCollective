"""Exercise the release CLI against isolated Git repositories."""
import pathlib
import subprocess
import tempfile
import unittest
import importlib.util
import json
from unittest.mock import patch

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / 'scripts/push-all.sh'
spec=importlib.util.spec_from_file_location('workspace_release',SCRIPT.with_name('push_all.py'))
release_module=importlib.util.module_from_spec(spec);spec.loader.exec_module(release_module)

class ReleaseTests(unittest.TestCase):
    def global_gate(self, root, run, statuses=None, catalog=None):
        class Response:
            def __init__(self,value):self.value=value
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self,*args):return json.dumps(self.value).encode()
        token=root/'token';token.write_text('synthetic-token')
        replies=[{'suites':catalog or [{'id':'api'},{'id':'web'}]}, {'id':'request'}]
        for status in statuses or ['passed']:
            replies.append({'id':'request','status':status,'run_id':None if status=='queued' else 'synthetic-run'})
            if status!='queued':replies.append({'run':run})
        with patch.dict(release_module.os.environ,{'MAP_MASTER_API_TOKEN_FILE':str(token)}),patch.object(release_module,'git',return_value='reviewed'),patch.object(release_module.time,'sleep'),patch.object(release_module.urllib.request,'urlopen',side_effect=[Response(v) for v in replies]) as http:
            release_module.Release(root,root).distributed()
            return http.call_args_list

    def fixture_run(self):
        return {'id':'synthetic-run','status':'passed',
            'repositories':{name:{'commit':'reviewed'} for name in ('.','OrgPortal','PIdP','CodeCollective')},
            'selection':{'paths':[],'suites':['api','web']},
            'hosts':[{'jobs':{'api':{'status':'passed'},'web':{'status':'reused'}}}]}

    def test_global_test_gate_requests_all_suites_without_deployment_or_email_actions(self):
        with tempfile.TemporaryDirectory() as folder:
            root=pathlib.Path(folder);(root/'lan-monitor').mkdir()
            calls=self.global_gate(root,self.fixture_run(),['queued','passed'])
            request=calls[1].args[0]
            self.assertEqual(request.get_method(),'POST')
            self.assertTrue(request.full_url.endswith('/api/v1/master/test-requests'))
            self.assertEqual(json.loads(request.data),{'suites':['api','web'],'force':False})
            self.assertEqual(request.get_header('Authorization'),'Bearer synthetic-token')
            self.assertTrue(json.loads((root/'global-tests.json').read_text())['passed'])

    def test_global_gate_collapses_large_granular_catalog_to_parent_suites(self):
        with tempfile.TemporaryDirectory() as folder:
            root=pathlib.Path(folder);(root/'lan-monitor').mkdir()
            catalog=[{'id':'api'},{'id':'web'}]+[{'id':'api--'+str(i)} for i in range(307)]
            calls=self.global_gate(root,self.fixture_run(),catalog=catalog)
            self.assertEqual(json.loads(calls[1].args[0].data)['suites'],['api','web'])
            self.assertTrue(json.loads((root/'global-tests.json').read_text())['completeSuiteSelection'])

    def test_global_test_gate_refuses_partial_runs_wrong_revisions_and_focused_scope(self):
        for error in ['partial','revision','scope']:
            with self.subTest(error=error),tempfile.TemporaryDirectory() as folder:
                root=pathlib.Path(folder);(root/'lan-monitor').mkdir()
                run=self.fixture_run()
                if error=='partial':run['status']='partial'
                if error=='revision':run['repositories']['CodeCollective']['commit']='different'
                if error=='scope':run['selection']['suites']=['api']
                with self.assertRaises(RuntimeError):self.global_gate(root,run)

    def test_dry_run_and_commit_push_with_spaces(self):
        with tempfile.TemporaryDirectory(prefix='workspace release ') as temp:
            root = pathlib.Path(temp)
            remote = root / 'remote.git'
            repo = root / 'workspace' / 'sample repo'
            repo.mkdir(parents=True)
            def run(*args):
                return subprocess.run(args, check=True, capture_output=True, text=True).stdout.strip()
            run('git', 'init', '--bare', str(remote))
            run('git', 'init', '-b', 'main', str(repo))
            def git(*args):
                return run('git', '-C', str(repo), *args)
            git('config', 'user.name', 'Release Test')
            git('config', 'user.email', 'test@example.invalid')
            (repo / 'file.txt').write_text('first\n')
            git('add', '.')
            git('commit', '-m', 'Initial')
            git('remote', 'add', 'origin', str(remote))
            git('push', '-u', 'origin', 'main')
            before = git('rev-parse', 'HEAD')
            (repo / 'file.txt').write_text('second\n')
            # Invoke through a symlink, exactly like the workspace entry point.
            link = root / 'workspace' / 'push-all.sh'
            link.symlink_to(SCRIPT)
            run(str(link), str(repo.parent), '--dry-run')
            self.assertEqual(git('rev-parse', 'HEAD'), before)
            self.assertTrue(git('status', '--porcelain'))
            self.assertFalse((repo.parent / '.local-releases').exists())
            run(str(link), str(repo.parent), '--skip-deploy', '--message', 'Reviewed change')
            self.assertEqual(git('log', '-1', '--format=%s'), 'Reviewed change')
            self.assertFalse(git('status', '--porcelain'))
            self.assertEqual(git('rev-parse', 'HEAD'), run('git', '--git-dir', str(remote), 'rev-parse', 'refs/heads/main'))

if __name__ == '__main__':
    unittest.main()
