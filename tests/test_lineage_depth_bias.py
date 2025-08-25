import unittest
from scripts.normalize_inventory import classify_tokens


class Dummy:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class TestLineageDepthBias(unittest.TestCase):
    def test_deeper_lineage_wins(self):
        # Simulate tokens from a path like:
        # top: 'goblin mayhem and holy angels' -> token 'goblin'
        # deeper: 'elves' closer to files
        tokens = [
            "goblin",  # top-level generic
            "mayhem", "and", "holy", "angels",
            "collection", "set",
            "elves",     # deeper folder with true lineage
            "pose1", "leg"
        ]
        designer_map = {}
        franchise_map = {}
        character_map = {}
        inferred = classify_tokens(tokens, designer_map, franchise_map, character_map,
                                   intended_use_map=None, general_faction_map=None)
        # Expect lineage_family to be 'elves' (last lineage token in sequence)
        self.assertEqual(inferred.get("lineage_family"), "elves")

    def test_single_lineage_token_is_used(self):
        tokens = ["elves", "archer", "pose1"]
        inferred = classify_tokens(tokens, {}, {}, {})
        self.assertEqual(inferred.get("lineage_family"), "elves")

    def test_ork_suppressed_with_space_marine_context(self):
        # Tokens emulate: "primaris killing ork" + purity seals context
        tokens = ["primaris", "killing", "ork", "purity", "seals", "bayard", "revenge"]
        inferred = classify_tokens(tokens, {}, {}, {})
        # Expect no lineage set to 'ork' due to SM + action context
        self.assertNotEqual(inferred.get("lineage_family"), "ork")
        # Warning should indicate ambiguous-vs context
        self.assertIn("lineage_ambiguous_vs_context", inferred.get("normalization_warnings", []))

    def test_orc_suppressed_with_space_marine_context(self):
        tokens = ["primaris", "killing", "orc", "purity", "seals", "bayard", "revenge"]
        inferred = classify_tokens(tokens, {}, {}, {})
        self.assertNotEqual(inferred.get("lineage_family"), "orc")
        self.assertIn("lineage_ambiguous_vs_context", inferred.get("normalization_warnings", []))


if __name__ == "__main__":
    unittest.main()
