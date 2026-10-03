# Son oynanış ve görünüm düzenlemeleri — 23 Eylül 2026

- Duraklatmadan ve elmasla canlanmadan sonra 1,2 saniyelik 3–2–1 hazırlık süresi.
  Bu sırada fizik, kronometre ve hamle kaydı ilerlemez; biriken zaman sonradan atlatılmaz.
- Aynı fizik karesinde gelen çift giriş ve basılı tuş tekrarı engellenir.
- Siyah ekran kenarları ve alt bilgi alanına dokunmak yörüngeyi değiştirmez.
- Duraklatma ve kalkan düğmelerinin genişletilmiş dokunma alanları çakışmaz.
- Duraklatıldığında küreler bir önceki konuma sıçramaz. Hareketli engellerin
  çizim zamanı kürelerin ara kare çizimiyle eşleştirilir.
- Sabit kürenin etrafında ince, parçalı yörünge işareti; yüzde ve çeyrek
  işaretleri olan bölüm ilerlemesi; ayrı skor, süre ve kombo/adım alanları.
- Menüde beş sektörün tamamlanma çubuğu.
- Ateşlenmek üzere olan lazerler sürekli görünen kesik amber çizgiyle belirtilir.
- Başarım bildirimleri aktif oynanışı kapatmak yerine duraklamayı veya sonuç
  ekranını bekler; beklerken bildirim süresi tükenmez.
- Yeni hazırlık metni dört dilde mevcuttur.

## Colab hatası

Paylaşılan defterin `2Y2L6K3aiBr4` hücresindeki kayıt, Pygame derlenirken
`fatal error: 'longintrepr.h' file not found` hatasını içeriyordu.
p4a'nın varsayılan Pygame tarifi 2.1.0 sürümünü kullanıyor:
https://github.com/kivy/python-for-android/blob/develop/pythonforandroid/recipes/pygame/__init__.py

`buildozer.spec` artık Pygame 2.6.1'i seçer. `android_recipes/pygame` tarifi,
üretilmiş C dosyalarını içeren resmi PyPI kaynak dağıtımını kullanır.
İndirilen dağıtımda SDL2 C kaynağı, Cython 3.0.11 üretimi ve Android şablonu
yerel olarak kontrol edildi. Android'de tam derleme henüz doğrulanmadı.

Yerel `HOLO_APK_OLUSTURUCU.ipynb` yenilendi:

1. Ubuntu'nun güncel ncurses/tinfo paketlerini kurar, başarısız komutta durur.
2. Tek bir güncel ZIP ister; iptal/eksik dosya durumunu açıkça bildirir.
3. Eski projeyi silmeden yeni çalışma klasörü kullanır, eski derleme önbelleğini taşımaz.
4. Derleme çıkış kodunu kontrol eder; hata halinde eski bir APK'yı başarı diye sunmaz.
5. Tam derleme kaydını `build-apk.log` dosyasına yazar.

`holo_apk_source.zip` test araçları açık kaynak paketidir, kurulabilir APK değildir.
Paket özel Pygame tarifini içerir; eski ZIP parçaları, kayıt dosyaları, günlükler ve
yerel araç ayarları dışarıda bırakılmıştır. Kaynak `config.json` ve oyuncunun kayıtları korunmuştur.

Colab tarayıcısı Google giriş ekranında kaldığından çevrimiçi defter değiştirilmedi
ve APK derlemesi başlatılmadı. Google'a giriş yaptıktan sonra yerel güncel defteri
Colab'da açın, üç adımı çalıştırın ve ikinci adımda güncel ZIP'i seçin.

## Kontroller

- `tools/verify_all.py`: 100 bölümün referans çözümü üç yıldız, sıfır sorun.
- `tools/test_play_all.py`: gerçek HoloGame döngüsünde 100/100 bölüm üç yıldızla
  tamamlandı; sonuç kaydı `build/polish_all_levels.log` dosyasında.
- `tools/ui_test.py`: arayüz, mağaza, başarımlar, dört dil ve canlanma kontrolleri geçti.
- `tools/polish_test.py`: çift giriş, tuş tekrarı, odak kaybı, hazırlık süresi,
  dokunma sınırları, bildirim kuyruğu ve sunucu tekrar oynatma uyumu geçti.
- `tools/screens.py`: ekranlar çizildi ve PNG olarak kontrol edildi.
- `tools/perf.py 10 50 100`: bu bilgisayarda başsız çizim yaklaşık 4,9–6,3 ms/kare;
  telefon performansını temsil etmez.

Çalıştırma: `.venv\Scripts\python.exe main.py`

Windows için `dist/HOLO.exe` de yeniden derlendi. Geçici kayıt klasörü ve kapalı
ağ uç noktasıyla başsız açılış kontrolünde beş saniye çalıştı, çökme kaydı oluşmadı.
