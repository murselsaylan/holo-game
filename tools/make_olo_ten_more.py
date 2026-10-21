"""Ten distinct edits from the latest recording, with notifications hard-masked."""
import concurrent.futures
import json
import subprocess
import sys
import zipfile
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
import make_olo_reel as r

PACK=r.ROOT.parent/'HOLOmedya'/'Olo_10_Yeni_Reels'
PACK.mkdir(exist_ok=True)
DATA=[
('14_sakin_ol','Sakin ol dedik.',[3,22,42,64,107,301],[
('SAKİN OL DEDİK.','Önce sakin olalım. Daha başındayız.'),
('BİRAZ FAZLA SAKİN.','Beklemek de bir hamle. Bazen.'),
('ŞİMDİ OLUR GİBİ.','Şu boşluk gözümüzün önünde.'),
('O BOŞLUK DEĞİLMİŞ.','Tamam. Başka bir boşluğa bakalım.'),
('BURAYA KADAR GELDİK.','Şimdi heyecan yapmayalım.'),
('SEN SAKİN KALIR MIYDIN?','Ben izliyorum. Hamle sende.')]),
('15_kristal_meselesi','Kristalle aramızdaki mesele.',[71,78,86,103,124,60],[
('GÜZEL GÖRÜNÜYOR.','Şu kristallerin bir havası var.'),
('YAKINDAN BAKMAYALIM.','Biraz uzaktan sevelim onları.'),
('BURADA BEKLESEK?','Acele etmeden de gidebiliriz.'),
('BİR HAMLE KALDI.','Şu aralığı gördün mü sen de?'),
('GÖRMEK YETMİYORMUŞ.','Parmağın da aynı fikirde olmalı.'),
('SEN ARADAN GEÇER MİYDİN?','Bence aklında başka bir yol var.')]),
('16_olo_not_aliyor','Olo not alıyor.',[39,144,58,76,183,211],[
('OLO NOT ALIYOR.','Bir: özgüven yerinde.'),
('İKİ: PLAN VAR.','Şimdi şu aradan dönüyoruz.'),
('ÜÇ: YENİ BİR PLAN.','Bu bölüme de bir bakalım.'),
('DÖRT: KRİSTAL VAR.','Notlara mesafe yazıyorum.'),
('BEŞ: DUVAR HÂLÂ ORADA.','Bir türlü yer değiştirmiyor.'),
('SONRAKİ NOT NE OLSUN?','Sen oynasan ne yazardım acaba?')]),
('17_buradan_gecilir','Buradan geçilir gibi.',[136,145,36,89,109,206],[
('BURADAN GEÇİLİR GİBİ.','Bakınca yol gayet açık.'),
('BİR KÜÇÜK DÖNÜŞ.','Sadece zamanını tutturacağız.'),
('BAŞKA BİR YOL DENEYELİM.','Mor olan da fena görünmüyor.'),
('GÖZE KOLAY GELİYOR.','El gözle aynı anda çalışsa keşke.'),
('TAM O AN…','Bir an önce dokunsak mıydık?'),
('SEN O ANI YAKALAR MIYDIN?','Ben bir şey söylemiyorum.')]),
('18_baslangic_ve_sonrasi','Başlangıçta kolay görünüyordu.',[2,18,46,72,174,300],[
('BAŞLANGIÇTA KOLAYDI.','İki küre. Bir dokunuş. Tamam.'),
('SONRA MOR GELDİ.','Biraz daha dikkat istiyormuş.'),
('SONRA BU HAMLE.','Şu dar yeri konuşmamız lazım.'),
('SONRA KRİSTALLER.','Oyunun dekoru da bize karışıyor.'),
('ŞİMDİ DE LAZERLER.','Gözümüz bir yerde daha olsun.'),
('BİR DE SONSUZ MOD VAR.','Nereye kadar gidersin sence?')]),
('19_parmagin_kipirdadi','Parmağın kıpırdadı mı?',[87,98,105,62,141,208],[
('PARMAĞIN KIPIRDADI MI?','Ekrana dokunacak gibi oldun.'),
('BEN DE ORADA BASARDIM.','Ama biraz daha mı beklesek?'),
('ŞİMDİ Mİ?','O an çok kısa sürüyor.'),
('BİR DAHA BAKALIM.','Başka bölümde de aynı mesele.'),
('YOLU GÖRDÜN GİBİ.','Kafanda hamleyi yaptın bile.'),
('BİR DE OYUNDA DENE.','Olo sonucu merak ediyor.')]),
('20_bolum_turu','Olo ile küçük bir bölüm turu.',[6,23,40,74,139,177],[
('KÜÇÜK BİR TUR.','Ben Olo. Yolu göstereyim.'),
('BURASI MOR TARAF.','Güzel. Ama boşluklara dikkat.'),
('ŞU HAMLEYE BAK.','Gözün iki kürede de olsun.'),
('ŞİMDİ YEŞİL TARAF.','Kristalle arana biraz mesafe koy.'),
('TURUNCUDA İŞLER DEĞİŞİR.','Lazerler de tura katıldı.'),
('SEN NEREDE KALIRDIN?','Ben burada rehberliği bırakıyorum.')]),
('21_bir_hamle_farki','Bazen tek hamle fark ediyor.',[45,59,102,108,122,212],[
('BİR HAMLE FARKI.','Bazen bütün mesele o.'),
('BİR TIK ERKEN…','Şimdi biraz bekleyelim dedik.'),
('BU SEFER ZAMANI MI?','Yol açık gibi görünüyor.'),
('O KADAR GELMİŞTİK.','Sonunu izlemek biraz üzdü.'),
('YENİ BİR ŞANS.','Başka bölüm. Aynı parmak.'),
('SEN NEYİ DEĞİŞTİRİRDİN?','Hamleyi kafanda yaptın mı?')]),
('22_yol_acik','Yol açık, peki zamanlama?',[137,33,70,84,180,302],[
('YOL AÇIK.','En azından buradan öyle duruyor.'),
('YA ZAMANLAMA?','İşte o kısmı konuşuyoruz.'),
('BİRAZ YAVAŞ…','Küreyi takip et. Kristali de.'),
('BİRAZ SABIR…','Şimdi geçmek için bekliyoruz.'),
('BİRAZ CESARET…','Ama sonsuza kadar bekleyemeyiz.'),
('SENİN RİTMİN NASIL?','Bir de senin hamleni görelim.')]),
('23_oynamadan_olmaz','İzlerken hamleyi yapmak kolay.',[20,48,77,140,184,299],[
('İZLERKEN KOLAY.','Ben de buradan çok iyi oynuyorum.'),
('ŞİMDİ BAS DERDİM.','Sonra fikrimi değiştirirdim.'),
('BURADA SUSARDIM.','Kristal cevap verdi zaten.'),
('SONRA BİR FİKİR DAHA.','Şu aradan dönersek olur gibi.'),
('SONUCU BİLİYORSUN.','Fikir güzel. Zamanlama biraz…'),
('BİR DE OYNARKEN BAK.','Belki senin elin daha sakindir.')]),
]

def render(index):
    name,title,starts,lines=DATA[index]
    r.OUT=PACK/name;r.OUT.mkdir(exist_ok=True)
    poses=['smug','finger_guns','shock','laugh_point','smug','finger_guns']
    r.BEATS=[(i*6,(i+1)*6,poses[i],text,heading) for i,(heading,text) in enumerate(lines)]
    r.CUTS=[(0,s,6) for s in starts]
    r.SOURCES=[PACK.parent/'WhatsApp Video 2026-10-16 at 18.51.18.mp4']
    assert all(s+6<=190 or 204<=s and s+6<=218 or 296<=s<=304 for s in starts)
    r.SOURCE_FILTER='drawbox=x=0:y=0:w=iw:h=110:color=0x060d1c:t=fill,'
    r.MUSIC_ONLY=True;r.MUSIC=PACK.parent/'Olo_Reels_Heyecanli/HOLO_Neon_Rush_140BPM.wav'
    r.CAPTION=title+' 👀\nSenin hamlen ne olurdu?'
    for i in range(6):r.panel(i)
    video=PACK/(name+'.mp4')
    if not video.exists():
        r.main();(r.OUT/'HOLO_Olo_Reels_TR.mp4').replace(video)
    subprocess.run([r.FF,'-y','-ss','2','-i',str(video),'-frames:v','1',str(PACK/(name+'_kapak.jpg'))],capture_output=True,check=True)
    test=subprocess.run([r.FF,'-v','error','-i',str(video),'-f','null','-'],capture_output=True,text=True)
    assert test.returncode==0,test.stderr
    # Verify the opaque privacy band in every exported source-cut frame.
    for c in sorted(r.OUT.glob('cut_*.mp4')):
        raw=subprocess.run([r.FF,'-v','error','-i',str(c),'-vf','crop=500:140:100:0,scale=1:1','-f','rawvideo','-pix_fmt','rgb24','-'],capture_output=True,check=True).stdout
        samples=np.frombuffer(raw,dtype=np.uint8).reshape(-1,3).astype(int)
        assert np.ptp(samples,axis=0).max()<=3,str(c)
    print('VERIFIED VIDEO + PRIVACY',name,flush=True)

def main():
    if len(sys.argv)>1:
        render(int(sys.argv[1]));return
    def worker(i):
        p=subprocess.run([sys.executable,str(Path(__file__).resolve()),str(i)],capture_output=True,text=True)
        if p.returncode:raise RuntimeError(p.stdout+p.stderr)
        print(p.stdout.strip(),flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(worker,range(len(DATA))))
    with zipfile.ZipFile(PACK/'Olo_10_Yeni_Reels.zip','w',compression=zipfile.ZIP_STORED) as z:
        for name,*_ in DATA:
            for f in [PACK/(name+'.mp4'),PACK/(name+'_kapak.jpg'),PACK/name/'Instagram_metin.txt']:
                z.write(f,name+'_aciklama.txt' if f.name=='Instagram_metin.txt' else f.name)
    (PACK/'kurgu_kaynaklari.json').write_text(json.dumps({row[0]:row[2] for row in DATA},indent=2),encoding='utf8')
    print('ALL TEN READY',flush=True)

if __name__=='__main__':main()
