"""Deliver music-only editions: retain the completed visuals, remove all TTS."""
from pathlib import Path
import subprocess
import zipfile
import imageio_ffmpeg

ROOT=Path(__file__).resolve().parents[1]
PACK=ROOT.parent/'HOLOmedya'/'Olo_Reels_Seri'
FF=imageio_ffmpeg.get_ffmpeg_exe()
NAMES=['01_bolum_degisti','02_dokunma_zamani','03_son_bir_bolum']
for name in NAMES:
    source=PACK/(name+'.mp4')
    target=PACK/(name+'_muzikli.mp4')
    subprocess.run([FF,'-y','-i',str(source),'-stream_loop','-1','-i',str(ROOT/'assets/audio/bgm_synthwave.wav'),'-map','0:v:0','-map','1:a:0','-c:v','copy','-af','volume=0.45,afade=t=in:st=0:d=0.6,afade=t=out:st=33.8:d=2.2','-c:a','aac','-b:a','192k','-ar','48000','-t','36','-movflags','+faststart',str(target)],capture_output=True,check=True)
    check=subprocess.run([FF,'-v','error','-i',str(target),'-f','null','-'],capture_output=True,text=True)
    assert check.returncode==0,check.stderr
    caption=PACK/name/'Instagram_metin.txt'
    text=caption.read_text(encoding='utf8').split('Ses:')[0]
    text+='Ses: sözsüz HOLO synthwave müziği. Olo replikleri yalnızca yazıyla.\n'
    caption.write_text(text,encoding='utf8')
    print('PASS music-only:',target,flush=True)
with zipfile.ZipFile(PACK/'Olo_Reels_Paketi.zip','w',compression=zipfile.ZIP_STORED) as z:
    for name in NAMES:
        for file in [PACK/(name+'_muzikli.mp4'),PACK/(name+'_kapak.jpg'),PACK/name/'Instagram_metin.txt']:
            z.write(file, name+'_aciklama.txt' if file.name=='Instagram_metin.txt' else file.name)
print('READY',PACK/'Olo_Reels_Paketi.zip')
