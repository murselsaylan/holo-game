"""Bundled Rajdhani (SIL OFL) fonts: consistent look and full Turkish glyph coverage on every platform."""
import os
import pygame
import paths

_CACHE = {}
_FILES = {False: "Rajdhani-SemiBold.ttf", True: "Rajdhani-Bold.ttf"}


def get_font(size, bold=False):
    size = int(size * 1.08)          # Rajdhani runs small compared to system UI fonts
    key = (size, bool(bold))
    f = _CACHE.get(key)
    if f is None:
        path = paths.asset("fonts", _FILES[bool(bold)])
        try:
            f = pygame.font.Font(path, size)
        except Exception:
            f = pygame.font.Font(None, int(size * 1.1))
        _CACHE[key] = f
    return f
