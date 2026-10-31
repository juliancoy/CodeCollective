import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from genSitemap import BASE_URL, collect_urls, generate_sitemap


class SearchIndexTests(unittest.TestCase):
    def test_final_assets_and_indexability(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'robots.txt').write_text('User-agent: *\nDisallow: /blocked\n')
            pages = {
                'index.html': '',
                'about.html': '<link rel="canonical" href="https://codecollective.us/about.html">',
                'news/index.html': '',
                'blocked.html': '',
                'private.html': '<meta name="Googlebot" content="noindex">',
                'alias.html': '<link rel="canonical" href="http://www.codecollective.us/about.html">',
                'external.html': '<link rel="canonical" href="https://example.com/">',
                'refresh.html': '<meta http-equiv="refresh" content="0;url=/">',
            }
            for rel, head in pages.items():
                path = root / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(f'<html><head>{head}</head><body>Page content</body></html>')
            # Repository/preview internals must never be discovered automatically.
            (root / 'internal.html').write_text('<html><head></head><body>Internal</body></html>')
            manifest = root / 'pages.json'
            manifest.write_text(json.dumps(list(pages)))
            urls = collect_urls(BASE_URL, root, True, manifest)
            self.assertEqual(urls, {BASE_URL+'/', BASE_URL+'/about', BASE_URL+'/news/'})
            self.assertIn('href="https://codecollective.us/about"', (root/'about.html').read_text())
            self.assertIn('href="https://codecollective.us/news/"', (root/'news/index.html').read_text())
            self.assertIn('href="https://codecollective.us/about"', (root/'alias.html').read_text())
            self.assertIn('href="https://example.com/"', (root/'external.html').read_text())
            self.assertEqual(collect_urls(BASE_URL, root, True, manifest), urls)
            manifest.write_text('["deleted.html"]')
            with self.assertRaisesRegex(ValueError, 'missing from deployment'):
                collect_urls(BASE_URL, root, manifest=manifest)

    def test_xml_escapes_urls(self):
        with TemporaryDirectory() as tmp:
            out = Path(tmp) / 'sitemap.xml'
            generate_sitemap(['https://codecollective.us/a?x=1&y=2'], out)
            self.assertIn('&amp;', out.read_text())
            self.assertNotIn('lastmod', out.read_text())
