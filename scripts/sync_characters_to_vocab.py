#!/usr/bin/env python3
"""Compatibility shim: delegates to scripts/20_loaders/sync_characters_to_vocab.py"""
from __future__ import annotations
import runpy
from pathlib import Path

CANONICAL = Path(__file__).resolve().parent / '20_loaders' / 'sync_characters_to_vocab.py'

if __name__ == '__main__':
    runpy.run_path(str(CANONICAL), run_name='__main__')
