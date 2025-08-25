import unittest
from pathlib import Path

from scripts.quick_scan import SCALE_RATIO_RE, SCALE_MM_RE, tokenize, classify_token


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


if __name__ == "__main__":
    unittest.main()
