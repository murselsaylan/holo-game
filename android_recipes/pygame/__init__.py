"""pygame 2.6.1 for python-for-android.

Two fixes over p4a's bundled 2.1.0 recipe:
1. Use the PyPI sdist (includes Cython-generated C for Python 3.11; GitHub
   tag archives omit it).
2. pygame 2.6.1's buildconfig/Setup.Android.SDL2.in lists the `surface`
   extension without the SIMD blitter sources, but alphablit.c calls them on
   arm64 (NEON is auto-enabled there). The .so then fails to load with
   "cannot locate symbol alphablit_alpha_sse2_argb_surf_alpha" and the game
   crashes at startup. Add the SIMD sources the desktop Setup already has.
"""
from os.path import join

from pythonforandroid.recipes.pygame import Pygame2Recipe


class HoloPygameRecipe(Pygame2Recipe):
    version = "2.6.1"
    url = "https://files.pythonhosted.org/packages/source/p/pygame/pygame-{version}.tar.gz"

    def prebuild_arch(self, arch):
        template = join(self.get_build_dir(arch.arch), "buildconfig", "Setup.Android.SDL2.in")
        with open(template) as f:
            text = f.read()
        if "simd_blitters_sse2.c" not in text:
            old = "surface src_c/surface.c"
            assert old in text, "unexpected pygame Setup.Android.SDL2.in layout"
            text = text.replace(old, "surface src_c/simd_blitters_sse2.c src_c/simd_blitters_avx2.c src_c/surface.c")
            with open(template, "w") as f:
                f.write(text)
        super().prebuild_arch(arch)


recipe = HoloPygameRecipe()
