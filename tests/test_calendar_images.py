import json
import os
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import Mock, patch

from PIL import Image
from calendar_normalize import download_event_images


def picture(color):
    out = BytesIO()
    Image.new('RGB', (20, 20), color).save(out, 'PNG')
    return Mock(content=out.getvalue())


class CalendarImageTests(unittest.TestCase):
    def setUp(self):
        self.previous = os.getcwd()
        self.temp = tempfile.TemporaryDirectory()
        os.chdir(self.temp.name)
        self.errors = Mock()
        self.get = patch('calendar_normalize.requests.get').start()
        self.get.return_value = picture('red')

    def tearDown(self):
        patch.stopall()
        os.chdir(self.previous)
        self.temp.cleanup()

    def run_images(self, events):
        download_event_images(events, lambda name: name.replace(' ', '_'), {}, self.errors)

    def event(self, url='https://example.com/cover.png'):
        return {'name': 'Demo Day', 'imageUrl': url}

    def test_same_name_different_images_do_not_collide(self):
        self.get.side_effect = [picture('red'), picture('blue')]
        events = [self.event(), self.event('https://example.com/new.png')]
        self.run_images(events)
        self.assertNotEqual(events[0]['imageUrl'], events[1]['imageUrl'])
        for event in events:
            self.assertTrue(Path(event['imageUrl'].lstrip('/')).is_file())

    def test_unchanged_url_with_updated_content_gets_new_filename(self):
        event = self.event()
        with patch('calendar_normalize.time.time', return_value=100000):
            self.run_images([event])
        old_url = event['imageUrl']
        self.get.return_value = picture('blue')
        with patch('calendar_normalize.time.time', return_value=200000):
            self.run_images([event])
        self.assertNotEqual(old_url, event['imageUrl'])
        self.assertEqual(event['imageSourceUrl'], 'https://example.com/cover.png')

    def test_reuses_fresh_cache_and_shared_source(self):
        events = [self.event(), self.event()]
        self.run_images(events)
        self.run_images([self.event(), events[0]])
        self.assertEqual(self.get.call_count, 1)
        self.errors.assert_not_called()

    def test_failed_refresh_keeps_last_good_image(self):
        event = self.event()
        with patch('calendar_normalize.time.time', return_value=100000):
            self.run_images([event])
        old_url = event['imageUrl']
        self.get.side_effect = RuntimeError('offline')
        with patch('calendar_normalize.time.time', return_value=200000):
            self.run_images([event])
        self.assertEqual(event['imageUrl'], old_url)
        self.errors.assert_called_once()

    def test_bad_image_keeps_remote_url_without_broken_local_file(self):
        event = self.event()
        self.get.return_value = Mock(content=b'not an image')
        self.run_images([event])
        self.assertEqual(event['imageUrl'], 'https://example.com/cover.png')
        self.assertFalse(Path('event_images').exists())
        self.errors.assert_called_once()

    def test_missing_cache_asset_is_downloaded_again(self):
        event = self.event()
        self.run_images([event])
        Path(event['imageUrl'].lstrip('/')).unlink()
        self.run_images([event])
        self.assertEqual(self.get.call_count, 2)
        self.assertTrue(Path(event['imageUrl'].lstrip('/')).is_file())

    def test_curated_local_image_is_preserved(self):
        Path('event_images').mkdir()
        Path('event_images/manual.webp').write_bytes(b'curated')
        event = self.event('/event_images/manual.webp')
        self.run_images([event])
        self.assertEqual(event['imageUrl'], '/event_images/manual.webp')
        self.get.assert_not_called()
        self.errors.assert_not_called()

    def test_corrupt_cache_is_rebuilt(self):
        event = self.event()
        self.run_images([event])
        cache = next(Path('.cache/calendar-images').glob('*.json'))
        cache.write_text('{broken')
        self.run_images([event])
        self.assertEqual(self.get.call_count, 2)
        self.assertIn('imageUrl', json.loads(cache.read_text()))

class LumaImageTests(unittest.TestCase):
    def test_json_ld_accepts_single_image_url(self):
        from scrape_luma_orgpage import parse_single_event
        result = parse_single_event({'name': 'Demo Day', 'image': 'https://example.com/cover.png'})
        self.assertEqual(result['imageUrl'], 'https://example.com/cover.png')

    def test_external_event_url_is_not_prefixed_with_luma(self):
        from scrape_luma_orgpage import parse_next_data_event
        result = parse_next_data_event({'name': 'Showcase', 'url': 'https://example.com/event'})
        self.assertEqual(result['url'], 'https://example.com/event')

    def test_luma_slug_gets_luma_origin(self):
        from scrape_luma_orgpage import parse_next_data_event
        self.assertEqual(parse_next_data_event({'url': 'abc123'})['url'], 'https://luma.com/abc123')
