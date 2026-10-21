"""Build 92 distinct edited gameplay videos with source provenance and SFX."""
from pathlib import Path
import json,subprocess,math,wave,hashlib
from concurrent.futures import ThreadPoolExecutor,as_completed
import numpy as np
from PIL import Image,ImageDraw
import edit_latest_social as lib

ROOT=lib.ROOT;BASE=ROOT.parent/'HOLOmedya/Uc_Aylik_Sezon';OUT=BASE/'videolar';OUT.mkdir(parents=True,exist_ok=True)
FF=lib.FF;SR=48000
MUSIC=lib.audio(ROOT.parent/'HOLOmedya/Olo_Reels_Heyecanli/HOLO_Neon_Rush_140BPM.wav')
THEMES=[
 ('karar','ŞİMDİ DOKUNUR MUYDUN?','Ben de tam burada düşündüm.','Burada senin hamlen ne olurdu?'),
 ('akis','BU GEÇİŞE PUANIN KAÇ?','Ritmi bulunca oluyor.','Bu akışa 10 üzerinden kaç verirsin?'),
 ('iki_deneme','AYNI BÖLÜM. İKİ DENEME.','Bir hamle, bambaşka sonuç.','İzlerken gördüğün hamleyi oynarken yapabilir misin?'),
 ('tur','FARKLI BÖLÜM, AYNI İKİ KÜRE.','Benim favorim bir sonraki.','Bu üç bölümden hangisini denemek isterdin?'),
 ('olo','OLO BU DENEMEYE GÜVENİYORDU.','Güvenimi biraz erken verdim.','Olo yine son deneme sözüne inandı.'),
 ('tanitim','İKİ KÜRE. TEK DOKUNUŞ.','İzlemek kolay. Hamle sende.','HOLO: iki küreyi tek dokunuşla yönet. Google Play’de HOLO — Yörünge Oyunu.'),
 ('son_donus','BİR DÖNÜŞ DAHA VARDI.','Bir daha deneyelim mi?','Bu denemede nerede dokunurdun?'),
 ('temiz','DURMADAN İZLENEN GEÇİŞ.','Bu kez duvar kazanamadı.','Ses açıkken bir de böyle izle. 🩵🩷')]
HOOKS={
 'karar':['ŞİMDİ DOKUNUR MUYDUN?','BİR SANİYE BEKLER MİYDİN?','SENCE HAMLE NEREDE?','BURADA PARMAĞIN NE YAPARDI?'],
 'akis':['BU GEÇİŞE PUANIN KAÇ?','RİTMİ BULUNCA BÖYLE OLUYOR.','İKİ KÜRE, TEK AKIŞ.','BU DÖNÜŞÜ BİR DAHA İZLE.'],
 'iki_deneme':['AYNI BÖLÜM. İKİ DENEME.','İZLERKEN KOLAY GELİYORDU.','BİR HAMLEYLE DEĞİŞEN SONUÇ.','ÖNCE İZLE, SONRA KARAR VER.'],
 'tur':['FARKLI BÖLÜM, AYNI İKİ KÜRE.','SEN HANGİSİNİ SEÇERDİN?','ÜÇ BÖLÜM. ÜÇ AYRI RİTİM.','BU YOLLARDAN HANGİSİ?'],
 'olo':['OLO BU DENEMEYE GÜVENİYORDU.','SON DENEME DEDİM. OLO İNANDI.','OLO YİNE BİZİ İZLİYOR.','DUVARLA YENİDEN TANIŞTIK.'],
 'tanitim':['İKİ KÜRE. TEK DOKUNUŞ.','İLK OYUNUMUZ: HOLO.','KOLAY GÖRÜNEN BİR OYUN.','GOOGLE PLAY’DE BULUŞALIM.'],
 'son_donus':['BİR DÖNÜŞ DAHA VARDI.','SONRA BİR HAMLE GELDİ…','BU KORİDORU GEÇER MİYDİN?','YOLU GÖRDÜM. HAMLEYİ KAÇIRDIM.'],
 'temiz':['DURMADAN İZLENEN GEÇİŞ.','BU KEZ DUVAR KAZANAMADI.','SESİ AÇ, AKIŞI İZLE.','TAM ZAMANINDA BİR DOKUNUŞ.']}

def sources():
    vals=[]
    for folder in [BASE/'kaynak',ROOT.parent/'HOLOmedya/Son_Surum_108_Cekimler']:
        for p in sorted(folder.glob('level_*.json')):
            m=json.loads(p.read_text(encoding='utf8'));m['path']=str(p.with_suffix('.mp4'));vals.append(m)
    return vals

def run(cmd):
    r=subprocess.run(cmd,capture_output=True)
    if r.returncode:raise RuntimeError(r.stderr.decode(errors='replace')[-2200:])

def overlay(path,title,line,ep,late=False):
    im=Image.new('RGBA',(720,1280));d=ImageDraw.Draw(im)
    if not late:
        for y in range(175):d.line((0,y,720,y),fill=(5,10,24,int(248*max(0,1-y/175)**.5)))
        d.text((36,30),f'HOLO  /  OLO İLE OYUNDA  {ep:02d}',font=lib.font(23),fill=(80,225,240))
        size=46
        while d.textbbox((0,0),title,font=lib.font(size))[2]>648:size-=1
        d.text((36,74),title,font=lib.font(size),fill='white')
    else:
        sprite=Image.open(ROOT/'assets/olo'/('finger_guns.png' if ep%2 else 'idle.png')).convert('RGBA') if (ROOT/'assets/olo/idle.png').exists() else Image.open(ROOT/'assets/olo/finger_guns.png').convert('RGBA')
        sprite.thumbnail((120,150));im.alpha_composite(sprite,(30,865))
        d.rounded_rectangle((164,887,676,1002),radius=18,fill=(7,20,34,245),outline=(35,210,235),width=2)
        d.text((183,897),'OLO',font=lib.font(22),fill=(65,230,240))
        row='';lines=[]
        for word in line.split():
            test=(row+' '+word).strip()
            if d.textbbox((0,0),test,font=lib.font(28))[2]>466:lines.append(row);row=word
            else:row=test
        lines.append(row)
        for k,row in enumerate(lines):d.text((183,925+31*k),row,font=lib.font(28),fill='white')
        d.rounded_rectangle((170,1016,676,1055),radius=12,fill=(7,20,34,245))
        d.text((423,1035),'GOOGLE PLAY’DE: HOLO',font=lib.font(23),anchor='mm',fill=(215,240,250))
    im.save(path)

def make_plan(vals):
    clean=[m for m in vals if m['kind']=='clean'];fail=[m for m in vals if m['kind']=='fail'];pairs={m['level']:m for m in clean}
    plan=[];seen=set()
    for i in range(92):
        theme,title,line,caption=THEMES[i%8];cycle=i//8
        title=HOOKS[theme][cycle%4]
        if theme in ('karar','olo','son_donus'):
            m=fail[(cycle*3+i%8)%len(fail)];length=min(14+(cycle%2)*2,m['duration']-.1);shots=[(m,max(0,m['duration']-length-.5),length)]
        elif theme=='iki_deneme':
            m=fail[(cycle*5)%len(fail)];c=pairs[m['level']];shots=[(c,max(0,c['duration']-9),7),(m,max(0,m['duration']-9),8)]
        elif theme=='tur':
            shots=[]
            for j in range(3):
                m=clean[(cycle*3+j)%len(clean)];shots.append((m,min(max(0,m['duration']-5),2+cycle%4),4))
        elif theme=='tanitim':
            c=clean[(cycle*7)%len(clean)];m=fail[(cycle*7+3)%len(fail)];shots=[(c,max(0,c['duration']-10),7),(m,max(0,m['duration']-10),8)]
        else:
            m=clean[(cycle*5+i%8)%len(clean)];length=min(14+(cycle%2)*2,m['duration']-.1);start=max(0,m['duration']-length-1-(cycle%3)*1.5);shots=[(m,start,length)]
        signature=tuple((s[0]['path'],round(s[1],2),round(s[2],2)) for s in shots)
        adjustment=0
        while signature in seen and adjustment<12:
            m,start,length=shots[0];shots[0]=(m,max(0,start-.4),length-.2)
            signature=tuple((s[0]['path'],round(s[1],2),round(s[2],2)) for s in shots)
            adjustment+=1
        if signature in seen:raise RuntimeError('Duplicate source edit')
        seen.add(signature)
        levels='/'.join(str(s[0]['level']) for s in shots)
        plan.append({'index':i+1,'theme':theme,'title':title,'olo':line,'caption':caption+f'\nBölüm: {levels}.\nKontrollü oyun motoru kaydı; gerçek fizik ve sonuçlar.\n#HOLO #MobilOyun #IndieGame #RefleksOyunu','shots':[{'source':m['path'],'start':start,'duration':length,'level':m['level'],'kind':m['kind']} for m,start,length in shots],'file':str(OUT/f'{i+1:03d}_{theme}.mp4'),'duration':sum(s[2] for s in shots)})
    return plan

def render(p):
    final=Path(p['file']);side=final.with_suffix('.json')
    if final.exists() and side.exists():return p['index']
    ep=p['index'];head=OUT/f'{ep:03d}_header.png';olo=OUT/f'{ep:03d}_olo.png';wav=OUT/f'{ep:03d}_audio.wav'
    overlay(head,p['title'],p['olo'],ep);overlay(olo,p['title'],p['olo'],ep,True)
    total=p['duration'];n=int(total*SR);offset=(ep*3*SR)%len(MUSIC);mus=np.concatenate([MUSIC[offset:],MUSIC])
    mix=np.tile(mus,(math.ceil(n/len(mus)),1))[:n]*.5;clock=0
    for s in p['shots']:
        m=json.loads(Path(s['source']).with_suffix('.json').read_text(encoding='utf8'))
        for e in m['sound_events']:
            if s['start']<=e['t']<s['start']+s['duration']:
                snd=ROOT/'assets/audio'/(e['sound']+'.wav')
                if not snd.exists():continue
                a=lib.audio(snd);at=int((clock+e['t']-s['start'])*SR);count=min(len(a),n-at)
                if count>0:mix[at:at+count]+=a[:count]*.6
        clock+=s['duration']
    mix=np.tanh(mix);fade=min(int(SR*.3),n);mix[-fade:]*=np.linspace(1,0,fade)[:,None]
    with wave.open(str(wav),'wb') as w:w.setnchannels(2);w.setsampwidth(2);w.setframerate(SR);w.writeframes((mix*30000).astype('<i2').tobytes())
    cmd=[FF,'-v','error','-y','-filter_complex_threads','1'];filters=[]
    for j,s in enumerate(p['shots']):
        cmd+=['-ss',str(s['start']),'-t',str(s['duration']),'-i',s['source']]
        filters.append(f'[{j}:v]scale=720:1296:flags=bicubic,crop=720:1280:0:8,fps=30,setsar=1,setpts=PTS-STARTPTS[v{j}]')
    k=len(p['shots']);cmd+=['-loop','1','-i',str(head),'-loop','1','-i',str(olo),'-i',str(wav)]
    filters.append(''.join(f'[v{j}]' for j in range(k))+f'concat=n={k}:v=1:a=0[base]')
    filters.append(f"[base][{k}:v]overlay=0:0[h];[h][{k+1}:v]overlay=0:0:enable='gte(t,{total-3.2})',scale=1080:1920:flags=bicubic[out]")
    cmd+=['-filter_complex',';'.join(filters),'-map','[out]','-map',f'{k+2}:a','-t',str(total),'-c:v','libx264','-preset','veryfast','-crf','21','-threads','2','-pix_fmt','yuv420p','-c:a','aac','-b:a','160k','-movflags','+faststart',str(final)]
    run(cmd);run([FF,'-v','error','-i',str(final),'-f','null','-'])
    sample=OUT/f'{ep:03d}_preview.jpg';run([FF,'-v','error','-y','-ss',str(min(2,total/3)),'-i',str(final),'-frames:v','1','-vf','scale=270:480',str(sample)])
    p['sha256']=hashlib.sha256(final.read_bytes()).hexdigest();p['verified_decode']=True;side.write_text(json.dumps(p,ensure_ascii=False,indent=2),encoding='utf8');final.with_suffix('.txt').write_text(p['caption'],encoding='utf8')
    print('EDIT VERIFIED',ep,p['theme'],flush=True);return ep

def main():
    vals=sources();assert len(vals)>=36,len(vals);plan=make_plan(vals)
    (BASE/'uretim_plani.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding='utf8')
    with ThreadPoolExecutor(max_workers=2) as pool:
        for fut in as_completed([pool.submit(render,p) for p in plan]):fut.result()
    sheet=Image.new('RGB',(270*8,480*12),(5,10,24))
    for p in plan:
        im=Image.open(OUT/f"{p['index']:03d}_preview.jpg");d=ImageDraw.Draw(im);d.text((10,430),f"{p['index']:03d}",font=lib.font(30),fill='white');sheet.paste(im,(((p['index']-1)%8)*270,((p['index']-1)//8)*480))
    sheet.save(BASE/'tum_videolar_onizleme.jpg',quality=90)
    print('92 VIDEOS VERIFIED',flush=True)
if __name__=='__main__':main()
