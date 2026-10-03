# HOLO 5.1.2 performance patch

Android software presentation reuses its destination surface and uses unfiltered
scaling. The SDL accelerated SCALED path is unchanged. This avoids a CPU filter
over the full tablet screen when SDL accelerated presentation is unavailable;
fine edges on that fallback path may look slightly sharper.

Glow surfaces now use a 12 MiB LRU instead of an unbounded dictionary, with
brightness quantized to 1/16. UI text uses an 8 MiB LRU and orb effects a 2 MiB
LRU. These limits cover those caches, not total application memory.
Physics, level data, scoring and progression are unchanged.

Validation: tools/render_perf_test.py passed (cache eviction/memory, repeated
text pixels, mobile fallback, touch coordinates, resize). Desktop CPU comparison
at 1200x2000: old scaling 8.01 ms, new scaling 1.68 ms per frame. This is not
tablet FPS. tools/ui_test.py and tools/polish_test.py passed. All 100 levels
completed with three stars through tools/test_play_all.py.

The source archive is not an installable update. A new Android artifact must be
built and signed through the existing Play upload-key workflow, then installed
and measured on the affected tablet. The current cloud notebook is the old APK
workflow; the notebook used for the published 5.1.1 AAB has been requested.
