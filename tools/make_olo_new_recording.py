"""New recording only; hard-mask notification region before any export."""
import subprocess
import zipfile
import json
from pathlib import Path
import make_olo_reel as r

PACK=r.ROOT.parent/'HOLOmedya'/'Yeni_Kayit_Reels'
PACK.mkdir(exist_ok=True)
SOURCE=PACK.parent/'WhatsApp Video 2026-10-16 at 18.51.18.mp4'
DATA=[
('09_birinci_bolumden_sonra','İlk bölümden sonra işler değişiyor.',[
('finger_guns','Bak. Gayet sakin başladık.','HER ŞEY SAKİN BAŞLADI.'),
('smug','Biraz ilerleyince renk değişti.','SONRA RENK DEĞİŞTİ.'),
('shock','Şu kristale mesafe koysak mı?','BİRAZ MESAFE İYİDİR.'),
('laugh_point','Tamam. Mesafeyi ayarlayamadık.','BİRAZ DAHA MESAFE…'),
('smug','Mor bölüme dönelim. Bir fikrim var.','BİR FİKRİM VAR.'),
('finger_guns','Senin fikrin daha iyi olabilir.','SEN NASIL GEÇERDİN?')],[3,20,59,76,38,141]),
('10_yuzde_89','O kadar geldik. Bir hamle kaldı.',[
('smug','Sakin gidiyoruz. Acelemiz yok.','SAKİN SAKİN…'),
('finger_guns','Kristali geride bıraktık.','BURAYA KADAR TAMAM.'),
('smug','Şimdi şu aradan geçeceğiz.','SADECE ŞU ARADAN.'),
('shock','O kadar geldik. Şuna bak.','O KADAR GELMİŞTİK.'),
('laugh_point','Başka bölüme geçmek çözüm mü?','BÖLÜMÜ DEĞİŞTİRSEK?'),
('finger_guns','Sen son hamleyi gördün sanki.','SON HAMLE SENDE.')],[85,94,100,106,135,174]),
('11_mor_yesil_turuncu','Üç renk. Bir sürü yanlış hamle.',[
('smug','Mor olanla aramız iyi gibi.','MORLA ARAMIZ İYİ.'),
('finger_guns','Yeşilde de aynı sakinlik.','YEŞİLDE DE SAKİNİZ.'),
('shock','Sakinlik kısa sürdü.','ÇOK KISA SÜRDÜ.'),
('smug','Turuncu belki bize iyi gelir.','BİR DE TURUNCU.'),
('laugh_point','Biraz fazla yakından tanıştık.','TANIŞMA BİRAZ SERT OLDU.'),
('finger_guns','Rengi sen seç. Hamleyi de.','SEN HANGİSİNİ SEÇERDİN?')],[35,71,77,172,184,205]),
('12_duvarla_randevu','Olo yine bir şey demiyor.',[
('smug','Şu boşluk tam bize göre.','BOŞLUK TAM BİZE GÖRE.'),
('shock','Bize göre değilmiş galiba.','GALİBA DEĞİLMİŞ.'),
('finger_guns','Bu sefer biraz bekleyeceğiz.','BİRAZ BEKLE…'),
('laugh_point','Duvar beklemiyormuş.','DUVARIN ACELESİ VAR.'),
('smug','Bak. Başka bir yol daha var.','BİR YOL DAHA VAR.'),
('finger_guns','Senin parmağın kıpırdadı sanki.','TAM NEREDE DOKUNURDUN?')],[58,63,120,125,143,211]),
('13_son_bir_hamle','Son bir hamle. Son bir deneme.',[
('finger_guns','Bu sefer geçeceğiz gibi.','BU SEFER OLACAK.'),
('shock','Bir tık fazla güvendik.','BİR TIK FAZLA GÜVEN.'),
('smug','Yeni bölüm. Temiz sayfa.','TEMİZ BİR SAYFA.'),
('laugh_point','Sayfaya duvar çizmişler.','SAYFADA DA DUVAR VAR.'),
('smug','Son bir hamle. Bir deneme daha.','SON BİR HAMLE.'),
('finger_guns','Sen burada bırakmazdın bence.','BİR DE SEN DENE.')],[44,59,118,125,208,300])]

def main():
    r.SOURCES=[SOURCE];r.MUSIC_ONLY=True
    r.MUSIC=PACK.parent/'Olo_Reels_Heyecanli/HOLO_Neon_Rush_140BPM.wav'
    # Solid pixels, not blur or a translucent layer: no notification text survives.
    r.SOURCE_FILTER='drawbox=x=0:y=0:w=iw:h=110:color=0x060d1c:t=fill,'
    for name,title,beats,starts in DATA:
        if (PACK/(name+'.mp4')).exists() and (PACK/(name+'_kapak.jpg')).exists():
            print('ALREADY VERIFIED',name,flush=True)
            continue
        r.OUT=PACK/name;r.OUT.mkdir(exist_ok=True)
        r.BEATS=[(i*6,(i+1)*6,*b) for i,b in enumerate(beats)]
        r.CUTS=[(0,s,6) for s in starts];r.CAPTION=title+'\nOlo izliyor. Hamle sende.'
        # Avoid the visibly notified area, with a safety margin.
        assert all(s+6<=190 or 204<=s and s+6<=218 or s>=296 for s in starts)
        r.main();video=PACK/(name+'.mp4');(r.OUT/'HOLO_Olo_Reels_TR.mp4').replace(video)
        subprocess.run([r.FF,'-y','-ss','2','-i',str(video),'-frames:v','1',str(PACK/(name+'_kapak.jpg'))],capture_output=True,check=True)
        test=subprocess.run([r.FF,'-v','error','-i',str(video),'-f','null','-'],capture_output=True,text=True);assert test.returncode==0,test.stderr
        print('VERIFIED',name,flush=True)
    (PACK/'kurgu_kaynaklari.json').write_text(json.dumps({'source':SOURCE.name,'notification_mask':'top 110 source pixels replaced with solid color','cuts':{row[0]:row[3] for row in DATA}},ensure_ascii=False,indent=2),encoding='utf8')
    with zipfile.ZipFile(PACK/'Yeni_Kayittan_5_Reels.zip','w',compression=zipfile.ZIP_STORED) as z:
        for name,*_ in DATA:
            for f in [PACK/(name+'.mp4'),PACK/(name+'_kapak.jpg'),PACK/name/'Instagram_metin.txt']:
                z.write(f,name+'_aciklama.txt' if f.name=='Instagram_metin.txt' else f.name)
    print('FIVE NEW RECORDING REELS READY',flush=True)

if __name__=='__main__':main()
