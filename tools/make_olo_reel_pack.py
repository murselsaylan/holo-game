"""Three standalone Reels, using different sections of the supplied recordings."""
import subprocess
import zipfile
from pathlib import Path
import make_olo_reel as reel

PACK = reel.ROOT.parent / 'HOLOmedya' / 'Olo_Reels_Seri'
VARIANTS = [
    ('01_bolum_degisti', 'Bölüm değişti. Sonuç?', [
        ('smug','Bu bölüm olmadı. Diğerine bakalım.','BÖLÜMÜ DEĞİŞTİRDİK.'),
        ('finger_guns','Bak, burada sakin sakin gidiyoruz.','BURASI DAHA SAKİN.'),
        ('shock','Kristal güzelmiş. Yakından bakmasaydık.','FAZLA YAKINDAN BAKTIK.'),
        ('laugh_point','Tamam. Turuncu olanı deneyelim.','BİR DE BUNU DENEYELİM.'),
        ('smug','Duvarlar bizi tanımaya başladı.','YİNE AYNI HİKÂYE.'),
        ('finger_guns','Sen hangi bölümü seçerdin?','SEN HANGİSİNİ SEÇERDİN?'),
    ],[(1,47,6),(1,33,6),(1,63,6),(1,101,6),(1,111,6),(1,121,6)]),
    ('02_dokunma_zamani', 'Hamleyi gördün mü?', [
        ('smug','Bir dokunuş erken. Bütün mesele bu.','BİR DOKUNUŞ ERKEN.'),
        ('finger_guns','Burada beklesek geçer miydik?','BİRAZ BEKLESEK MİYDİK?'),
        ('shock','Şimdi de biraz fazla bekledik.','BU SEFER GEÇ KALDIK.'),
        ('laugh_point','Şu dar yer var ya. Hep o.','ŞU DAR YER…'),
        ('smug','Ekrana bakarken kolay geliyor.','BURADAN KOLAY GÖRÜNÜYOR.'),
        ('finger_guns','Tam nerede dokunurdun?','SEN NEREDE DOKUNURDUN?'),
    ],[(0,3,5),(1,6,6),(1,48,6),(1,89,6),(1,109,6),(0,16,6)]),
    ('03_son_bir_bolum', 'Sadece bir bölüm daha.', [
        ('smug','Bir bölüm geçip çıkacaktık.','BİR BÖLÜM GEÇİP ÇIKACAKTIK.'),
        ('shock','Bu sayılmaz. Daha yeni başladık.','BU SAYILMAZ.'),
        ('finger_guns','Başka bölüm. Temiz bir başlangıç.','YENİ BÖLÜM. YENİ UMUT.'),
        ('laugh_point','Az önce nereye bakıyorduk?','BİR ANLIK DALGINLIK.'),
        ('smug','Son deneme lafını duymadım sayıyorum.','SON DENEME DEDİK Mİ?'),
        ('finger_guns','Sen olsan burada bırakır mıydın?','BURADA BIRAKIR MIYDIN?'),
    ],[(1,15,6),(0,8,6),(1,60,6),(1,91,6),(1,107,6),(1,47,6)]),
]

def main():
    PACK.mkdir(exist_ok=True)
    for folder,title,beats,cuts in VARIANTS:
        reel.OUT=PACK/folder;reel.OUT.mkdir(exist_ok=True)
        reel.BEATS=[(i*6,(i+1)*6,*beat) for i,beat in enumerate(beats)]
        reel.CUTS=cuts;reel.CAPTION=title+' 👀\nOlo izliyor. Hamle sende.'
        reel.main()
        video=reel.OUT/'HOLO_Olo_Reels_TR.mp4'
        dest=PACK/(folder+'.mp4');video.replace(dest)
        subprocess.run([reel.FF,'-y','-ss','7','-i',str(dest),'-frames:v','1',str(PACK/(folder+'_kapak.jpg'))],capture_output=True,check=True)
        check=subprocess.run([reel.FF,'-v','error','-i',str(dest),'-f','null','-'],capture_output=True,text=True)
        assert check.returncode==0,check.stderr
        print('VERIFIED',dest,flush=True)
    with zipfile.ZipFile(PACK/'Olo_Reels_Paketi.zip','w',compression=zipfile.ZIP_STORED) as z:
        for f in sorted(PACK.glob('*.mp4')):z.write(f,f.name)
        for f in sorted(PACK.glob('*_kapak.jpg')):z.write(f,f.name)
        for f in sorted(PACK.glob('*/Instagram_metin.txt')):z.write(f,f.parent.name+'_aciklama.txt')
    print('PACK READY',PACK,flush=True)

if __name__=='__main__':main()
