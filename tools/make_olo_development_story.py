"""Six source-grounded development episodes; reconstruction always labelled."""
import concurrent.futures
import json
import math
import subprocess
import sys
import zipfile
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFont
import imageio_ffmpeg
import make_olo_reel as r

PACK=r.ROOT.parent/'HOLOmedya'/'HOLO_Gelisim_Hikayesi'
PACK.mkdir(exist_ok=True)
NEW=PACK.parent/'WhatsApp Video 2026-10-16 at 18.51.18.mp4'
DATA=[
('01_fikir_ve_mekanik','1/6 — İki küre, tek fikir.',[
('01/06 • BİR FİKİR','Ben Olo. HOLO nasıl kuruldu, anlatayım.'),
('İKİ KÜRE. TEK BAĞ.','Temelde birbirine bağlı iki küre var.'),
('BİRİ SABİT, BİRİ DÖNER.','Biri merkez olur. Diğeri etrafında döner.'),
('DOKUN. MERKEZ DEĞİŞSİN.','Dokununca görevleri değişir. Yol böyle açılır.'),
('KODDAN HAREKETE.','Bu mekanik Python ve Pygame ile kuruldu.'),
('SIRADA: İLK KORİDORLAR.','İki küre hazır. Peki nereye gidecekler?')]),
('02_bolumleri_kurmak','2/6 — Boşluktan bölüme.',[
('02/06 • BÖLÜM TASARIMI','Küreler dönüyor. Şimdi onlara bir yol lazım.'),
('ÖNCE KORİDORLAR.','Duvarlar ve dönüşlerle rotalar kuruldu.'),
('SONRA HAREKETLİ ENGELLER.','Hareketli duvarlar zamanlamayı değiştirdi.'),
('YENİ MEKANİKLER.','Kalkan, güç alanları ve lazerler eklendi.'),
('ZOR OLSUN. GEÇİLEBİLSİN.','Çözüm yolları gerçek fizikte test edildi.'),
('SIRADA: UZAYIN RENGİ.','Yol var. Şimdi bu dünyaya bir yüz verelim.')]),
('03_gorsel_dunya','3/6 — HOLO’nun uzayı.',[
('03/06 • GÖRSEL DÜNYA','Mekanik tek başına yetmez. Bir dünya lazım.'),
('UZAYIN KATMANLARI.','Arka planda yıldızlar, bulutsular ve gezegenler.'),
('HER SEKTÖRÜN BİR HAVASI.','Renkler ve dokular sektörlere göre değişir.'),
('KRİSTALDEN LAZERE.','Görüntüyle engeller aynı dünyanın parçası oldu.'),
('MENÜ DE BU DÜNYADA.','Menü ve arayüz de uzay temasına uyarlandı.'),
('SIRADA: BİTMEYEN YOL.','Peki bölüm bitince yol devam etse?')]),
('04_sonsuz_mod','4/6 — Biten bölümlerden sonsuz yola.',[
('04/06 • SONSUZ MOD','Bu kez hedef kapısı değil, daha uzağı düşündük.'),
('İLK FİKİR: HARİTALARI BAĞLA.','Ayrı bölüm tasarımları uç uca denendi.'),
('PORTAL DEĞİL, DEVAM EDEN YOL.','Harita yürüdüğün yolun devamı olsun istedik.'),
('HER GİRİŞTE YENİ BİR ROTA.','Rastgele rota fikriyle tekrar hissi azaltıldı.'),
('ZORLUK YAVAŞ YAVAŞ.','Engelleri kademeli açmak üzerine çalışıldı.'),
('SIRADA: SENİN REKORUN.','Yol uzadı. Şimdi rekora bir anlam verelim.')]),
('05_rekor_ve_kimlik','5/6 — Oyuncunun izi.',[
('05/06 • REKOR VE KİMLİK','Bölümü geçtin. Peki skorun nerede kalacak?'),
('SKORLAR ÇEVRİMİÇİ.','Sıralama için sunucu tarafı kuruldu.'),
('KOŞULAR DOĞRULANIYOR.','Gönderilen hamleler sunucuda yeniden oynatılır.'),
('DÜNYA VE ÜLKE SIRALAMASI.','Böylece skorunu diğer oyuncularla kıyaslarsın.'),
('BİR DE SENİN TARZIN.','Skinler kürelere ve aradaki bağa kimlik verdi.'),
('SIRADA: BİRİ DAHA GELİYOR.','Oyunda eksik bir ses vardı. Bence bendim.')]),
('06_olo_ve_son_dokunuslar','6/6 — Olo sahneye çıkıyor.',[
('06/06 • SIRA OLO’DA.','Evet. Bu bölümde ben varım.'),
('ÖNCE KARAKTER ÇALIŞMALARI.','Duruşlar, yüzler ve farklı tepkiler denendi.'),
('SONRA OYUNUN İÇİNE.','Kaybedince, kazanınca ve menüde karşılıyorum.'),
('DURUMA GÖRE BİR LAF.','Her denemeye aynı cümleyi söylemeyeyim dedik.'),
('GÖRSELLİĞİ KORU, AKIŞI İYİLEŞTİR.','Çizimleri önceden hazırlayıp takılmayı azalttık.'),
('İKİ KÜREDEN HOLO’YA.','Hikâye burada bitmiyor. Şimdi sıra sende.')]),
]

def smallfont(n):return ImageFont.truetype(str(r.ROOT/'assets/fonts/Rajdhani-Bold.ttf'),n)

def make_diagram(kind):
    out=PACK/(kind+'.mp4')
    if out.exists():return out
    w,h=384,832;writer=imageio_ffmpeg.write_frames(str(out),(w,h),fps=30,quality=8,macro_block_size=2);writer.send(None)
    pts=[(100,650),(280,650),(280,450),(110,450),(110,260),(270,260)]
    for n in range(1080):
        t=n/30;stage=int(t//6);im=Image.new('RGB',(w,h),(6,13,28));d=ImageDraw.Draw(im)
        for x in range(0,w,24):d.line((x,145,x,665),fill=(13,29,46))
        for y in range(145,665,24):d.line((0,y,w,y),fill=(13,29,46))
        d.text((w//2,150),'GELİŞİMİN CANLANDIRMASI',font=smallfont(19),anchor='mm',fill=(80,220,240))
        if kind=='temel_mekanik':
            pivot=(190+math.sin(t*.4)*24,410+math.cos(t*.35)*24);a=t*1.5;rad=86
            p=(pivot[0]+math.cos(a)*rad,pivot[1]+math.sin(a)*rad)
            d.ellipse((pivot[0]-rad,pivot[1]-rad,pivot[0]+rad,pivot[1]+rad),outline=(34,65,85),width=1)
            d.line((*pivot,*p),fill=(100,200,235),width=3)
            colors=[(0,220,255),(255,75,180)]
            for j,(x,y) in enumerate([pivot,p]):
                c=colors[(j+int(t//2))%2]
                d.ellipse((x-13,y-13,x+13,y+13),fill=c)
                d.ellipse((x-20,y-20,x+20,y+20),outline=c,width=2)
            d.text((192,580),'DOKUN → MERKEZİ DEĞİŞTİR',font=smallfont(23),anchor='mm',fill='white')
            if stage==4:
                d.rounded_rectangle((35,225,350,300),radius=8,fill=(10,25,40),outline=(50,100,125))
                d.text((52,244),'Python + Pygame',font=smallfont(26),fill=(90,230,245))
        elif kind=='harita_taslagi':
            count=min(6,2+stage)
            d.line(pts[:count],fill=(30,77,100),width=60)
            d.line(pts[:count],fill=(6,13,28),width=53)
            for a,b in zip(pts[:count],pts[1:count]):d.line((*a,*b),fill=(0,175,210),width=2)
            q=pts[min(count-1,int((t%6)/6*count))];d.ellipse((q[0]-8,q[1]-8,q[0]+8,q[1]+8),fill=(255,215,75))
            d.text((192,715),'ROTA → ENGEL → ÇÖZÜM',font=smallfont(24),anchor='mm',fill='white')
        elif kind=='sonsuz_taslak':
            shift=int(t*35)%180
            for k in range(-1,5):
                yy=230+k*180-shift;col=[(0,190,230),(170,85,255),(45,220,140)][k%3]
                d.rectangle((65,yy,320,yy+165),outline=col,width=3)
                d.line((150 if k%2 else 230,yy+165,150 if k%2 else 230,yy+180),fill=col,width=7)
            d.ellipse((184,500,200,516),fill=(0,225,255));d.ellipse((225,476,241,492),fill=(255,65,170));d.line((192,508,233,484),fill='white',width=2)
            d.text((192,720),'UÇ UCA → YENİ ROTA',font=smallfont(24),anchor='mm',fill='white')
        else:
            for i,(label,yy) in enumerate([('GÖRSELİ HAZIRLA',280),('ÖNBELLEKTE TUT',410),('KAREDE TEKRAR KULLAN',540)]):
                d.rounded_rectangle((35,yy,350,yy+75),radius=15,fill=(12,31,46),outline=(45,205,230),width=2)
                d.text((192,yy+37),label,font=smallfont(25),anchor='mm',fill='white')
                if i<2:d.text((192,yy+100),'↓',font=smallfont(30),anchor='mm',fill=(50,220,235))
        writer.send(np.asarray(im).tobytes())
    writer.close();return out

def make_stills(kind):
    out=PACK/(kind+'.mp4')
    if out.exists():return out
    if kind=='olo_tasarim':
        names=['smug','shock','laugh_point','clap','finger_guns','smug'];images=[]
        for pose in names:
            im=Image.new('RGB',(384,832),(6,13,28));d=ImageDraw.Draw(im)
            d.text((192,160),'OLO • KARAKTER ÇALIŞMALARI',font=smallfont(20),anchor='mm',fill=(75,215,240))
            s=Image.open(r.ROOT/'assets/olo'/f'{pose}.png').convert('RGBA');s.thumbnail((290,370));im.paste(s,((384-s.width)//2,260),s)
            images.append(im)
    else:
        paths=['01_menu.png','02_endless.png','04_endless_climb.png','05_endless_result.png','06_star_skins.png','08_featured.png']
        images=[]
        for path in paths:
            src=Image.open(r.ROOT/'store_assets/screenshots_105/tr'/path).convert('RGB');src.thumbnail((384,682))
            im=Image.new('RGB',(384,832),(6,13,28));im.paste(src,((384-src.width)//2,115));d=ImageDraw.Draw(im)
            d.rectangle((0,0,384,110),fill=(6,13,28));d.text((192,135),'OYUNDAN GÖRÜNTÜ',font=smallfont(19),anchor='mm',fill=(75,215,240));images.append(im)
    wr=imageio_ffmpeg.write_frames(str(out),(384,832),fps=30,quality=8,macro_block_size=2);wr.send(None)
    for frame in range(1080):wr.send(np.asarray(images[min(5,frame//180)]).tobytes())
    wr.close();return out

def prepare():
    for kind in ['temel_mekanik','harita_taslagi','sonsuz_taslak','performans']:make_diagram(kind)
    make_stills('arayuz');make_stills('olo_tasarim')

def render(index):
    name,title,beats=DATA[index];r.OUT=PACK/name;r.OUT.mkdir(exist_ok=True)
    r.SOURCES=[NEW,PACK/'temel_mekanik.mp4',PACK/'harita_taslagi.mp4',PACK/'sonsuz_taslak.mp4',PACK/'arayuz.mp4',PACK/'olo_tasarim.mp4',PACK/'performans.mp4',r.ROOT/'store_assets/olo_game_tr.mp4']
    shots=[[(1,s,6) for s in range(0,36,6)],[(2,0,6),(0,3,6),(0,36,6),(0,172,6),(2,24,6),(0,23,6)],[(0,3,6),(0,142,6),(0,23,6),(0,74,6),(4,0,6),(0,179,6)],[(3,0,6),(3,6,6),(3,12,6),(0,298,6),(0,304,6),(4,18,6)],[(4,0,6),(0,224,6),(6,0,6),(0,273,6),(4,24,6),(5,0,6)],[(5,0,6),(5,6,6),(7,1,6),(7,12,6),(6,24,6),(0,5,6)]][index]
    # Leaderboard scenes selected outside notified intervals; hard mask remains.
    r.CUTS=shots;r.SOURCE_FILTER='drawbox=x=0:y=0:w=iw:h=110:color=0x060d1c:t=fill,'
    poses=['finger_guns','smug','shock','laugh_point','smug','finger_guns']
    r.BEATS=[(i*6,(i+1)*6,poses[i],text,heading) for i,(heading,text) in enumerate(beats)]
    r.MUSIC_ONLY=True;r.MUSIC=PACK.parent/'Olo_Reels_Heyecanli/HOLO_Neon_Rush_140BPM.wav'
    r.CAPTION=title+'\nHOLO’nun gelişim hikâyesi. Anlatan: Olo.\nİlk mekanik, harita taslağı ve çalışma şemaları canlandırmadır; diğer kesitler oyundan alınmıştır.'
    v=PACK/(name+'.mp4')
    if not v.exists():r.main();(r.OUT/'HOLO_Olo_Reels_TR.mp4').replace(v)
    subprocess.run([r.FF,'-y','-ss','2','-i',str(v),'-frames:v','1',str(PACK/(name+'_kapak.jpg'))],capture_output=True,check=True)
    test=subprocess.run([r.FF,'-v','error','-i',str(v),'-f','null','-'],capture_output=True,text=True);assert test.returncode==0,test.stderr
    print('VERIFIED STORY',name,flush=True)

def main():
    if len(sys.argv)>1:render(int(sys.argv[1]));return
    prepare()
    def job(i):
        p=subprocess.run([sys.executable,str(Path(__file__).resolve()),str(i)],capture_output=True,text=True)
        if p.returncode:raise RuntimeError(p.stdout+p.stderr)
        print(p.stdout.strip(),flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(job,range(6)))
    sources='''HOLO GELİŞİM HİKÂYESİ — KAYNAK NOTU
Seri, belgelenmiş geliştirme konularını öğretici sırayla anlatır; kesin tarihli bir sürüm kronolojisi değildir.
İlk prototipin özgün kaydı bulunamadığı için temel mekanik, koridor taslağı ve ilk sonsuz harita fikri CANLANDIRMA olarak etiketlenmiştir.
Dayanaklar: README.md (Python/Pygame, deterministik fizik, bölüm çözücüsü ve sunucu), docs/SON_DUZENLEMELER.md (23 Eylül düzenlemeleri), docs/PERFORMANCE_5_1_2.md (önbellek/ölçekleme), tools/endless_stitched_prototype.py (uç uca haritalar), Git Olo geçmişi (karakter çalışmaları, duruma bağlı tepkiler, önbellek).
Görüntüler: 16 Ekim 18.51.18 kaydı; store_assets/screenshots_105/tr; assets/olo; store_assets/olo_game_tr.mp4. Bunlar erken sürüm kayıtları olarak sunulmaz.
Telefon kayıtlarında üst 110 kaynak piksel tamamen opak kapatılmıştır. Seslendirme yoktur.
'''
    (PACK/'Kaynak_ve_paylasim_sirasi.txt').write_text(sources,encoding='utf8')
    with zipfile.ZipFile(PACK/'HOLO_Gelisim_6_Bolum.zip','w',compression=zipfile.ZIP_STORED) as z:
        for name,*_ in DATA:
            for f in [PACK/(name+'.mp4'),PACK/(name+'_kapak.jpg'),PACK/name/'Instagram_metin.txt']:z.write(f,name+'_aciklama.txt' if f.name=='Instagram_metin.txt' else f.name)
        z.write(PACK/'Kaynak_ve_paylasim_sirasi.txt','Kaynak_ve_paylasim_sirasi.txt')
    print('SIX DEVELOPMENT EPISODES READY',flush=True)

if __name__=='__main__':main()
