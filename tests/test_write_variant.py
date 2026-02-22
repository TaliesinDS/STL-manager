#!/usr/bin/env python3
from __future__ import annotations

import os

import pytest

from db.models import Variant
from db.session import get_session


def test_manual_write_variant_roundtrip():
    vid_env = os.environ.get("TEST_WRITE_VARIANT_ID")
    if not vid_env:
        pytest.skip("manual write test skipped; set TEST_WRITE_VARIANT_ID to run")
    vid = int(vid_env)
    # Read original, set temp value, verify, and revert
    with get_session() as session:
        v = session.query(Variant).get(vid)
        assert v is not None, f"Variant {vid} not found"
        original = v.support_state
        v.support_state = "supported_test"
        session.commit()
    try:
        with get_session() as session:
            v2 = session.query(Variant).get(vid)
            assert v2 is not None
            assert v2.support_state == "supported_test"
    finally:
        # Revert to original to avoid polluting the DB
        with get_session() as session:
            v3 = session.query(Variant).get(vid)
            if v3 is not None:
                v3.support_state = original
                session.commit()

