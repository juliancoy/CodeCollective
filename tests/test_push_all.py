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
    def test_global_test_gate_calls_coordinator_and_pins_revisions(self):
        with tempfile.TemporaryDirectory() as folder:
            root=pathlib.Path(folder);(root/'lan-monitor').mkdir()
            run={'id':'synthetic-run','status':'passed','repositories':{name:{'commit':'reviewed'} for name in ('.','OrgPortal','PIdP')},
                 'hosts':[{'jobs':{'api':{'status':'passed'},'web':{'status':'reused'}}}]}
            class Response:
                def __init__(self,value):self.value=value
                def __enter__(self):return self
                def __exit__(self,*args):pass
                def read(self,*args):return json.dumps(self.value).encode()
            with patch.object(release_module,'git',return_value='reviewed'),patch.object(release_module.urllib.request,'urlopen',side_effect=[Response({'running':False}),Response({'run':{'id':'synthetic-run'}}),Response({'run':run})]) as http:
                release_module.Release(root,root).distributed()
                self.assertEqual(http.call_args_list[1].args[0].get_method(),'POST')
                self.assertTrue(json.loads((root/'global-tests.json').read_text())['passed'])

    def test_global_test_gate_refuses_partial_runs_and_wrong_revisions(self):
        for status,sha in [('partial','reviewed'),('passed','different')]:
            with self.subTest(status=status,sha=sha),tempfile.TemporaryDirectory() as folder:
                root=pathlib.Path(folder);(root/'lan-monitor').mkdir()
                run={'id':'synthetic-run','status':status,'repositories':{name:{'commit':sha} for name in ('.','OrgPortal','PIdP')},'hosts':[{'jobs':{'api':{'status':'passed'}}}]}
                class Response:
                    def __init__(self,value):self.value=value
                    def __enter__(self):return self
                    def __exit__(self,*args):pass
                    def read(self,*args):return json.dumps(self.value).encode()
                with patch.object(release_module,'git',return_value='reviewed'),patch.object(release_module.urllib.request,'urlopen',side_effect=[Response({'running':False}),Response({'run':{'id':'synthetic-run'}}),Response({'run':run})]):
                    with self.assertRaises(RuntimeError):release_module.Release(root,root).distributed()

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
