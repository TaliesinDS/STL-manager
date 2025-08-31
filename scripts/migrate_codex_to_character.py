#!/usr/bin/env python3
"""Compatibility shim: delegates to scripts/50_cleanup_repair/migrate_codex_to_character.py"""
from __future__ import annotations
from pathlib import Path
import runpy

CANONICAL = Path(__file__).resolve().parent / '50_cleanup_repair' / 'migrate_codex_to_character.py'

if __name__ == '__main__':
    runpy.run_path(str(CANONICAL), run_name='__main__')
