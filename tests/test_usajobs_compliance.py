"""Access safeguards for the public USAJOBS collectors (no live API calls)."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[1]


def load_collector(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'usa' / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AccessLimitsTests(unittest.TestCase):
    def test_normalization_uses_announcement_instead_of_status_url(self):
        module = load_collector('fetch_jobs_search')
        record = module.normalize_job({'MatchedObjectDescriptor': {
            'PositionURI': 'https://www.usajobs.gov/job/866104100',
            'UserArea': {'Details': {'DetailStatusUrl': 'https://apply.usastaffing.gov/Application/ApplicationStatus'}}}})
        self.assertEqual(record['detail_url'], 'https://www.usajobs.gov/job/866104100')

    def test_throttling_and_server_pause_stop_without_another_request(self):
        for name in ('fetch_jobs', 'fetch_jobs_search'):
            module = load_collector(name)
            call = (lambda: module.fetch_api_payload({})) if name == 'fetch_jobs' else (lambda: module.fetch_json(module.SEARCH_API_URL))
            for code, headers in ((429, {}), (503, {'Retry-After': '120'}),
                                  (503, {'Retry-After': 'Wed, 28 Oct 2026 00:00:00 GMT'}), (403, {})):
                with self.subTest(collector=name, code=code, headers=headers):
                    error = HTTPError('https://data.usajobs.gov', code, 'blocked', headers, None)
                    with patch.object(module, 'urlopen', side_effect=error) as request, patch.object(module.time, 'sleep') as sleep:
                        with self.assertRaises(HTTPError):
                            call()
                        self.assertEqual(request.call_count, 1)
                        sleep.assert_not_called()


if __name__ == '__main__':
    unittest.main()
