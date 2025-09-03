from __future__ import annotations

from pathlib import Path
import json
import os

import pytest


pytestmark = pytest.mark.workflow


def _assert_ok(rc, cp, context: str = ""):
    if rc != 0:
        raise AssertionError(f"{context} failed: rc={rc}\nSTDOUT:\n{cp.stdout}\nSTDERR:\n{cp.stderr}")


def _bootstrap_db(cli, venv_python: str, db_url: str):
    # Pass STLMGR_DB_URL to child to ensure consistent path resolution
    cp = cli([venv_python, "scripts/00_bootstrap/bootstrap_db.py", "--db-url", db_url], env={"STLMGR_DB_URL": db_url})
    _assert_ok(cp.returncode, cp, "bootstrap_db")


def _insert_variants_direct(db_url: str):
    # Insert a few variants with raw_path_tokens covering Spanish, Chinese, Japanese and accented Latin
    os.environ["STLMGR_DB_URL"] = db_url
    from db.session import get_session
    from db.models import Variant
    with get_session() as sess:
        rows = [
            Variant(rel_path="ml/test_es", filename=None, raw_path_tokens=["PiernaDRCH", "BrazoIZQ"]),
            Variant(rel_path="ml/test_zh", filename=None, raw_path_tokens=["分件", "武器"]),
            Variant(rel_path="ml/test_ja", filename=None, raw_path_tokens=["分割", "腕"]),
            Variant(rel_path="ml/test_romanize", filename=None, raw_path_tokens=["Señorita"]),
        ]
        for r in rows:
            sess.add(r)
        sess.commit()


@pytest.mark.parametrize("apply_twice", [False, True])
def test_backfill_english_tokens_end_to_end(cli, venv_python: str, tmp_db_url: str, repo_root: Path, apply_twice: bool):
    # 1) Bootstrap DB and insert sample variants
    _bootstrap_db(cli, venv_python, tmp_db_url)
    _insert_variants_direct(tmp_db_url)

    reports_dir = repo_root / "reports" / "test_artifacts"
    reports_dir.mkdir(parents=True, exist_ok=True)
    out1 = reports_dir / "backfill_test_apply.json"

    # 2) Run backfill apply once
    cp = cli(
        [
            venv_python,
            "scripts/30_normalize_match/backfill_english_tokens.py",
            "--db-url", tmp_db_url,
            "--batch", "50",
            "--apply",
            "--out", str(out1),
        ],
        env={"STLMGR_DB_URL": tmp_db_url},
    )
    _assert_ok(cp.returncode, cp, "backfill_english_tokens --apply")
    assert out1.exists(), "Expected backfill report to be written"
    data = json.loads(out1.read_text("utf-8"))
    assert isinstance(data, dict) and "proposals" in data

    # 3) Validate DB content
    os.environ["STLMGR_DB_URL"] = tmp_db_url
    from db.session import get_session
    from db.models import Variant
    with get_session() as sess:
        rows = {v.rel_path: v for v in sess.query(Variant).all()}
        # Spanish abbreviations -> English phrases, locale en (ASCII)
        es = rows.get("ml/test_es")
        assert es is not None
        eng = es.english_tokens or []
        assert "right leg" in eng and "left arm" in eng
        assert (es.token_locale or "en").startswith("en")
        # Chinese CJK -> zh locale + phrase mapping
        zh = rows.get("ml/test_zh")
        assert zh is not None
        zhe = zh.english_tokens or []
        assert "split parts" in zhe and "weapon" in zhe
        assert zh.token_locale == "zh"
        # Japanese CJK -> ja locale + phrase mapping
        ja = rows.get("ml/test_ja")
        assert ja is not None
        jae = ja.english_tokens or []
        assert "split parts" in jae and "arm" in jae
        assert ja.token_locale == "ja"
        # Romanization fallback for accented Latin
        ro = rows.get("ml/test_romanize")
        assert ro is not None
        roe = ro.english_tokens or []
        assert "senorita" in roe  # Unidecode fallback lowercased

        snap = {k: tuple((rows[k].english_tokens or [])) for k in rows}

    if apply_twice:
        # 4) Re-run apply to ensure idempotency (no changes should be proposed/applied)
        out2 = reports_dir / "backfill_test_apply_second.json"
        cp2 = cli(
                [
                    venv_python,
                    "scripts/30_normalize_match/backfill_english_tokens.py",
                    "--db-url", tmp_db_url,
                    "--batch", "50",
                    "--apply",
                    "--out", str(out2),
                ],
                env={"STLMGR_DB_URL": tmp_db_url},
            )
        _assert_ok(cp2.returncode, cp2, "backfill_english_tokens --apply (2nd)")
        assert out2.exists()
        data2 = json.loads(out2.read_text("utf-8"))
        # No proposals expected on second run without --force
        assert isinstance(data2, dict) and isinstance(data2.get("proposals", []), list)
        assert len(data2.get("proposals", [])) == 0
        # Verify DB remained unchanged
        os.environ["STLMGR_DB_URL"] = tmp_db_url
        from db.session import get_session as _gs
        from db.models import Variant as _V
        with _gs() as sess:
            rows2 = {v.rel_path: v for v in sess.query(_V).all()}
            for k, before in snap.items():
                assert tuple(rows2[k].english_tokens or []) == before
