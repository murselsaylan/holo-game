"""Corrupt / odd save files must never crash start-up.   python tools/save_fuzz_test.py"""
import os, sys, json, tempfile, importlib
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ["SDL_VIDEODRIVER"] = "dummy"; os.environ["SDL_AUDIODRIVER"] = "dummy"
CASES = {
    "root null": "null", "root list": "[]", "root string": '"x"', "empty file": "", "truncated": '{"save_version": 2, "level_s',
    "version null": '{"save_version": null}', "version text": '{"save_version": "2"}',
    "level_stats null": '{"save_version": 2, "level_stats": null}', "level_stats bad keys": '{"save_version": 2, "level_stats": {"level1": {"stars": 3}, "2": 5}}',
    "best_taps text": '{"save_version": 2, "level_stats": {"3": {"stars": 3, "best_score": 10, "best_taps": ["60", "x"]}}}',
    "best_taps negative": '{"save_version": 2, "level_stats": {"3": {"stars": 3, "best_taps": [-5, 10]}}}',
    "pending without level": '{"save_version": 2, "pending_runs": [{"taps": [1, 2]}, 7, null, {"level": "x", "taps": []}]}',
    "daily missing fields": '{"save_version": 2, "daily": {"date": "%s"}}' % __import__("datetime").date.today().isoformat(),
    "daily wrong type": '{"save_version": 2, "daily": 5, "weekly": []}',
    "settings list": '{"save_version": 2, "settings": []}',
    "campaign text": '{"save_version": 2, "campaign_level": "7", "unlocked_skins": null, "equipped_skin": 3}',
}
bad = 0
for name, text in CASES.items():
    d = tempfile.mkdtemp(prefix="holo_fuzz_")
    open(os.path.join(d, "save_data.json"), "w", encoding="utf-8").write(text)
    os.environ["HOLO_SAVE_DIR"] = d
    for m in ("paths", "save_manager"):
        sys.modules.pop(m, None)
    try:
        import save_manager as sm
        s = sm.SaveManager()
        # everything the first screens touch
        s.levels_cleared; s.highest_cleared; s.unlocked_level; s.campaign_level; s.total_score; s.get_total_stars()
        s.get_best_taps(3); s.get_level_best_time(2); s.queue_run(5, [10, 20]); s.drop_run(5)
        s._daily(); s._weekly(); s.is_skin_unlocked("neon_pulse"); s._check_skin_unlocks(); s.save()
        print("PASS", name)
    except Exception as e:
        bad += 1
        import traceback
        print("FAIL", name, "->", repr(e)); traceback.print_exc(limit=3)
print("ALL OK" if not bad else f"{bad} FAILED")
sys.exit(1 if bad else 0)
