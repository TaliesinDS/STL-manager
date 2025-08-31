#!/usr/bin/env python3
"""Compatibility shim: delegates to scripts/20_loaders/sync_designers_from_tokenmap.py"""
from __future__ import annotations
import sys
from pathlib import Path

CANONICAL = Path(__file__).resolve().parent / '20_loaders' / 'sync_designers_from_tokenmap.py'
if __name__ == '__main__':
    # Execute the canonical module as a script with same argv
    import runpy
    runpy.run_path(str(CANONICAL), run_name='__main__')
