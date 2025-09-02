import unittest
from pathlib import Path
import sys
import importlib.util
from pathlib import Path

from scripts.quick_scan import SCALE_RATIO_RE, SCALE_MM_RE, tokenize, classify_token


def _load_normalizer():
    # Load normalize_inventory.py directly since its parent folder has a numeric prefix
    repo_root = Path(__file__).resolve().parents[1]
    mod_path = repo_root / 'scripts' / '30_normalize_match' / 'normalize_inventory.py'
    spec = importlib.util.spec_from_file_location('normalize_inventory_mod', mod_path)
    if spec is None or spec.loader is None:
        raise RuntimeError('Failed to load normalize_inventory module spec')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestScaleParsing(unittest.TestCase):
    def test_scale_ratio_requires_separator(self):
        # Should NOT match: bare numbers or numbers with trailing dot
        for tok in ["13", "13.", "113", "1."]:
            self.assertIsNone(SCALE_RATIO_RE.match(tok), msg=f"Unexpected ratio match for '{tok}'")

        # Should match: explicit separators between 1 and denominator
        yes = ["1:3", "1-10", "1/35", "1_72"]
        for tok in yes:
            m = SCALE_RATIO_RE.match(tok)
            self.assertIsNotNone(m, msg=f"Expected ratio match for '{tok}'")
            den = int(m.group(1))
            self.assertGreaterEqual(den, 1)
            self.assertLessEqual(den, 999)

    def test_scale_mm_detection(self):
        yes = {"32mm": 32, "54mm": 54, "75mm": 75}
        for tok, expected in yes.items():
            m = SCALE_MM_RE.match(tok)
            self.assertIsNotNone(m, msg=f"Expected mm match for '{tok}'")
            self.assertEqual(int(m.group(1)), expected)

        no = ["mm32", "32", "32-mm", "mm"]
        for tok in no:
            self.assertIsNone(SCALE_MM_RE.match(tok), msg=f"Unexpected mm match for '{tok}'")

    def test_tokenize_directory_with_dot_does_not_create_false_ratio(self):
        # Path like '13. Medraut' previously risked being misread; ensure no scale_ratio tokens appear
        p = Path("C:/models/Characters/13. Medraut/Female Warrior/pose1.stl")
        tokens = tokenize(p)
        # Ensure none of the tokens classify as scale_ratio
        self.assertFalse(any(classify_token(t) == "scale_ratio" for t in tokens), tokens)

    def test_split_scale_tokens_detected_in_normalizer(self):
        # Simulate tokens from a path like:
        # sample_store/Ca 3d Studios - Nami (+NSFW)/1-6 scale Nami CA3D Pre Supported/1-6scale Nami CA3D Pre Supported
        # Tokenizer will likely produce tokens like ["ca", "3d", "studios", "nami", "1", "6", "scale", "nami", "ca3d", "pre", "supported", "1", "6scale", ...]
        tokens = ["ca", "3d", "studios", "nami", "1", "6", "scale", "nami", "ca3d", "pre", "supported", "1", "6scale"]
        # Use empty maps for designer/franchise/character here; scale detection should not depend on them
        normalize_mod = _load_normalizer()
        inferred = normalize_mod.classify_tokens(tokens, designer_map={}, franchise_map={}, character_map={})
        self.assertEqual(inferred.get("scale_ratio_den"), 6, inferred)

    def test_scale_prefix_underscore_format(self):
        # Recognize scale-1_10 style by tokenization: expect tokens ["scale", "1", "10"] leading to 1:10
        tokens = ["display", "artist", "piece", "scale", "1", "10", "package"]
        normalize_mod = _load_normalizer()
        inferred = normalize_mod.classify_tokens(tokens, designer_map={}, franchise_map={}, character_map={})
        self.assertEqual(inferred.get("scale_ratio_den"), 10, inferred)


if __name__ == "__main__":
    unittest.main()
