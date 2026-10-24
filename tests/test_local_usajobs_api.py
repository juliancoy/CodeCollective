"""Exercise the actual local HTTP handler against an isolated on-disk snapshot."""
import functools
import gzip
import http.client
import importlib.util
import json
from pathlib import Path
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer

spec = importlib.util.spec_from_file_location('collective_run', Path(__file__).resolve().parents[1] / 'run.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
VERSION = 'v20260424T173211Z'


class LocalJobsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.dataset = self.root / 'usa/data/publish/jobs'
        shard = self.dataset / VERSION / 'shards/state=ALL/page=0001.json.gz'
        shard.parent.mkdir(parents=True)
        self.payload = {'version': VERSION, 'records': [{'job_id': '123', 'title': 'Local job'}]}
        shard.write_bytes(gzip.compress(json.dumps(self.payload).encode()))
        self.manifest = {'version': VERSION, 'source_fetched_at': '2026-04-24T17:31:43Z',
                         'source_record_count': 1, 'states': {'ALL': {'shards': [
                             {'page': 1, 'record_count': 1, 'key': f'jobs/{VERSION}/shards/state=ALL/page=0001.json.gz'}]}}}
        (self.dataset / 'latest.json').write_text(json.dumps({'version': VERSION}))
        (self.dataset / VERSION / 'manifest.json').write_text(json.dumps(self.manifest))
        (self.root / '.env.usajobs').write_text('private fixture')
        (self.root / 'index.html').write_text('local homepage')
        handler = functools.partial(runner.LocalSiteHandler, directory=self.root)
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temp.cleanup()

    def request(self, path, method='GET'):
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port)
        connection.request(method, path)
        response = connection.getresponse()
        result = response.status, dict(response.getheaders()), response.read()
        connection.close()
        return result

    def test_local_manifest_and_gzip_page_preserve_snapshot_and_date(self):
        status, _, body = self.request('/api/jobs/meta')
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)['source_fetched_at'], self.manifest['source_fetched_at'])
        status, headers, body = self.request(f'/api/jobs?version={VERSION}&state=ALL&page=1')
        self.assertEqual(status, 200)
        self.assertEqual(headers['Content-Encoding'], 'gzip')
        self.assertEqual(json.loads(gzip.decompress(body)), self.payload)
        status, _, body = self.request('/api/jobs?page=1', 'HEAD')
        self.assertEqual((status, body), (200, b''))
        self.assertEqual(self.request('/')[2], b'local homepage')

    def test_missing_data_does_not_fall_back_to_a_remote_service(self):
        (self.dataset / 'latest.json').unlink()
        self.assertEqual(self.request('/api/jobs/meta')[0], 404)
        self.assertEqual(self.request(f'/api/jobs?version={VERSION}')[0], 200)

    def test_history_lists_saved_snapshots_newest_first_and_marks_latest(self):
        newer = 'v20260501T120000Z'
        manifest = {**self.manifest, 'version': newer, 'source_fetched_at': '2026-05-01T12:00:00Z'}
        (self.dataset / newer).mkdir()
        (self.dataset / newer / 'manifest.json').write_text(json.dumps(manifest))
        status, _, body = self.request('/api/jobs/versions')
        self.assertEqual(status, 200)
        history = json.loads(body)
        self.assertEqual(history['latest'], VERSION)
        self.assertEqual([row['version'] for row in history['versions']], [newer, VERSION])
        self.assertEqual(history['versions'][0]['source_fetched_at'], '2026-05-01T12:00:00Z')
        self.assertEqual(self.request(f'/api/jobs/meta?version={newer}')[0], 200)

    def test_bad_queries_and_private_paths_are_rejected(self):
        for path, status in [('/api/jobs?page=0', 400), ('/api/jobs?page=no', 400),
                             ('/api/jobs?page=2', 404), ('/api/jobs?state=ZZ', 404),
                             ('/api/jobs/meta?version=../private', 400),
                             ('/.env.usajobs', 404), ('/%2eenv.usajobs', 404), ('/usa/data/', 404)]:
            with self.subTest(path=path):
                self.assertEqual(self.request(path)[0], status)

    def test_manifest_cannot_serve_a_file_outside_the_dataset(self):
        self.manifest['states']['ALL']['shards'][0]['key'] = '../../../../.env.usajobs'
        (self.dataset / VERSION / 'manifest.json').write_text(json.dumps(self.manifest))
        self.assertEqual(self.request('/api/jobs')[0], 400)
