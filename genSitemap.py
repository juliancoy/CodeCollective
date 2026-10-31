"""Build discovery metadata from curated public pages, never repository internals.

Run after asset pruning with --root .cloudflare/site --prepare-html during release.
Cloudflare's auto-trailing-slash HTML handling serves file.html at /file.
"""
import argparse
import json
import re
from pathlib import Path
from urllib.parse import quote, urljoin, urlparse, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser
from xml.etree import ElementTree as ET

from bs4 import BeautifulSoup

BASE_URL = "https://codecollective.us"
MANIFEST = Path(__file__).parent / "scripts/search-pages.json"


def normalize_existing_canonicals(root_dir):
    """Keep aliases' chosen targets, but remove first-party redirect spellings."""
    canonical_tag = re.compile(r'<link\b(?=[^>]*\brel\s*=\s*[\"\']canonical[\"\'])[^>]*>', re.I)
    href = re.compile(r'(\bhref\s*=\s*)([\"\'])(.*?)(\2)', re.I | re.S)

    def normalize(match):
        parts = urlsplit(match[3])
        if parts.hostname not in {"codecollective.us", "www.codecollective.us"}:
            return match[0]
        path = parts.path
        if path.endswith("/index.html"):
            path = path[:-10]
        elif path.endswith(".html"):
            path = path[:-5]
        target = urlunsplit(("https", "codecollective.us", path or "/", parts.query, parts.fragment))
        return match[1] + match[2] + target + match[4]

    for path in root_dir.rglob("*.html"):
        html = path.read_text(encoding="utf-8", errors="replace")
        updated = canonical_tag.sub(lambda m: href.sub(normalize, m[0]), html)
        if updated != html:
            path.write_text(updated, encoding="utf-8")


def path_to_url(base_url, path, root_dir):
    rel = path.relative_to(root_dir).as_posix()
    if rel == "index.html":
        rel = ""
    elif rel.endswith("/index.html"):
        rel = rel[:-10]
    elif rel.endswith(".html"):
        rel = rel[:-5]
    return base_url.rstrip("/") + "/" + quote(rel, safe="/-._~")


def collect_urls(base_url, root_dir, prepare_html=False, manifest=MANIFEST):
    root_dir = Path(root_dir)
    if prepare_html:
        normalize_existing_canonicals(root_dir)
    robots = RobotFileParser()
    robots.parse((root_dir / "robots.txt").read_text().splitlines())
    urls = set()
    for rel in json.loads(Path(manifest).read_text()):
        path = root_dir / rel
        if not path.is_file():
            raise ValueError(f"Public search page missing from deployment: {rel}")
        html = path.read_text(encoding="utf-8")
        soup = BeautifulSoup(html, "html.parser")
        if not soup.head or not soup.body:
            raise ValueError(f"Public search page is not an HTML document: {rel}")
        if any("noindex" in m.get("content", "").lower() or "none" in m.get("content", "").lower().split(",")
               for m in soup.find_all("meta") if m.get("name", "").lower() in {"robots", "googlebot"}):
            continue
        if soup.find("meta", attrs={"http-equiv": re.compile("^refresh$", re.I)}):
            continue
        url = path_to_url(base_url, path, root_dir)
        if not robots.can_fetch("Googlebot", url) or not robots.can_fetch("*", url):
            continue
        canonicals = soup.find_all("link", rel="canonical")
        if len(canonicals) > 1:
            raise ValueError(f"Multiple canonicals: {rel}")
        if canonicals:
            target = urljoin(url, canonicals[0].get("href", ""))
            parsed = urlparse(target)
            # Accept the former .html spelling only when it identifies this page.
            old_url = base_url.rstrip("/") + "/" + quote(rel, safe="/-._~")
            if target not in {url, old_url}:
                continue
            if parsed.query or parsed.fragment:
                continue
        if prepare_html:
            tag = f'<link rel="canonical" href="{url}" />'
            if canonicals:
                html = re.sub(r'<link\b(?=[^>]*\brel\s*=\s*[\"\']canonical[\"\'])[^>]*>', lambda _: tag, html, flags=re.I)
            else:
                html = re.sub(r'</head\s*>', lambda m: tag + '\n' + m[0], html, count=1, flags=re.I)
            path.write_text(html, encoding="utf-8")
        urls.add(url)
    return urls


def generate_sitemap(links, output_file):
    ET.register_namespace("", "http://www.sitemaps.org/schemas/sitemap/0.9")
    ns = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
    root = ET.Element(ns + "urlset")
    for link in sorted(links):
        ET.SubElement(ET.SubElement(root, ns + "url"), ns + "loc").text = link
    ET.indent(root, space="  ")
    ET.ElementTree(root).write(output_file, encoding="utf-8", xml_declaration=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).parent)
    parser.add_argument("--prepare-html", action="store_true")
    args = parser.parse_args()
    urls = collect_urls(BASE_URL, args.root, args.prepare_html)
    if not urls:
        raise ValueError("No indexable public pages")
    generate_sitemap(urls, args.root / "sitemap.xml")
    print(f"Sitemap generated: {len(urls)} public pages")
