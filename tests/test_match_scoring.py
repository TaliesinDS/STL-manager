"""Unit tests for scoring / matching logic in match_variants_to_units.

Tests cover pure functions that do NOT require a database connection:
  - norm_text, system_hint
  - find_chapter_hint, _has_marine_context
  - detect_mount_context, apply_mount_bias
  - detect_spell_context, detect_aos_faction_hint
  - score_match, find_best_matches
  - _path_segments
"""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from typing import Dict, List, Set, Tuple

# The module lives under a numeric-prefix directory so we import it via spec.
_REPO = Path(__file__).resolve().parents[1]
_MOD_PATH = _REPO / "scripts" / "30_normalize_match" / "match_variants_to_units.py"
_spec = importlib.util.spec_from_file_location("match_variants_to_units", str(_MOD_PATH))
_mod = importlib.util.module_from_spec(_spec)
# Register in sys.modules BEFORE exec so that @dataclass can resolve __module__
sys.modules["match_variants_to_units"] = _mod
_spec.loader.exec_module(_mod)

# Pull out all the symbols we want to test
norm_text = _mod.norm_text
system_hint = _mod.system_hint
find_chapter_hint = _mod.find_chapter_hint
_has_marine_context = _mod._has_marine_context
detect_mount_context = _mod.detect_mount_context
apply_mount_bias = _mod.apply_mount_bias
detect_spell_context = _mod.detect_spell_context
detect_aos_faction_hint = _mod.detect_aos_faction_hint
score_match = _mod.score_match
find_best_matches = _mod.find_best_matches
_path_segments = _mod._path_segments
UnitRef = _mod.UnitRef


# ── helpers ──────────────────────────────────────────────────────────────────


def _ref(unit_key: str = "test_unit", system_key: str = "w40k",
         faction_key: str | None = None, category: str | None = None,
         unit_id: int = 1, unit_name: str = "Test Unit") -> UnitRef:
    return UnitRef(
        unit_id=unit_id,
        system_key=system_key,
        unit_key=unit_key,
        unit_name=unit_name,
        faction_key=faction_key,
        category=category,
    )


# ── norm_text ────────────────────────────────────────────────────────────────


class TestNormText(unittest.TestCase):
    def test_basic_lowering_and_collapse(self):
        self.assertEqual(norm_text("Hello  World"), "hello world")

    def test_warhammer_40k_alias(self):
        self.assertEqual(norm_text("Warhammer 40,000 Space Marines"), "w40k space marines")

    def test_age_of_sigmar_alias(self):
        self.assertIn("aos", norm_text("Age of Sigmar Nighthaunt"))

    def test_horus_heresy_alias(self):
        self.assertIn("heresy", norm_text("Horus Heresy Terminators"))

    def test_30k_alias(self):
        self.assertIn("heresy", norm_text("30k Solar Auxilia"))

    def test_non_word_collapse(self):
        self.assertEqual(norm_text("a--b__c//d"), "a b c d")


# ── system_hint ──────────────────────────────────────────────────────────────


class TestSystemHint(unittest.TestCase):
    def test_w40k_keywords(self):
        for text in ["40k Space Marines", "W40K files", "wh40k", "Warhammer 40,000"]:
            self.assertEqual(system_hint(text), "w40k", msg=text)

    def test_aos_direct_keywords(self):
        for text in ["aos", "Age of Sigmar", "Sigmar", "Freeguild"]:
            self.assertEqual(system_hint(text), "aos", msg=text)

    def test_aos_faction_tokens(self):
        self.assertEqual(system_hint("Soulblight Gravelords Vampires"), "aos")

    def test_heresy_keywords(self):
        for text in ["Heresy era", "30k", "Horus Heresy"]:
            self.assertEqual(system_hint(text), "heresy", msg=text)

    def test_no_hint(self):
        self.assertIsNone(system_hint("some random STL folder"))

    def test_case_insensitive(self):
        self.assertEqual(system_hint("AOS stuff"), "aos")


# ── find_chapter_hint ────────────────────────────────────────────────────────


class TestFindChapterHint(unittest.TestCase):
    def test_long_form_chapter(self):
        self.assertEqual(find_chapter_hint("blood angels captain"), ("blood_angels", None))
        self.assertEqual(find_chapter_hint("dark angels terminators"), ("dark_angels", None))

    def test_subfaction(self):
        self.assertEqual(find_chapter_hint("deathwing terminators"), ("dark_angels", "deathwing"))
        self.assertEqual(find_chapter_hint("flesh tearers assault"), ("blood_angels", "flesh_tearers"))

    def test_abbreviation_with_marine_context(self):
        # 'ba' should only match with marine context
        chap, sub = find_chapter_hint("ba intercessor squad")
        self.assertEqual(chap, "blood_angels")

    def test_abbreviation_without_marine_context(self):
        chap, sub = find_chapter_hint("ba generic folder")
        self.assertIsNone(chap)

    def test_dw_requires_terminator(self):
        # 'dw' with terminator -> deathwing
        chap, sub = find_chapter_hint("dw terminator squad")
        self.assertEqual(chap, "dark_angels")
        self.assertEqual(sub, "deathwing")

    def test_dw_without_terminator_no_match(self):
        # 'dw' without terminator -> ignored
        chap, sub = find_chapter_hint("dw intercessor squad")
        # Should still match via abbreviation list (but not as deathwing)
        # Actually 'dw' is skipped entirely in the abbreviation loop
        # when marine context is present but no terminator context
        self.assertNotEqual(sub, "deathwing")

    def test_no_hint(self):
        self.assertEqual(find_chapter_hint("random models folder"), (None, None))


# ── _has_marine_context ──────────────────────────────────────────────────────


class TestHasMarineContext(unittest.TestCase):
    def test_positive(self):
        for tok in ["intercessor", "tactical", "captain", "librarian", "chaplain"]:
            self.assertTrue(_has_marine_context(tok), msg=tok)

    def test_negative(self):
        self.assertFalse(_has_marine_context("random folder name"))


# ── detect_mount_context ─────────────────────────────────────────────────────


class TestDetectMountContext(unittest.TestCase):
    def test_mounted_terrorgeist(self):
        is_mount, mtype = detect_mount_context("vampire lord on terrorgeist")
        self.assertTrue(is_mount)
        self.assertEqual(mtype, "terror")

    def test_mounted_dragon(self):
        is_mount, mtype = detect_mount_context("prince on zombie dragon")
        self.assertTrue(is_mount)
        self.assertEqual(mtype, "dragon")

    def test_mounted_generic(self):
        is_mount, mtype = detect_mount_context("knight mounted on horse")
        self.assertTrue(is_mount)
        self.assertIsNone(mtype)

    def test_no_mount(self):
        is_mount, mtype = detect_mount_context("space marine tactical squad")
        self.assertFalse(is_mount)
        self.assertIsNone(mtype)


# ── apply_mount_bias ─────────────────────────────────────────────────────────


class TestApplyMountBias(unittest.TestCase):
    def test_no_mount_context_returns_unchanged(self):
        results = [(_ref(unit_key="vampire_lord"), 15.0, "vampire lord")]
        out = apply_mount_bias(results, "vampire lord")
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0][1], 15.0)

    def test_mounted_terrorgeist_boosted(self):
        base = _ref(unit_key="vampire_lord", unit_id=1)
        mounted = _ref(unit_key="vampire_lord_on_terrorgeist", unit_id=2)
        results = [(base, 15.0, "vampire lord"), (mounted, 14.0, "vampire lord on terrorgeist")]
        out = apply_mount_bias(results, "vampire lord on terrorgeist")
        # mounted should be boosted above base
        self.assertEqual(out[0][0].unit_key, "vampire_lord_on_terrorgeist")
        self.assertGreater(out[0][1], out[1][1])

    def test_base_penalized_in_mount_context(self):
        base = _ref(unit_key="vampire_lord", unit_id=1)
        results = [(base, 15.0, "vampire lord")]
        out = apply_mount_bias(results, "vampire lord on terrorgeist")
        # base should be penalized (-1.0)
        self.assertEqual(out[0][1], 14.0)


# ── detect_spell_context ─────────────────────────────────────────────────────


class TestDetectSpellContext(unittest.TestCase):
    def test_positive(self):
        for text in ["endless spell tokens", "manifestation folder", "invocation of khorne"]:
            self.assertTrue(detect_spell_context(text), msg=text)

    def test_negative(self):
        self.assertFalse(detect_spell_context("space marine captain"))


# ── detect_aos_faction_hint ──────────────────────────────────────────────────


class TestDetectAosFactionHint(unittest.TestCase):
    def test_known_faction(self):
        self.assertEqual(detect_aos_faction_hint("stormcast eternals heroes"), "stormcast_eternals")
        self.assertEqual(detect_aos_faction_hint("nighthaunt grimghast reapers"), "nighthaunt")

    def test_no_match(self):
        self.assertIsNone(detect_aos_faction_hint("random folder no faction"))


# ── score_match ──────────────────────────────────────────────────────────────


class TestScoreMatch(unittest.TestCase):
    def test_base_score_positive(self):
        ref = _ref()
        s = score_match("intercessor", ref, "intercessor squad", None)
        self.assertGreater(s, 0)

    def test_system_consistency_boost(self):
        ref = _ref(system_key="w40k")
        s_match = score_match("intercessor", ref, "intercessor squad", "w40k")
        s_no = score_match("intercessor", ref, "intercessor squad", None)
        self.assertGreater(s_match, s_no)

    def test_cross_system_penalty(self):
        ref = _ref(system_key="w40k")
        s = score_match("intercessor", ref, "intercessor squad", "aos")
        s_neutral = score_match("intercessor", ref, "intercessor squad", None)
        self.assertLess(s, s_neutral)

    def test_faction_in_text_boost(self):
        ref = _ref(faction_key="blood_angels")
        s_with = score_match("intercessor", ref, "blood_angels intercessor", None)
        s_without = score_match("intercessor", ref, "intercessor squad", None)
        self.assertGreater(s_with, s_without)

    def test_path_segment_boost(self):
        ref = _ref()
        seg_set: Set[str] = {"intercessor"}
        s_with = score_match("intercessor", ref, "intercessor", None, seg_set)
        s_without = score_match("intercessor", ref, "intercessor", None)
        self.assertGreater(s_with, s_without)

    def test_generic_alias_penalty(self):
        ref = _ref()
        s = score_match("ranger", ref, "ranger folder", None)
        s_non_generic = score_match("intercessor", ref, "intercessor folder", None)
        self.assertLess(s, s_non_generic)

    def test_longer_phrase_scores_higher(self):
        ref = _ref()
        s_short = score_match("hi", ref, "hi there", None)
        s_long = score_match("terminator assault squad", ref, "terminator assault squad", None)
        self.assertGreater(s_long, s_short)


# ── _path_segments ───────────────────────────────────────────────────────────


class TestPathSegments(unittest.TestCase):
    def test_basic_segments(self):
        segs = _path_segments("Freeguild Cavaliers\\5. Calix\\CalixAlternativeDeers")
        self.assertEqual(len(segs), 3)
        self.assertIn("freeguild cavaliers", segs)

    def test_filters_noise(self):
        segs = _path_segments("STL/Supported STL/Model")
        # 'stl' and 'supported stl' are in NOISE set
        self.assertNotIn("stl", segs)
        self.assertNotIn("supported stl", segs)

    def test_empty(self):
        self.assertEqual(_path_segments(""), [])
        self.assertEqual(_path_segments(None), [])


# ── find_best_matches (integration of scoring) ──────────────────────────────


class TestFindBestMatches(unittest.TestCase):
    def _build_index(self, entries: List[Tuple[str, UnitRef]]) -> Dict[str, List[UnitRef]]:
        from collections import defaultdict
        idx: Dict[str, List[UnitRef]] = defaultdict(list)
        for phrase, ref in entries:
            idx[phrase].append(ref)
        return idx

    def test_single_match(self):
        ref = _ref(unit_key="intercessor_squad", unit_name="Intercessor Squad")
        idx = self._build_index([("intercessor squad", ref)])
        results = find_best_matches(idx, "intercessor squad space marines", "w40k")
        self.assertTrue(len(results) >= 1)
        self.assertEqual(results[0][0].unit_key, "intercessor_squad")

    def test_no_match(self):
        ref = _ref(unit_key="intercessor_squad", unit_name="Intercessor Squad")
        idx = self._build_index([("intercessor squad", ref)])
        results = find_best_matches(idx, "some unrelated folder", None)
        self.assertEqual(len(results), 0)

    def test_longer_phrase_preferred(self):
        ref_short = _ref(unit_key="assault_squad", unit_name="Assault Squad", unit_id=1)
        ref_long = _ref(unit_key="terminator_assault_squad", unit_name="Terminator Assault Squad", unit_id=2)
        idx = self._build_index([
            ("assault squad", ref_short),
            ("terminator assault squad", ref_long),
        ])
        results = find_best_matches(idx, "terminator assault squad models", "w40k")
        # The longer phrase should subsume the shorter one
        matched_keys = {r[0].unit_key for r in results}
        self.assertIn("terminator_assault_squad", matched_keys)

    def test_system_consistency_affects_ranking(self):
        ref_40k = _ref(unit_key="ranger_40k", system_key="w40k", unit_name="Ranger", unit_id=1)
        ref_aos = _ref(unit_key="ranger_aos", system_key="aos", unit_name="Ranger", unit_id=2)
        idx = self._build_index([
            ("ranger", ref_40k),
            ("ranger", ref_aos),
        ])
        results = find_best_matches(idx, "ranger squad w40k", "w40k")
        if len(results) >= 2:
            # 40k ranger should score higher than aos ranger
            scores = {r[0].unit_key: r[1] for r in results}
            self.assertGreater(scores["ranger_40k"], scores["ranger_aos"])

    def test_mount_injection(self):
        base = _ref(unit_key="vampire_lord", unit_name="Vampire Lord", unit_id=1)
        mounted = _ref(unit_key="vampire_lord_on_terrorgeist", unit_name="Vampire Lord on Terrorgeist", unit_id=2)
        idx = self._build_index([("vampire lord", base)])
        mount_children = {"vampire_lord": [mounted]}
        results = find_best_matches(
            idx, "vampire lord on terrorgeist", "aos",
            mount_children=mount_children,
        )
        matched_keys = {r[0].unit_key for r in results}
        self.assertIn("vampire_lord_on_terrorgeist", matched_keys)

    def test_spell_injection(self):
        ref = _ref(
            unit_key="purple_sun",
            unit_name="Purple Sun",
            system_key="aos",
            faction_key="stormcast_eternals",
            category="endless_spell",
            unit_id=10,
        )
        idx: Dict[str, List[UnitRef]] = {}  # empty — no direct text match
        spells = {"stormcast_eternals": [ref]}
        results = find_best_matches(
            idx, "stormcast eternals endless spell",
            "aos",
            spells_by_faction=spells,
        )
        matched_keys = {r[0].unit_key for r in results}
        self.assertIn("purple_sun", matched_keys)


if __name__ == "__main__":
    unittest.main()
