"""Reads config.json next to the game (also the only config channel on Android)."""
import os
import json

import sys

_CACHE = None


def _load():
    global _CACHE
    if _CACHE is None:
        try:
            base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
            candidates = [
                os.path.join(os.path.dirname(sys.executable), "config.json"),
                os.path.join(base, "config.json")
            ]
            loaded = False
            for p in candidates:
                if os.path.isfile(p):
                    with open(p, encoding="utf-8") as f:
                        _CACHE = json.load(f)
                    loaded = True
                    break
            if not loaded:
                _CACHE = {}
        except Exception:
            _CACHE = {}
    return _CACHE


def get(key, default=None):
    return _load().get(key, default)


def dev_unlock_all():
    """TEMPORARY test switch: every level and skin selectable. Set "dev_unlock_all": false (or remove) before release."""
    return not get("release_mode", False) and (bool(get("dev_unlock_all", False)) or os.environ.get("HOLO_DEV_UNLOCK", "") == "1")


def test_tools():
    """TEMPORARY tester features: level select, previous/next level, autopilot, immortality (pause menu).
    On for "test_tools": true or "dev_unlock_all": true. For the release build both are false: the level-select screen and
    all these tools disappear and players simply continue the campaign with the levels they have unlocked."""
    return not get("release_mode", False) and (bool(get("test_tools", False)) or dev_unlock_all())
