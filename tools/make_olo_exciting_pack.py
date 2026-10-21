"""Five new music-only Reels with a custom energetic electronic score."""
import subprocess
import wave
import zipfile
import numpy as np
from PIL import Image,ImageDraw
import make_olo_reel as r

PACK=r.ROOT.parent/'HOLOmedya'/'Olo_Reels_Heyecanli'
PACK.mkdir(exist_ok=True)

def music():
    sr=48000; length=36; audio=np.zeros((sr*length,2),dtype=np.float64)
    rng=np.random.default_rng(20261016);beat=60/140
    def add(start,sound,pan=0):
        at=int(start*sr);n=min(len(sound),len(audio)-at)
        if n>0:
            audio[at:at+n,0]+=sound[:n]*(.8-.25*pan)
            audio[at:at+n,1]+=sound[:n]*(.8+.25*pan)
    def kick():
        t=np.arange(int(sr*.32))/sr
        return .7*np.sin(2*np.pi*(48*t+95*.035*(1-np.exp(-t/.035))))*np.exp(-t*15)
    def snare():
        t=np.arange(int(sr*.18))/sr;noise=rng.normal(0,1,len(t));noise=np.r_[0,np.diff(noise)]
        return (.16*noise+.16*np.sin(2*np.pi*185*t))*np.exp(-t*24)
    def hat(open=False):
        t=np.arange(int(sr*(.16 if open else .055)))/sr;noise=rng.normal(0,1,len(t));noise=np.r_[0,np.diff(noise)]
        return .035*noise*np.exp(-t*(27 if open else 85))
    roots=[110,87.307,130.813,97.999]
    for b in range(int(length/beat)+1):
        at=b*beat;add(at,kick())
        if b%2:add(at,snare())
        add(at,hat(),-.5);add(at+beat/2,hat(b%4==3),.5)
        root=roots[(b//8)%4]
        for sub in range(2):
            t=np.arange(int(sr*beat*.43))/sr;freq=root/2
            env=(1-np.exp(-t*110))*np.exp(-t*14)
            bass=(np.sin(2*np.pi*freq*t)+.25*np.sin(2*np.pi*freq*2*t))*env*.24
            add(at+sub*beat/2,bass)
        for sub in range(4):
            t=np.arange(int(sr*.18))/sr;ratio=[1,1.5,2,2.3784][(b+sub)%4];freq=root*ratio*2
            env=(1-np.exp(-t*150))*np.exp(-t*23)
            synth=sum(np.sin(2*np.pi*freq*k*t)/k for k in range(1,5))*.065*env
            add(at+sub*beat/4,synth,(-1 if sub%2 else 1)*.7)
            add(at+sub*beat/4+.16,synth*.25,(-1 if sub%2 else 1)*-.7)
    # Filtered noise rises into new sections; transitions every six seconds.
    for section in [6,12,18,24,30]:
        t=np.arange(sr)//1/sr;noise=rng.normal(0,1,len(t));noise=np.convolve(noise,np.ones(9)/9,mode='same')
        add(section-1,noise*.10*t*t)
        add(section,noise[::-1]*.12*np.exp(-t*8))
    audio=np.tanh(audio*1.15);audio*=.88/max(.001,np.max(np.abs(audio)))
    target=PACK/'HOLO_Neon_Rush_140BPM.wav'
    with wave.open(str(target),'wb') as f:
        f.setnchannels(2);f.setsampwidth(2);f.setframerate(sr);f.writeframes((audio*32767).astype('<i2').tobytes())
    return target

DATA=[
('04_duvar_kazandi','Duvar yine kazandı.',[
('smug','Ben bir şey demedim. Duvar dedi.','DUVAR YİNE KAZANDI.'),
('finger_guns','Burası geniş. Buradan geçeriz.','BURADAN GEÇERİZ.'),
('shock','Geniş olması yetmedi galiba.','GALİBA YETMEDİ.'),
('laugh_point','Bölümü değiştirdik. Bakalım.','YENİ BÖLÜM. AYNI BİZ.'),
('smug','Şu hamleyi bir daha düşünelim.','BİR SANİYE GERİ ALSAK…'),
('finger_guns','Sen o boşluğu gördün, değil mi?','O BOŞLUĞU GÖRDÜN MÜ?')],[(1,47,6),(1,119,6),(0,3,5),(1,85,6),(1,110,6),(1,16,6)]),
('05_sadece_bir_dokunus','Sadece bir dokunuş.',[
('finger_guns','Tek tuş var. Bahane bulmak zor.','SADECE BİR DOKUNUŞ.'),
('smug','Şimdi değil. Birazdan.','BİRAZ DAHA BEKLE…'),
('shock','Birazdan derken…','TAMAM. O KADAR DEĞİL.'),
('laugh_point','Ben olsam burada susardım.','OLO BİLE SUSTU.'),
('smug','Parmağın kıpırdadı sanki.','SEN DE DOKUNACAKTIN.'),
('finger_guns','Nerede basacağını biliyorsun gibi.','HAMLEYİ GÖRDÜN MÜ?')],[(1,34,6),(1,65,6),(0,8,6),(1,90,6),(1,103,6),(1,122,6)]),
('06_renk_degisti','Renk değişti, dert değişmedi.',[
('smug','Yeşil olan daha sakin duruyor.','YEŞİL OLAN KOLAYDIR.'),
('shock','Sakin duruyormuş sadece.','SADECE ÖYLE DURUYORMUŞ.'),
('finger_guns','Turuncuya dönelim. Tanıdık yer.','TANIDIK BİR YERE DÖNELİM.'),
('laugh_point','Burası da bizi hatırladı.','BURASI BİZİ HATIRLADI.'),
('smug','Bir de şu kristalli yere bakalım.','BİR İHTİMAL DAHA VAR.'),
('finger_guns','Sen hangisine şans verirdin?','YEŞİL Mİ, TURUNCU MU?')],[(1,37,6),(1,48,6),(1,100,6),(1,111,6),(1,67,6),(1,88,6)]),
('07_bir_sonraki_deneme','Bir sonraki denemede kesin.',[
('finger_guns','Bu sefer yolu öğrendik.','BU SEFER YOLU BİLİYORUZ.'),
('shock','Yolu biliyoruz. Zamanı değil.','BİR ŞEYİ EKSİK ÖĞRENMİŞİZ.'),
('smug','Şimdi kafamızda plan var.','PLAN HAZIR.'),
('laugh_point','Planın o kısmı yoktu galiba.','PLAN BURAYA KADARDI.'),
('smug','Sonraki denemede kesin dedik mi?','BU SEFER KESİN DEDİK Mİ?'),
('finger_guns','Senin planın biraz farklı sanki.','SEN NASIL GEÇERDİN?')],[(1,10,6),(0,3,5),(1,62,6),(1,47,6),(1,108,6),(1,121,6)]),
('08_olo_sayiyor','Olo saymayı bıraktı.',[
('smug','Kaçıncı deneme? Ben saymıyorum.','OLO SAYMAYI BIRAKTI.'),
('shock','Bu duvarla aramızda bir şey var.','BU DUVARLA BİR DERDİMİZ VAR.'),
('finger_guns','Şimdi başka bir şey deneyelim.','FARKLI BİR HAMLE.'),
('laugh_point','Sonuç biraz tanıdık geldi.','TANIDIK BİR SONUÇ.'),
('smug','Bakışından anladım. Bir fikrin var.','BİR FİKRİN VAR GİBİ.'),
('finger_guns','O fikri oyunda denemek lazım.','BİR DE SEN DENE.')],[(1,92,6),(0,16,6),(1,71,6),(1,111,6),(1,41,6),(1,123,6)])]

def main():
    r.MUSIC_ONLY=True;r.MUSIC=music()
    for name,title,beats,cuts in DATA:
        r.OUT=PACK/name;r.OUT.mkdir(exist_ok=True)
        r.BEATS=[(i*6,(i+1)*6,*b) for i,b in enumerate(beats)];r.CUTS=cuts;r.CAPTION=title+' 👀\nHamle sende. Olo izliyor.'
        r.main();v=PACK/(name+'.mp4');(r.OUT/'HOLO_Olo_Reels_TR.mp4').replace(v)
        subprocess.run([r.FF,'-y','-ss','2','-i',str(v),'-frames:v','1',str(PACK/(name+'_kapak.jpg'))],capture_output=True,check=True)
        result=subprocess.run([r.FF,'-v','error','-i',str(v),'-f','null','-'],capture_output=True,text=True);assert result.returncode==0,result.stderr
        print('VERIFIED',name,flush=True)
    with zipfile.ZipFile(PACK/'Olo_5_Yeni_Reels.zip','w',compression=zipfile.ZIP_STORED) as z:
        for name,*_ in DATA:
            for f in [PACK/(name+'.mp4'),PACK/(name+'_kapak.jpg'),PACK/name/'Instagram_metin.txt']:
                z.write(f,name+'_aciklama.txt' if f.name=='Instagram_metin.txt' else f.name)
    print('ALL FIVE READY',flush=True)

if __name__=='__main__':main()
