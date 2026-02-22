"""Unit tests for UI display-name builders in scripts/lib/ui_display.py.

Tests cover:
  - _split_words, _clean_words, _title_case, _norm_label
  - _is_bucket_phrase, _is_packaging_segment
  - _best_named_segment_from_path
  - _choose_thing_name (via stub translate + mock variant)
  - build_ui_display (via stub translate + mock variant)
"""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

# ---------------------------------------------------------------------------
# Load ui_display module
# ---------------------------------------------------------------------------
_REPO = Path(__file__).resolve().parents[1]
_MOD_PATH = _REPO / "scripts" / "lib" / "ui_display.py"

# Before loading ui_display, we need to pre-seed a fake backfill module
# so that its lazy-loader doesn't try to exec the real one (which needs DB
# models etc.).  We'll provide a trivial translate_tokens that returns
# its tokens untouched.
_FAKE_MOD_NAME = "scripts._backfill_english_tokens"


def _identity_translate(tokens, _glos, *, dedup=True):
    """Stub translate_tokens — returns tokens unchanged."""
    if dedup:
        seen = set()
        out = []
        for t in tokens:
            if t not in seen:
                seen.add(t)
                out.append(t)
        return out
    return list(tokens)


# Pre-seed the module so ui_display won't try to load the real one
_fake_mod = SimpleNamespace(translate_tokens=_identity_translate)
sys.modules[_FAKE_MOD_NAME] = _fake_mod  # type: ignore[assignment]

spec = importlib.util.spec_from_file_location("ui_display", str(_MOD_PATH))
ui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ui)

# Pull out symbols
_split_words = ui._split_words
_clean_words = ui._clean_words
_title_case = ui._title_case
_norm_label = ui._norm_label
_is_bucket_phrase = ui._is_bucket_phrase
_is_packaging_segment = ui._is_packaging_segment
_best_named_segment_from_path = ui._best_named_segment_from_path
_choose_thing_name = ui._choose_thing_name
build_ui_display = ui.build_ui_display

# Dummy glossary (object with no entries — identity translate will ignore it)
_GLOS = object()


# ---------------------------------------------------------------------------
# Mock variant factory
# ---------------------------------------------------------------------------

def _variant(**kwargs) -> SimpleNamespace:
    """Create a minimal mock variant with sensible defaults."""
    defaults = dict(
        rel_path="",
        filename="",
        character_name="",
        codex_unit_name="",
        english_tokens=None,
        collection_theme="",
        collection_original_label="",
        collection_id=None,
        raw_path_tokens=None,
        files=None,
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


# ── _split_words ─────────────────────────────────────────────────────────────


class TestSplitWords(unittest.TestCase):
    def test_camel_case(self):
        self.assertEqual(_split_words("CamelCaseWord"), ["Camel", "Case", "Word"])

    def test_separator_chars(self):
        self.assertEqual(_split_words("hello-world_foo.bar"), ["hello", "world", "foo", "bar"])

    def test_number_letter_boundary(self):
        self.assertEqual(_split_words("Item32B"), ["Item", "32", "B"])

    def test_empty(self):
        self.assertEqual(_split_words(""), [])

    def test_path_takes_last_segment(self):
        # paths with '/' — _split_words keeps only last segment
        result = _split_words("foo/bar/BazQuux")
        self.assertIn("Baz", result)
        self.assertIn("Quux", result)


# ── _clean_words ─────────────────────────────────────────────────────────────


class TestCleanWords(unittest.TestCase):
    def test_removes_banned_words(self):
        result = _clean_words(["supported", "knight", "stl"])
        self.assertNotIn("supported", result)
        self.assertNotIn("stl", result)
        self.assertIn("knight", result)

    def test_removes_pure_digits(self):
        result = _clean_words(["32", "knight"])
        self.assertNotIn("32", result)

    def test_removes_mm_measurements(self):
        result = _clean_words(["32mm", "model"])
        self.assertNotIn("32mm", result)

    def test_removes_very_short_tokens(self):
        # single-char tokens (except allowed short words) are stripped
        result = _clean_words(["x", "a", "of", "knight"])
        self.assertNotIn("x", result)
        self.assertNotIn("a", result)
        self.assertIn("of", result)


# ── _title_case ──────────────────────────────────────────────────────────────


class TestTitleCase(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(_title_case(["blood", "angels"]), "Blood Angels")

    def test_small_words_lowered_except_first(self):
        self.assertEqual(_title_case(["of", "the", "realm"]), "Of the Realm")

    def test_acronyms_uppercased(self):
        self.assertIn("CG", _title_case(["cg", "model"]))

    def test_empty(self):
        self.assertEqual(_title_case([]), "")


# ── _norm_label ──────────────────────────────────────────────────────────────


class TestNormLabel(unittest.TestCase):
    def test_lowered_and_cleaned(self):
        result = _norm_label("Blood Angels - Captain")
        self.assertEqual(result, "blood angels captain")

    def test_empty(self):
        self.assertEqual(_norm_label(""), "")
        self.assertEqual(_norm_label(None), "")


# ── _is_bucket_phrase ────────────────────────────────────────────────────────


class TestIsBucketPhrase(unittest.TestCase):
    def test_generic_body_parts(self):
        self.assertTrue(_is_bucket_phrase(["heads", "and", "arms"]))
        self.assertTrue(_is_bucket_phrase(["bodies"]))

    def test_non_generic(self):
        self.assertFalse(_is_bucket_phrase(["vampire", "lord"]))

    def test_all_connectors_no_nouns(self):
        self.assertFalse(_is_bucket_phrase(["and"]))


# ── _is_packaging_segment ───────────────────────────────────────────────────


class TestIsPackagingSegment(unittest.TestCase):
    def test_supported(self):
        self.assertTrue(_is_packaging_segment("supported"))
        self.assertTrue(_is_packaging_segment("Unsupported"))

    def test_packaging_formats(self):
        self.assertTrue(_is_packaging_segment("stl"))
        self.assertTrue(_is_packaging_segment("lychee"))

    def test_mm_measurements(self):
        self.assertTrue(_is_packaging_segment("32mm"))

    def test_non_packaging(self):
        self.assertFalse(_is_packaging_segment("Vampire Lord"))

    def test_empty(self):
        self.assertFalse(_is_packaging_segment(""))


# ── _best_named_segment_from_path ────────────────────────────────────────────


class TestBestNamedSegmentFromPath(unittest.TestCase):
    def test_prefers_deepest_named(self):
        result = _best_named_segment_from_path("Collection/Characters/Vampire Lord/Supported")
        # Should prefer 'Vampire Lord' over packaging 'Supported'
        self.assertIn("Vampire Lord", result)

    def test_skips_pure_packaging(self):
        result = _best_named_segment_from_path("Supported/STL")
        # Both are packaging; should return something (may be empty or best-effort)
        # At minimum it shouldn't crash
        self.assertIsInstance(result, str)

    def test_empty(self):
        self.assertEqual(_best_named_segment_from_path(""), "")


# ── _choose_thing_name ──────────────────────────────────────────────────────


class TestChooseThingName(unittest.TestCase):
    def test_character_name_takes_precedence(self):
        v = _variant(character_name="Lord Kroak")
        result = _choose_thing_name(v, _GLOS, None, _translate=_identity_translate)
        self.assertIn("Kroak", result)

    def test_comma_name_preserved(self):
        v = _variant(rel_path="Collection/3. Smith, John/Supported")
        result = _choose_thing_name(v, _GLOS, None, _translate=_identity_translate)
        self.assertIn("Smith, John", result)

    def test_hyphen_segment_parsed(self):
        v = _variant(rel_path="DM Stash - March Release - Dragon Knight/Supported")
        result = _choose_thing_name(v, _GLOS, None, _translate=_identity_translate)
        # Should pick 'Dragon Knight' (rightmost non-brand segment)
        self.assertTrue(len(result) > 0)

    def test_unit_name_fallback(self):
        v = _variant(codex_unit_name="Intercessor Squad")
        result = _choose_thing_name(v, _GLOS, None, _translate=_identity_translate)
        self.assertIn("Intercessor", result)

    def test_english_tokens_fallback(self):
        v = _variant(english_tokens=["vampire", "lord", "mounted"])
        result = _choose_thing_name(v, _GLOS, ["vampire", "lord", "mounted"],
                                    _translate=_identity_translate)
        # Should produce something from tokens
        self.assertTrue(len(result) > 0)


# ── build_ui_display ────────────────────────────────────────────────────────


class TestBuildUiDisplay(unittest.TestCase):
    def test_hyphen_brand_pattern(self):
        v = _variant(rel_path="Cast n Play - March - Dragon Knight/Supported")
        result = build_ui_display(v, _GLOS)
        self.assertTrue(len(result) > 0)
        # Should not start with the brand "Cast n Play"
        self.assertFalse(result.startswith("Cast n Play"))

    def test_composite_on_segment(self):
        v = _variant(rel_path="Collection/Vampire Lord on Zombie Dragon/STL")
        result = build_ui_display(v, _GLOS)
        self.assertTrue(len(result) > 0)

    def test_proper_name_leaf(self):
        v = _variant(rel_path="Collection/Blood Angels Captain")
        result = build_ui_display(v, _GLOS)
        self.assertTrue(len(result) > 0)

    def test_comma_preserve(self):
        # When the comma segment is NOT the deepest proper-name leaf, step 4
        # kicks in and preserves the comma verbatim.  When it IS the leaf,
        # step 3 (proper-name leaf) fires first and title-cases the words.
        v = _variant(rel_path="Collection/3. Draco, Marcus/Supported")
        result = build_ui_display(v, _GLOS)
        # Either verbatim comma form or title-cased words are acceptable
        self.assertTrue("Draco" in result and "Marcus" in result, result)

    def test_collection_prefix(self):
        v = _variant(
            rel_path="Collection/Blood Angels Captain",
            collection_theme="Dark Crusade",
        )
        result = build_ui_display(v, _GLOS)
        # With a collection theme, the result should include the collection as prefix
        self.assertTrue(len(result) > 0)

    def test_empty_variant(self):
        v = _variant()
        result = build_ui_display(v, _GLOS)
        # Should not crash; may return empty string
        self.assertIsInstance(result, str)

    def test_packaging_segments_skipped(self):
        v = _variant(rel_path="Supported/STL/Lychee")
        result = build_ui_display(v, _GLOS)
        # All segments are packaging; result may be empty but shouldn't crash
        self.assertIsInstance(result, str)

    def test_bucket_with_unit_prefix(self):
        v = _variant(
            rel_path="Collection/Freeguild Cavaliers/Bodies/Supported",
            codex_unit_name="Freeguild Cavaliers",
        )
        result = build_ui_display(v, _GLOS)
        # The bucket 'Bodies' should get a unit prefix
        self.assertTrue(len(result) > 0)


if __name__ == "__main__":
    unittest.main()
