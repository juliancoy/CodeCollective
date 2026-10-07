"""Exercise the release CLI against isolated Git repositories."""
import pathlib
import subprocess
import tempfile
import unittest

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / 'scripts/push-all.sh'

class ReleaseTests(unittest.TestCase):
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
