"""Standalone social export; uses supplied gameplay, never changes the game."""
import asyncio
import base64
import math
import subprocess
from pathlib import Path

import edge_tts
import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT.parent / 'HOLOmedya' / 'reels_olo_yavas'
OUT.mkdir(exist_ok=True)
FF = imageio_ffmpeg.get_ffmpeg_exe()
W, H, FPS = 720, 1280, 30
BEATS = [
    (0, 6, 'smug', 'Ben Olo. Şu aradan geçecektik sadece.', 'ŞU ARADAN GEÇECEKTİK.'),
    (6, 12, 'finger_guns', 'Tek dokunuş. Bu sefer olur.', 'BU SEFER TAMAM.'),
    (12, 18, 'shock', 'Bir tık erken oldu galiba.', 'BİR TIK ERKEN…'),
    (18, 24, 'laugh_point', 'Az kalmıştı. Ben bir şey demiyorum.', 'AZ KALMIŞTI.'),
    (24, 30, 'smug', 'Son bir deneme. Gerçekten son.', 'SON BİR DENEME.'),
    (30, 36, 'finger_guns', 'Senin aklında bir hamle var sanki.', 'SENCE GEÇİLİR Mİ?'),
]
CUTS = [(0,0,3),(0,3,5),(0,8,6),(0,16,6),(0,3,5),(0,8,6)]
CAPTION = 'Şu aradan geçecektik sadece. 😶\nSenin aklındaki hamle ne?'
MUSIC_ONLY = False
MUSIC = ROOT/'assets/audio/bgm_synthwave.wav'
SOURCES = None
SOURCE_FILTER = ''

def font(n):
    return ImageFont.truetype(str(ROOT / 'assets/fonts/Rajdhani-Bold.ttf'), n)

async def voices():
    for i, (_, _, _, text, _) in enumerate(BEATS):
        target = OUT / f'olo_voice_{i}.wav'
        if not target.exists() or target.stat().st_size < 100:
            text = text.replace('’', " ")
            ps = "Add-Type -AssemblyName System.Speech; $s=New-Object System.Speech.Synthesis.SpeechSynthesizer; $s.SelectVoice('Microsoft Tolga'); $s.Rate=0; $s.SetOutputToWaveFile('" + str(target).replace("'", "''") + "'); $s.Speak('" + text.replace("'", "''") + "'); $s.Dispose()"
            subprocess.run(['powershell','-NoProfile','-EncodedCommand',base64.b64encode(ps.encode('utf-16le')).decode()],check=True,capture_output=True)

def panel(i):
    _, _, pose, text, heading = BEATS[i]
    im = Image.new('RGBA', (W, H))
    d = ImageDraw.Draw(im)
    for y in range(230):
        d.line((0, y, W, y), fill=(5, 10, 24, int(245 * (1-y/230)**.45)))
    for y in range(910,H):
        d.line((0,y,W,y),fill=(5,10,24,int(245*min(1,(y-910)/120))))
    d.text((42,68),'SAYLANS  /  HOLO',font=font(25),fill=(80,220,240))
    size=52
    ft=font(size)
    while d.textbbox((0,0),heading,font=ft)[2]>W-84:
        size-=2;ft=font(size)
    d.text((42,107),heading,font=ft,fill='white')
    d.rounded_rectangle((235,1000,675,1155),radius=23,fill=(13,26,44,245),outline=(40,215,240,255),width=2)
    d.text((258,1014),'OLO',font=font(25),fill=(60,230,240))
    words=text.split(); lines=[];line=''
    for word in words:
        test=(line+' '+word).strip()
        if d.textbbox((0,0),test,font=font(35))[2]>390:
            lines.append(line);line=word
        else:line=test
    lines.append(line)
    for j,line in enumerate(lines):d.text((258,1050+j*37),line,font=font(35),fill='white')
    d.text((W//2,1190),'HOLO  •  İNDİRME BAĞLANTISI PROFİLDE' if i==5 else 'HOLO  /  İKİ KÜRE, TEK NABIZ',font=font(26),anchor='mm',fill=(210,230,245))
    sprite=Image.open(ROOT/'assets/olo'/f'{pose}.png').convert('RGBA')
    sprite.thumbnail((225,265),Image.Resampling.LANCZOS)
    return im,sprite

def main():
    if not MUSIC_ONLY:
        asyncio.run(voices())
    clips=SOURCES or sorted((ROOT.parent / 'HOLOmedya').glob('WhatsApp*.mp4'))
    # All cuts are from the user's two original recordings.
    # Deaths and retries from the same real level. No fabricated play or scores.
    cuts=CUTS
    for i,(source,start,duration) in enumerate(cuts):
        timing = f'setpts=PTS-STARTPTS,tpad=stop_mode=clone:stop_duration={6-duration}' if duration<6 else 'setpts=PTS-STARTPTS'
        subprocess.run([FF,'-y','-ss',str(start),'-t',str(duration),'-i',str(clips[source]),'-t','6','-vf',f'{SOURCE_FILTER}{timing},scale=590:1280:flags=lanczos,pad=720:1280:65:0:color=0x060d1c,fps=30','-an','-c:v','libx264','-preset','fast','-crf','17',str(OUT/f'cut_{i}.mp4')],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,check=True)
    listing=OUT/'cuts.txt';listing.write_text('\n'.join(f"file 'cut_{i}.mp4'" for i in range(6)),encoding='utf8')
    subprocess.run([FF,'-y','-f','concat','-safe','0','-i',str(listing),'-c','copy',str(OUT/'gameplay.mp4')],capture_output=True,check=True)
    reader=imageio_ffmpeg.read_frames(str(OUT/'gameplay.mp4'),pix_fmt='rgb24');next(reader)
    writer=imageio_ffmpeg.write_frames(str(OUT/'visual.mp4'),(W,H),fps=FPS,codec='libx264',quality=8,macro_block_size=2,output_params=['-preset','fast','-pix_fmt','yuv420p'])
    writer.send(None); overlays=[panel(i) for i in range(6)]
    previews=[]
    for n,raw in enumerate(reader):
        t=n/FPS;i=min(5,int(t/6)); overlay,sprite=overlays[i]
        im=Image.frombytes('RGB',(W,H),raw).convert('RGBA');im.alpha_composite(overlay)
        phase=t%6;pop=min(1,phase/.40); y=int(970+(1-pop)*300+math.sin(t*3)*3)
        im.alpha_composite(sprite,(20,y))
        rgb=im.convert('RGB');writer.send(np.asarray(rgb).tobytes())
        if n in [60,240,420,600,780,960]:previews.append(rgb.resize((240,427)))
    writer.close()
    sheet=Image.new('RGB',(720,854))
    for i,p in enumerate(previews):sheet.paste(p,((i%3)*240,(i//3)*427))
    sheet.save(OUT/'HOLO_Reels_onizleme.jpg',quality=92)
    if MUSIC_ONLY:
        subprocess.run([FF,'-y','-i',str(OUT/'visual.mp4'),'-i',str(MUSIC),'-map','0:v','-map','1:a','-vf','scale=1080:1920:flags=lanczos','-c:v','libx264','-preset','fast','-crf','18','-af','afade=t=in:d=0.3,afade=t=out:st=34.5:d=1.5','-c:a','aac','-b:a','192k','-ar','48000','-t','36','-movflags','+faststart',str(OUT/'HOLO_Olo_Reels_TR.mp4')],capture_output=True,check=True)
        (OUT/'Instagram_metin.txt').write_text(CAPTION+'\nHOLO — İki küre, tek nabız.\nBağlantı profilde.\n#HOLO #MobilOyun #Reels #IndieGame\n\nSözsüz özgün elektronik müzik. Olo yalnızca yazıyla konuşur.\n',encoding='utf8')
        print('RENDERED',OUT,flush=True)
        return
    args=[FF,'-y','-i',str(OUT/'visual.mp4')]
    for i in range(6):args+=['-i',str(OUT/f'olo_voice_{i}.wav')]
    args+=['-stream_loop','-1','-i',str(ROOT/'assets/audio/bgm_synthwave.wav')]
    filters=[f'[{i+1}:a]adelay={i*6000+650}|{i*6000+650},volume=1.5[v{i}]' for i in range(6)]
    filters+=['[7:a]volume=0.08,afade=t=out:st=34:d=2[m]', ''.join(f'[v{i}]' for i in range(6))+'[m]amix=inputs=7:duration=longest:normalize=0,alimiter=limit=0.95[a]']
    args+=['-filter_complex',';'.join(filters),'-map','0:v','-map','[a]','-vf','scale=1080:1920:flags=lanczos','-c:v','libx264','-preset','fast','-crf','18','-c:a','aac','-b:a','192k','-ar','48000','-t','36','-movflags','+faststart',str(OUT/'HOLO_Olo_Reels_TR.mp4')]
    subprocess.run(args,capture_output=True,check=True)
    (OUT/'Instagram_metin.txt').write_text(CAPTION+'\nHOLO — İki küre, tek nabız.\nİndirme bağlantısı profilde.\n\n#HOLO #MobilOyun #Oyun #Reels #IndieGame\n\nSes: Olo için sentetik Türkçe anlatım. Müzik: oyunun kendi synthwave parçası.\n',encoding='utf8')
    print(OUT/'HOLO_Olo_Reels_TR.mp4')

if __name__=='__main__':main()
