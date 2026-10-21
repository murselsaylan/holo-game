"""Short edits of newly captured HoloGame 1.0.8 footage, with actual event SFX."""
from pathlib import Path
import json,math,subprocess,zipfile
import numpy as np
from PIL import Image,ImageDraw,ImageFont
import imageio_ffmpeg

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT.parent/'HOLOmedya/Son_Surum_108_Cekimler'
OUT=ROOT.parent/'HOLOmedya/Son_Surum_108_Reels'
OUT.mkdir(exist_ok=True)
FF=imageio_ffmpeg.get_ffmpeg_exe();SR=48000

def font(n):return ImageFont.truetype(str(ROOT/'assets/fonts/Rajdhani-Bold.ttf'),n)
def meta(lid,kind):return json.loads((SOURCE/f'level_{lid:03d}_{kind}.json').read_text(encoding='utf8'))
def tail(lid,kind,seconds,hold=1.4):
    m=meta(lid,kind);end=m['duration']-3+hold
    return (SOURCE/m['file'],max(0,end-seconds),seconds)

def audio(path):
    p=subprocess.run([FF,'-v','error','-i',str(path),'-f','f32le','-ac','2','-ar',str(SR),'-'],capture_output=True,check=True)
    return np.frombuffer(p.stdout,dtype='<f4').reshape(-1,2).copy()

def render(name,shots,headings,line,caption,footer='OYUN PROFİLDE • HAMLE SENDE'):
    total=sum(x[2] for x in shots);music=audio(ROOT.parent/'HOLOmedya/Olo_Reels_Heyecanli/HOLO_Neon_Rush_140BPM.wav')
    mixed=np.tile(music,(math.ceil(total*SR/len(music)),1))[:int(total*SR)]*.55
    sprite=Image.open(ROOT/'assets/olo/finger_guns.png').convert('RGBA');sprite.thumbnail((135,170))
    wr=imageio_ffmpeg.write_frames(str(OUT/(name+'_visual.mp4')),(720,1280),fps=30,quality=9,macro_block_size=2,output_params=['-preset','fast']);wr.send(None)
    clock=0;frame=0;previews=[];cache={}
    for i,(path,start,duration) in enumerate(shots):
        cut=OUT/(name+f'_cut{i}.mp4')
        subprocess.run([FF,'-y','-ss',str(start),'-i',str(path),'-t',str(duration),'-vf','scale=720:1296:flags=lanczos,crop=720:1280:0:8,fps=30','-an','-c:v','libx264','-crf','17',str(cut)],capture_output=True,check=True)
        events=json.loads(path.with_suffix('.json').read_text(encoding='utf8'))['sound_events']
        for ev in events:
            if start<=ev['t']<start+duration:
                sound=ROOT/'assets/audio'/(ev['sound']+'.wav')
                if not sound.exists():continue
                if sound not in cache:cache[sound]=audio(sound)
                data=cache[sound];at=int((clock+ev['t']-start)*SR);n=min(len(data),len(mixed)-at)
                if n>0:mixed[at:at+n]+=data[:n]*.65
        reader=imageio_ffmpeg.read_frames(str(cut),pix_fmt='rgb24');next(reader)
        header=Image.new('RGBA',(720,1280));hd=ImageDraw.Draw(header)
        for y in range(180):hd.line((0,y,720,y),fill=(5,10,24,int(245*max(0,1-y/180)**.5)))
        hd.text((38,36),'HOLO  /  İKİ KÜRE. TEK DOKUNUŞ.',font=font(23),fill=(90,225,240))
        size=49
        while hd.textbbox((0,0),headings[i],font=font(size))[2]>640:size-=1
        hd.text((38,77),headings[i],font=font(size),fill='white')
        for raw in reader:
            t=frame/30;im=Image.frombytes('RGB',(720,1280),raw).convert('RGBA');im.alpha_composite(header)
            d=ImageDraw.Draw(im)
            if t>=total-3.5:
                # Small late reaction: avoid covering the main action during the hook.
                d.rounded_rectangle((177,1060,675,1165),radius=20,fill=(7,20,34,245),outline=(35,210,235),width=2)
                d.text((195,1068),'OLO',font=font(21),fill=(75,225,240))
                words=line.split();lines=[];row=''
                for word in words:
                    test=(row+' '+word).strip()
                    if d.textbbox((0,0),test,font=font(30))[2]>455:lines.append(row);row=word
                    else:row=test
                lines.append(row)
                for k,row in enumerate(lines):d.text((195,1093+k*32),row,font=font(30),fill='white')
                im.alpha_composite(sprite,(25,1030))
                d.rounded_rectangle((175,1180,675,1224),radius=16,fill=(7,20,34,245))
                d.text((425,1202),footer,font=font(23),anchor='mm',fill=(210,235,245))
            rgb=im.convert('RGB');wr.send(np.asarray(rgb).tobytes())
            if frame%180==60:previews.append(rgb.resize((240,427)))
            frame+=1
        clock+=duration
    wr.close()
    mixed=np.tanh(mixed);peak=np.max(np.abs(mixed))
    if peak>.94:mixed*=.94/peak
    fade=int(SR*.45);mixed[-fade:]*=np.linspace(1,0,fade)[:,None]
    wav=OUT/(name+'_audio.wav')
    import wave
    with wave.open(str(wav),'wb') as f:f.setnchannels(2);f.setsampwidth(2);f.setframerate(SR);f.writeframes((mixed*32767).astype('<i2').tobytes())
    final=OUT/(name+'.mp4')
    subprocess.run([FF,'-y','-i',str(OUT/(name+'_visual.mp4')),'-i',str(wav),'-map','0:v','-map','1:a','-vf','scale=1080:1920:flags=lanczos','-c:v','libx264','-preset','fast','-crf','18','-c:a','aac','-b:a','192k','-t',str(total),'-movflags','+faststart',str(final)],capture_output=True,check=True)
    subprocess.run([FF,'-v','error','-i',str(final),'-f','null','-'],capture_output=True,check=True)
    sheet=Image.new('RGB',(240*max(1,len(previews)),427))
    for k,p in enumerate(previews):sheet.paste(p,(k*240,0))
    sheet.save(OUT/(name+'_onizleme.jpg'),quality=92)
    (OUT/(name+'_aciklama.txt')).write_text(caption+'\n\nGörüntüler HOLO 1.0.8 oyun motorundan alınmıştır. Kontrollü tanıtım kaydı; gerçek dokunuş girdileri, gerçek fizik ve sonuçlar.\n#HOLO #MobilOyun #IndieGame #RefleksOyunu',encoding='utf8')
    print('FINAL VERIFIED',final,flush=True)

def main():
    render('01_izlerken_oynarken',[tail(47,'clean',8),tail(47,'fail',8)],['İZLERKEN BEN: KOLAY.','OYNARKEN BEN: BİR SANİYE…'],'Aynı bölüm. Bir hamle farkı.','İzlerken yolu gördün. Peki dokunuşun zamanı? 👀\nOyunu indirmek için profildeki bağlantı.')
    render('02_son_donus',[tail(63,'fail',14,2)],['SON DÖNÜŞÜ GEÇER MİYDİN?'],'Sen burada bekler miydin?','Bir koridor daha vardı. Sen burada ne yapardın?\nHOLO indirme bağlantısı profilde.')
    render('03_temiz_gecis',[tail(85,'clean',16,2)],['BU AKIŞA PUANIN KAÇ?'],'Bir de senin geçişini görelim.','Bu sefer oldu. 🩵🩷\nHOLO 1.0.8 — gerçek bölüm, gerçek geçiş.\nOyunun bağlantısı profilde.')
    shots=[]
    for lid in [23,47,63,85]:
        m=meta(lid,'clean');shots.append((SOURCE/m['file'],max(3,m['game_time']*.45),4))
    render('04_hangi_bolum',[*shots],['MOR: SAKİN BAŞLIYORUZ.','YEŞİL: BİRAZ DİKKAT.','TURUNCU: ŞİMDİ ZAMANLAMA.','PEKİ BU BÖLÜM?'],'Sen hangisinde takılırdın?','Mor, yeşil, turuncu ve son sektör.\nHangi bölüm daha çok uğraştırırdı?\nHOLO indirme bağlantısı profilde.')
    with zipfile.ZipFile(OUT/'Son_Surum_108_Reels_Paketi.zip','w',compression=zipfile.ZIP_STORED) as z:
        for f in OUT.iterdir():
            if f.name in [n+'.mp4' for n in ['01_izlerken_oynarken','02_son_donus','03_temiz_gecis','04_hangi_bolum']] or f.name.endswith('_aciklama.txt') or f.name.endswith('_onizleme.jpg'):z.write(f,f.name)
    print('FOUR LATEST VERSION EDITS READY',flush=True)

if __name__=='__main__':main()
