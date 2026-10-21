"""Three focused edits for the first measured Instagram publishing batch."""
import json,math,subprocess
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
import imageio_ffmpeg
import make_olo_reel as r

OUT=r.ROOT.parent/'HOLOmedya'/'Instagram_Yayin_Paketi'
OUT.mkdir(exist_ok=True)
NEW=OUT.parent/'WhatsApp Video 2026-10-16 at 18.51.18.mp4'
PROTO=OUT.parent/'HOLO_Gelisim_Hikayesi/temel_mekanik.mp4'
DATA=[
('01_son_hamle',[(NEW,99),(NEW,105)],['SADECE ŞU ARADAN…','SEN NEREDE DOKUNURDUN?'],['','Ben bir tık daha beklerdim. Galiba.'],
'Son hamlede sen dokunur muydun, bekler miydin? 👀\nHOLO: iki küre, tek dokunuş. Olo izliyor.\nOyunu indir: profildeki bağlantı.\n#HOLO #MobilOyun #RefleksOyunu #IndieGame'),
('02_olo_yorum_bekliyor',[(NEW,58),(NEW,76),(NEW,184)],['OLO BİR ŞEY DEMİYOR.','TAMAM. BİR ŞEY DİYECEK.','OLO BUNA NE DESİN?'],['Şu boşluk tam bize göre.','Biraz fazla yaklaştık.','Bir sonraki lafımı yorumlara bırak.'],
'Olo bu denemeye ne desin? En sevdiğimiz öneriyi sonraki Olo paylaşımında kullanmak istiyoruz. 👀\nSence tek cümlesi ne olurdu?\nHOLO indirme bağlantısı profilde.\n#HOLO #Olo #MobilOyun #IndieGame'),
('03_iki_kureden_bugune',[(PROTO,3),(NEW,3),(NEW,174)],['ÖNCE SADECE İKİ KÜRE.','SONRA BİR DÜNYA.','ŞİMDİ HAMLE SENDE.'],['İlk mekaniği böyle anlatabiliriz.','Duvarlar ve bölümlerle yol açıldı.','HOLO’nun gelişim hikâyesi profilde.'],
'İki küre fikrinden HOLO’nun bugünkü dünyasına. 🩵🩷\nİlk sahne temel mekaniğin CANLANDIRMASIDIR; eski bir prototip kaydı değildir. Devamındaki görüntüler gerçek oyun kaydından.\nGelişim serisi ve oyunun indirme bağlantısı profilde.\n#HOLO #OyunGelistirme #IndieGame #MobilOyun')]

def render(name,shots,heads,lines,caption):
    total=len(shots)*6
    r.BEATS=[(i*6,(i+1)*6,['smug','shock','finger_guns'][i],lines[i],heads[i]) for i in range(len(shots))]
    overlays=[]
    for i in range(len(shots)):
        p,s=r.panel(i)
        if not lines[i]:
            # Gameplay first: no speech panel or mascot during the opening.
            p.paste((0,0,0,0),(0,910,720,1280));s=None
        overlays.append((p,s))
    visual=OUT/(name+'_visual.mp4');wr=imageio_ffmpeg.write_frames(str(visual),(720,1280),fps=30,quality=8,macro_block_size=2);wr.send(None)
    for i,(source,start) in enumerate(shots):
        cut=OUT/(name+f'_cut{i}.mp4')
        vf='drawbox=x=0:y=0:w=iw:h=110:color=0x060d1c:t=fill,scale=590:1280:flags=lanczos,pad=720:1280:65:0:color=0x060d1c,fps=30'
        subprocess.run([r.FF,'-y','-ss',str(start),'-i',str(source),'-t','6','-vf',vf,'-an','-c:v','libx264','-crf','17',str(cut)],capture_output=True,check=True)
        reader=imageio_ffmpeg.read_frames(str(cut),pix_fmt='rgb24');next(reader)
        for j,raw in enumerate(reader):
            im=Image.frombytes('RGB',(720,1280),raw).convert('RGBA');panel,sprite=overlays[i];im.alpha_composite(panel)
            if sprite:im.alpha_composite(sprite,(20,int(970+math.sin(j/30*3)*3)))
            d=ImageDraw.Draw(im)
            if i==len(shots)-1:
                d.rectangle((0,1170,720,1230),fill=(6,13,28));d.text((360,1190),'HOLO • BAĞLANTI PROFİLDE',font=r.font(26),anchor='mm',fill=(210,230,245))
            wr.send(np.asarray(im.convert('RGB')).tobytes())
    wr.close();v=OUT/(name+'.mp4')
    music=OUT.parent/'Olo_Reels_Heyecanli/HOLO_Neon_Rush_140BPM.wav'
    subprocess.run([r.FF,'-y','-i',str(visual),'-i',str(music),'-map','0:v','-map','1:a','-vf','scale=1080:1920:flags=lanczos','-c:v','libx264','-crf','18','-preset','fast','-af',f'volume=0.85,afade=t=out:st={total-1}:d=1','-c:a','aac','-b:a','192k','-t',str(total),'-movflags','+faststart',str(v)],capture_output=True,check=True)
    subprocess.run([r.FF,'-v','error','-i',str(v),'-f','null','-'],capture_output=True,check=True)
    subprocess.run([r.FF,'-y','-ss','2','-i',str(v),'-frames:v','1',str(OUT/(name+'_kapak.jpg'))],capture_output=True,check=True)
    (OUT/(name+'_aciklama.txt')).write_text(caption,encoding='utf8');print('READY',v,flush=True)

if __name__=='__main__':
    for row in DATA:render(*row)
    (OUT/'yayin_listesi.json').write_text(json.dumps([{'file':row[0]+'.mp4','caption':row[-1]} for row in DATA],ensure_ascii=False,indent=2),encoding='utf8')
