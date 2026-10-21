"""Capture the current HoloGame renderer and real input-driven outcomes.
Separate save, offline, no forced deaths/wins or physics changes.
"""
import os,sys,tempfile,json,hashlib,random,math
from pathlib import Path
os.environ['SDL_VIDEODRIVER']='dummy'
os.environ['SDL_AUDIODRIVER']='dummy'
os.environ['HOLO_SAVE_DIR']=tempfile.mkdtemp(prefix='holo_social_capture_')
os.environ['HOLO_SERVER']='http://127.0.0.1:1'
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import pygame
import numpy as np
import imageio_ffmpeg
import holo,locales
from sim import LevelData,replay,SIM_DT
from version import __version__

OUT=ROOT.parent/'HOLOmedya'/'Son_Surum_108_Cekimler'
OUT.mkdir(exist_ok=True)

def failure(raw):
    level=LevelData(raw);taps=raw['ref_taps']
    candidates=[]
    for i in range(len(taps)-1,max(0,len(taps)//3),-1):
        trial=taps[:i]+taps[i+1:]
        s,res=replay(level,trial,max_seconds=90)
        if s.dead and .4<s.max_progress<.995 and s.t<65:
            candidates.append((s.max_progress,s.t,trial))
    if not candidates:raise RuntimeError('No authentic failure found')
    return max(candidates,key=lambda x:x[0])[2]

def main():
    random.seed(77);pygame.init();g=holo.HoloGame(headless=True)
    sm=g.save_mgr;sm.data.update(is_profile_set=True,player_name='HOLO',player_country='TR',howto_seen=True)
    sm.settings['online']=False;sm.settings['ghost_race']=False
    sm.settings['screen_shake']=True;sm.language='tr';locales.set_language('tr');g.on_language_change()
    g._maybe_login_popup=lambda:None
    manifest=[];events=[];clock=[0.0]
    original=g.audio.play_sfx
    def sfx(name,*a,**kw):
        if not name.startswith('sfx_olo'):events.append({'t':round(clock[0],4),'sound':name})
        return original(name,*a,**kw)
    g.audio.play_sfx=sfx
    for lid in [23,47,63,85]:
        raw=json.loads((ROOT/'levels'/f'level{lid}.json').read_text(encoding='utf8'))
        for kind,taps in [('clean',raw['ref_taps']),('fail',failure(raw))]:
            path=OUT/f'level_{lid:03d}_{kind}.mp4'
            if path.exists() and path.with_suffix('.json').exists():
                manifest.append(json.loads(path.with_suffix('.json').read_text(encoding='utf8')));continue
            assert g.load_and_play_level(lid)
            g._autoplay=None;g.toasts=[];events.clear();clock[0]=0
            g.olo.hide()
            ti=0;frame=0;finish=None;draw_size=(720,1296)
            wr=imageio_ffmpeg.write_frames(str(path),draw_size,fps=30,codec='libx264',quality=9,macro_block_size=2,output_params=['-preset','fast']);wr.send(None)
            while frame<60*95:
                clock[0]=frame/60
                if g.state=='playing':
                    while ti<len(taps) and taps[ti]<=g.sim.n:g.swap_pivot();ti+=1
                g.update(SIM_DT,(450,800));g.toasts=[]
                if g.state in ('victory','failed') and finish is None:finish=frame
                if frame%2==0:
                    g.draw();fr=pygame.transform.smoothscale(g.frame,draw_size)
                    wr.send(np.ascontiguousarray(pygame.surfarray.array3d(fr).swapaxes(0,1)).tobytes())
                frame+=1
                if finish is not None and frame-finish>=60*3:break
            wr.close()
            expected='victory' if kind=='clean' else 'failed'
            assert g.state==expected,(lid,kind,g.state)
            meta={'file':path.name,'version':__version__,'level':lid,'kind':kind,'terminal_state':g.state,'duration':round(frame/60,3),'game_time':g.sim.t,'max_progress':g.sim.max_progress,'taps':taps,'sound_events':list(events),'sim_sha256':hashlib.sha256((ROOT/'sim.py').read_bytes()).hexdigest(),'capture':'HoloGame.update + HoloGame.draw, real tap inputs at 60Hz, video 30fps','forced_outcomes':False}
            path.with_suffix('.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf8');manifest.append(meta)
            print('CAPTURED',path.name,g.state,round(g.sim.max_progress*100),round(frame/60,1),flush=True)
    (OUT/'capture_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
    pygame.quit();print('LATEST VERSION CAPTURE COMPLETE',__version__,flush=True)

if __name__=='__main__':main()
