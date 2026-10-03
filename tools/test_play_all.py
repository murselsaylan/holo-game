"""Play all 100 levels end-to-end through HoloGame and report results."""
import os
import sys
import time
import tempfile

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ["HOLO_SERVER"] = "http://127.0.0.1:1"
os.environ["HOLO_SAVE_DIR"] = tempfile.mkdtemp(prefix="holo_all_levels_")

import pygame
import holo
from sim import SIM_DT

def play_level(game, level_id):
    game.save_mgr.data["howto_seen"] = True
    game.attempts = 1
    loaded = game.load_and_play_level(level_id)
    if not loaded:
        return False, "failed_to_load", 0, None
    game.state = "playing"
    
    taps = sorted(game.level.data.raw.get("ref_taps", []))
    ti = 0
    frames = 0
    max_frames = 60 * 300  # 5 minutes max per level
    
    while game.state == "playing" and frames < max_frames:
        while ti < len(taps) and taps[ti] <= game.sim.n:
            game.swap_pivot()
            ti += 1
        game.update_gameplay(SIM_DT)
        game._update_camera(SIM_DT)
        frames += 1
        
    res = game.victory_modal.r if game.victory_modal else None
    return (game.state == "victory"), game.state, frames, res

def main():
    game = holo.HoloGame(headless=True)
    game.online.url = "http://127.0.0.1:1"
    
    print("=" * 75)
    print("HOLO: 100 BOLUMUN TAMAMINI TEK TEK OYNAYIP TEST ETME BASLADI")
    print("=" * 75)
    
    t_start = time.time()
    passed = 0
    failed = []
    
    sector_results = {1: [], 2: [], 3: [], 4: [], 5: []}
    
    for lid in range(1, 101):
        sector = (lid - 1) // 20 + 1
        t0 = time.time()
        ok, state, frames, res = play_level(game, lid)
        dur = time.time() - t0
        
        if ok and res and res.get("stars", 0) == 3:
            passed += 1
            stars = res["stars"]
            score = res["level_total"]
            rank = res["rank"]
            sec_time = res["time"]
            swaps = res["swaps"]
            sector_results[sector].append(lid)
            status_str = f"OK (3*, {rank}, {score}p, {swaps} adim, {sec_time:.1f}s)"
        else:
            failed.append((lid, state, res))
            status_str = f"HATA (state={state}, res={res})"
            
        print(f"Bolum {lid:3d}/100 [Sektor {sector}] : {status_str} ({dur:.2f}s)")
        sys.stdout.flush()
        
    t_total = time.time() - t_start
    print("\n" + "=" * 75)
    print(f"TEST TAMAMLANDI: {passed}/100 Bolum Basariyla Gecildi! (Toplam sure: {t_total:.1f}s)")
    print("=" * 75)
    
    for sec in range(1, 6):
        cnt = len(sector_results[sec])
        print(f"  Sektor {sec} (Bolum {(sec-1)*20+1}-{sec*20}): {cnt}/20 Basarili")
        
    if failed:
        print(f"\nBASARISIZ BOLUMLER ({len(failed)} adet):")
        for f in failed:
            print(f"  - Bolum {f[0]}: state={f[1]}, res={f[2]}")
        sys.exit(1)
    else:
        print("\nTUM BOLUMLER HATASIZ CALISIYOR VE 3 YILDIZLA BITIYOR!")
        sys.exit(0)

if __name__ == "__main__":
    main()
