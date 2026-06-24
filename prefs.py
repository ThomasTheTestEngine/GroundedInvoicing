"""
Lightweight persistence for UI preferences (column widths, sort state, etc.)
Stored as a simple JSON file alongside the database.
"""

import json
from pathlib import Path

PREFS_PATH = Path(__file__).parent / "ui_prefs.json"


def load_prefs():
    try:
        return json.loads(PREFS_PATH.read_text())
    except Exception:
        return {}


def save_prefs(prefs):
    try:
        PREFS_PATH.write_text(json.dumps(prefs, indent=2))
    except Exception:
        pass


def get(key, default=None):
    return load_prefs().get(key, default)


def set(key, value):
    prefs = load_prefs()
    prefs[key] = value
    save_prefs(prefs)
