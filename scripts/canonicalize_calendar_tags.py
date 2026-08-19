#!/usr/bin/env python3
"""One-time migration from compound calendar source tags to atomic tags."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

COMPOUND_TAGS = {
    "Water & Environment": ["Water", "Environment"],
    "Survival & Health": ["Survival", "Health"],
    "Health & Wellness": ["Health", "Wellness"],
    "Safety & Stability": ["Safety", "Stability"],
    "Climate & Energy": ["Climate", "Energy"],
    "Belonging & Culture": ["Belonging", "Culture"],
    "Code Collective & Partners": ["Code Collective", "Partners"],
    "Esteem & Opportunity": ["Esteem", "Opportunity"],
    "Growth & Creativity": ["Growth", "Creativity"],
    "Purpose & Service": ["Purpose", "Service"],
    "Faith & Spirituality": ["Faith", "Spirituality"],
    "Cloud & Platform": ["Cloud", "Platform"],
    "Crypto & Web3": ["Crypto", "Web3"],
}


def replace_compound_string_literals(path: Path) -> None:
    text = path.read_text()
    original = text
    for compound, atomic in COMPOUND_TAGS.items():
        replacement = ", ".join(f'"{tag}"' for tag in atomic)
        text = text.replace(f'"{compound}"', replacement)
    if text != original:
        path.write_text(text)
        print(f"updated {path.relative_to(ROOT)}")


def update_pratt_source() -> None:
    """Pratt is not an Environment source; do not seed Environment-derived tags."""
    path = ROOT / "baltimore/event_sources.py"
    text = path.read_text()
    original = text
    old = '''        "name": "Enoch Pratt Free Library Events",\n        "url": "https://www.prattlibrary.org/events",\n        "tags": ["Government", "MarylandGov", "Politics", "Community", "Infrastructure", "Purpose"],\n        "excluded_org_tags": ["Environment"],\n'''
    new = '''        "name": "Enoch Pratt Free Library Events",\n        "url": "https://www.prattlibrary.org/events",\n        "tags": ["Government", "MarylandGov", "Politics", "Community", "Purpose"],\n        "excluded_org_tags": ["Environment"],\n'''
    text = text.replace(old, new)
    if text != original:
        path.write_text(text)
        print("updated baltimore/event_sources.py (Pratt)")


def update_taxonomy() -> None:
    path = ROOT / "city_source_taxonomy.py"
    text = path.read_text()
    marker = "_MASLOW_BY_TAG = {"
    _, tail = text.split(marker, 1)
    normalizer = '''def normalize_tags(tags):\n    """Trim and deduplicate tags without interpreting or splitting them."""\n    normalized = []\n    seen = set()\n    for tag in tags or []:\n        value = str(tag or "").strip()\n        if not value or value in seen:\n            continue\n        seen.add(value)\n        normalized.append(value)\n    return normalized\n\n\n'''
    text = normalizer + marker + tail
    lines = []
    compound_keys = {f'    "{tag}":' for tag in COMPOUND_TAGS}
    for line in text.splitlines():
        if any(line.startswith(prefix) for prefix in compound_keys):
            continue
        lines.append(line)
    path.write_text("\n".join(lines) + "\n")
    print("updated city_source_taxonomy.py")


def update_tests() -> None:
    path = ROOT / "tests/test_city_source_taxonomy.py"
    text = path.read_text()
    text = text.replace(
        '''    def test_normalize_tags_splits_ampersand_labels(self):\n        self.assertEqual(\n            normalize_tags(["Crypto & Web3", "Cloud & Platform", "Crypto"]),\n            ["Crypto", "Web3", "Cloud", "Platform"],\n        )\n''',
        '''    def test_normalize_tags_does_not_interpret_tag_names(self):\n        self.assertEqual(\n            normalize_tags(["Crypto", "Web3", "Crypto", " Cloud "]),\n            ["Crypto", "Web3", "Cloud"],\n        )\n''',
    )
    text = text.replace(
        '''    def test_compound_source_tags_are_split_before_taxonomy_expansion(self):\n        sources = [{"name": "Crypto meetup", "tags": ["Crypto & Web3", "Tech Community"]}]\n\n        apply_city_source_taxonomy(sources)\n\n        tags = sources[0]["tags"]\n        self.assertIn("Crypto", tags)\n        self.assertIn("Web3", tags)\n        self.assertNotIn("Crypto & Web3", tags)\n        self.assertIn("Finance", tags)\n        self.assertIn("Safety", tags)\n''',
        '''    def test_atomic_source_tags_expand_without_compound_processing(self):\n        sources = [{"name": "Crypto meetup", "tags": ["Crypto", "Web3", "Tech Community"]}]\n\n        apply_city_source_taxonomy(sources)\n\n        tags = sources[0]["tags"]\n        self.assertIn("Crypto", tags)\n        self.assertIn("Web3", tags)\n        self.assertIn("Finance", tags)\n        self.assertIn("Safety", tags)\n''',
    )
    text = text.replace(
        '''        self.assertNotIn("Environment", pratt["tags"])\n        self.assertNotIn("Infrastructure", pratt["tags"])\n''',
        '''        self.assertNotIn("Environment", pratt["tags"])\n        self.assertNotIn("Infrastructure", pratt["tags"])\n        self.assertNotIn("Safety", pratt["tags"])\n        self.assertNotIn("Water", pratt["tags"])\n''',
    )
    path.write_text(text)
    print("updated tests/test_city_source_taxonomy.py")


def main() -> None:
    for path in ROOT.glob("*/event_sources.py"):
        replace_compound_string_literals(path)
    replace_compound_string_literals(ROOT / "data/category_maps/community_sectors.json")
    update_pratt_source()
    update_taxonomy()
    update_tests()


if __name__ == "__main__":
    main()
