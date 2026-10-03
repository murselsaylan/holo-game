"""Exercise mobile fallback, cache bounds and cached text pixels offline."""
import os
import sys
import tempfile
import time

os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'
os.environ['HOLO_SAVE_DIR'] = tempfile.mkdtemp(prefix='holo_render_')
os.environ['HOLO_SERVER'] = 'http://127.0.0.1:1'
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pygame
import holo
import ui
from render_cache import SurfaceCache
from level_manager import glow_sprite, _GLOW

g = holo.HoloGame(headless=True)
cache = SurfaceCache(800)
for n in range(100):
    cache.put(n, pygame.Surface((10, 10), depth=32))
assert cache.bytes_used == 800 and len(cache.items) == 2
assert cache.get(98) is not None
cache.put(100, pygame.Surface((10, 10), depth=32))
assert cache.get(99) is None  # Least recently used, not most recently inserted.
cache.put('large', pygame.Surface((100, 100)))
assert cache.bytes_used <= cache.max_bytes

for n in range(500):
    glow_sprite(80 + n % 60, (0, 200, 255), (n % 100) / 100)
assert _GLOW.bytes_used <= _GLOW.max_bytes

a = pygame.Surface((400, 100))
b = a.copy()
ui.draw_text(a, 'HOLO 123', 42, (255, 200, 100), (200, 50), max_w=180)
ui.draw_text(b, 'HOLO 123', 42, (255, 200, 100), (200, 50), max_w=180)
assert pygame.image.tobytes(a, 'RGB') == pygame.image.tobytes(b, 'RGB')

g.android = True
g.scaled = False
g.window = pygame.display.set_mode((1200, 2000))
g.win_w, g.win_h = g.window.get_size()
g.frame.fill((25, 50, 100))
g.settings['screen_shake'] = False
g._present()
buf = g._present_buffer
g._present()
assert g._present_buffer is buf
assert g.window.get_at((600, 1000))[:3] == (25, 50, 100)
assert g.to_virtual((600, 1000)) == (450, 810)
for name, fn in [('old smoothscale + allocation', lambda: pygame.transform.smoothscale(g.frame, buf.get_size())),
                 ('mobile scale + reuse', lambda: pygame.transform.scale(g.frame, buf.get_size(), buf))]:
    start = time.perf_counter()
    for _ in range(100):
        fn()
    print(f'{name}: {(time.perf_counter() - start) * 10:.2f} ms/frame (desktop CPU)')
g.win_w, g.win_h = 600, 1000
g._present()
assert g._present_buffer is not buf
print('PASS: cache memory bounds, eviction, text pixels, Android fallback, touch mapping and resize')
