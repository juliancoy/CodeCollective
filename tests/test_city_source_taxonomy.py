import unittest

from city_source_taxonomy import apply_city_source_taxonomy, normalize_tags


class CitySourceTaxonomyTests(unittest.TestCase):
    def test_normalize_tags_only_trims_and_deduplicates(self):
        self.assertEqual(
            normalize_tags(["Crypto", "Web3", "Crypto", " Cloud ", ""]),
            ["Crypto", "Web3", "Cloud"],
        )

    def test_taxonomy_does_not_add_derived_tags(self):
        sources = [{"name": "Climate infrastructure", "tags": ["Infrastructure"]}]

        apply_city_source_taxonomy(sources)

        self.assertEqual(sources[0]["tags"], ["Infrastructure"])

    def test_taxonomy_does_not_interpret_atomic_tags(self):
        sources = [{"name": "Crypto meetup", "tags": ["Crypto", "Web3", "Tech Community"]}]

        apply_city_source_taxonomy(sources)

        self.assertEqual(
            sources[0]["tags"],
            ["Crypto", "Web3", "Tech Community"],
        )


if __name__ == "__main__":
    unittest.main()
