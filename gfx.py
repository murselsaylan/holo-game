"""Pixel-format conversion that also works without a pygame.display window.

On iPhones the game draws through its own high-DPI pygame.Window + GPU renderer (holo._init_display): there is no
display.set_mode() surface then, and Surface.convert() would fail ("No convert format has been set"). Every
convert in the game goes through cv(), which converts to the frame's format in that case.
"""
_target = None


def set_target(surface):
    """The surface whose pixel format cv() converts to (None = the display surface, the usual case)."""
    global _target
    _target = surface


def cv(surface):
    return surface.convert(_target) if _target is not None else surface.convert()
