from pathlib import Path
import edit_latest_social as edit

edit.OUT=edit.ROOT.parent/'HOLOmedya/TikTok_Ilk_Oyun_Tanitimi'
edit.OUT.mkdir(exist_ok=True)
edit.render('HOLO_ilk_oyunumuz',
    [edit.tail(23,'clean',7,1.5),edit.tail(47,'fail',9,2)],
    ['İLK OYUNUMUZ YAYINDA!','İZLERKEN KOLAYDI…'],
    'İlk oyunumuz. İlk duvarımız değil.',
    'Merhaba! İlk oyunumuzu yaptık ve Google Play’de yayınladık. 🩵🩷\nAdı HOLO. İki küreyi tek dokunuşla yönetiyorsun. İzlerken kolay geliyor… oynarken biraz değişiyor 😅\nDeneyip fikrini söylersen çok seviniriz. Google Play’de HOLO — Yörünge Oyunu.\n#HOLO #MobilOyun #OyunGelistirme #IndieGame',
    footer='GOOGLE PLAY’DE: HOLO')
