"""Isolated, real-engine footage for the three-month social season."""
import capture_latest_social as base
import json,hashlib,random
from pathlib import Path
import numpy as np
import imageio_ffmpeg
from sim import LevelData,replay,SIM_DT
import pygame,holo,locales
from version import __version__

OUT=base.ROOT.parent/'HOLOmedya/Uc_Aylik_Sezon/kaynak'
OUT.mkdir(parents=True,exist_ok=True)
LEVELS=[5,9,13,18,27,31,35,39,51,55,59,67,71,75,79,88,92,96]

def find_failure(raw):
    taps=raw['ref_taps'];level=LevelData(raw)
    for idx in range(len(taps)-1,0,-1):
        trial=taps[:idx]+taps[idx+1:]
        sim,_=replay(level,trial,max_seconds=100)
        if sim.dead and .25<sim.max_progress<.995:return trial,sim.t
    return None,None

def main():
    random.seed(81);pygame.init();g=holo.HoloGame(headless=True)
    g.save_mgr.data.update(is_profile_set=True,player_name='HOLO',player_country='TR',howto_seen=True)
    g.save_mgr.settings.update(online=False,ghost_race=False,screen_shake=True)
    g.save_mgr.language='tr';locales.set_language('tr');g.on_language_change();g._maybe_login_popup=lambda:None
    events=[];clock=[0.0];original=g.audio.play_sfx
    def sfx(name,*a,**kw):
        if not name.startswith('sfx_olo'):events.append({'t':clock[0],'sound':name})
        return original(name,*a,**kw)
    g.audio.play_sfx=sfx
    for lid in LEVELS:
        raw=json.loads((base.ROOT/'levels'/f'level{lid}.json').read_text(encoding='utf8'))
        fs,ft=find_failure(raw)
        for kind,taps in [('clean',raw['ref_taps']),('fail',fs)]:
            if taps is None:continue
            path=OUT/f'level_{lid:03d}_{kind}.mp4'
            if path.exists() and path.with_suffix('.json').exists():continue
            sim,_=replay(LevelData(raw),taps,max_seconds=100)
            start=max(0,sim.t-21);assert g.load_and_play_level(lid)
            g._autoplay=None;g.toasts=[];g.olo.hide();events.clear();ti=0;step=0;finish=None;nframes=0
            wr=imageio_ffmpeg.write_frames(str(path),(540,972),fps=30,quality=8,macro_block_size=2,output_params=['-preset','ultrafast']);wr.send(None)
            while step<60*105:
                clock[0]=step/60
                if g.state=='playing':
                    while ti<len(taps) and taps[ti]<=g.sim.n:g.swap_pivot();ti+=1
                g.update(SIM_DT,(450,800));g.toasts=[]
                if g.state in ('victory','failed') and finish is None:finish=step
                if step%2==0 and step/60>=start:
                    g.draw();fr=pygame.transform.smoothscale(g.frame,(540,972))
                    wr.send(np.ascontiguousarray(pygame.surfarray.array3d(fr).swapaxes(0,1)).tobytes());nframes+=1
                step+=1
                if finish is not None and step-finish>=150:break
            wr.close();expected='victory' if kind=='clean' else 'failed'
            if g.state!=expected:raise RuntimeError((lid,kind,g.state))
            actual_start=__import__('math').ceil(start*30)/30
            data={'file':path.name,'version':__version__,'level':lid,'kind':kind,'terminal_state':g.state,'duration':nframes/30,'game_time':g.sim.t,'max_progress':g.sim.max_progress,'clip_start':actual_start,'sound_events':[{'t':round(e['t']-actual_start,4),'sound':e['sound']} for e in events if e['t']>=actual_start],'taps':taps,'forced_outcomes':False,'capture':'HoloGame real 60Hz inputs, last 21 seconds + result','sim_sha256':hashlib.sha256((base.ROOT/'sim.py').read_bytes()).hexdigest()}
            path.with_suffix('.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8')
            print('CAPTURE',lid,kind,round(nframes/30,1),flush=True)
    pygame.quit();print('SEASON CAPTURE COMPLETE',flush=True)
if __name__=='__main__':main()
