import unittest

from baltimore.event_sources import sources as baltimore_sources
from city_source_taxonomy import apply_city_source_taxonomy, normalize_tags


class CitySourceTaxonomyTests(unittest.TestCase):
    def test_normalize_tags_splits_ampersand_labels(self):
        self.assertEqual(
            normalize_tags(["Crypto & Web3", "Cloud & Platform", "Crypto"]),
            ["Crypto", "Web3", "Cloud", "Platform"],
        )

    def test_sector_exclusion_removes_sector_and_mapped_source_tags(self):
        sources = [
            {
                "name": "Library",
                "tags": ["Community", "Infrastructure", "Purpose"],
                "excluded_org_tags": ["Environment"],
            }
        ]

        apply_city_source_taxonomy(sources)

        tags = sources[0]["tags"]
        self.assertNotIn("Environment", tags)
        self.assertNotIn("Infrastructure", tags)
        self.assertIn("Culture", tags)
        self.assertIn("Belonging", tags)
        self.assertIn("Purpose", tags)
        self.assertNotIn("Safety", tags)

    def test_unexcluded_infrastructure_still_maps_to_environment(self):
        sources = [{"name": "Climate infrastructure", "tags": ["Infrastructure"]}]

        apply_city_source_taxonomy(sources)

        self.assertIn("Infrastructure", sources[0]["tags"])
        self.assertIn("Environment", sources[0]["tags"])

    def test_compound_source_tags_are_split_before_taxonomy_expansion(self):
        sources = [{"name": "Crypto meetup", "tags": ["Crypto & Web3", "Tech Community"]}]

        apply_city_source_taxonomy(sources)

        tags = sources[0]["tags"]
        self.assertIn("Crypto", tags)
        self.assertIn("Web3", tags)
        self.assertNotIn("Crypto & Web3", tags)
        self.assertIn("Finance", tags)
        self.assertIn("Safety", tags)

    def test_pratt_runtime_tags_exclude_environment_sector(self):
        pratt = next(
            source
            for source in baltimore_sources
            if source.get("name") == "Enoch Pratt Free Library Events"
        )

        self.assertNotIn("Environment", pratt["tags"])
        self.assertNotIn("Infrastructure", pratt["tags"])


if __name__ == "__main__":
    unittest.main()
