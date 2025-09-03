# Global PyTest settings for tests/ directory
# Ignore the legacy multilingual test module to avoid basename import collisions
collect_ignore = [
    "test_multilingual_backfill.py",
]
