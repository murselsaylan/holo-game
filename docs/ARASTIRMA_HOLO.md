# Başarılı oyunlardan alınanlar (HOLO, 02.11.2026)

Kaynaklar sektör yazıları ve haber siteleridir (şirket verisi değil). Gelir ve elde tutma etkisi HOLO'da ölçülmedi.
Hiçbir oyunun içeriği, adı veya görseli kopyalanmadı; yalnız genel tasarım kalıpları uyarlandı.
Arama sonuçları bazı sorularda zayıf kaldı (Geometry Dash'in ödül döngüsü, Alto'nun fener tasarımı, Royal Match'in "Lightning Rush" ayrıntısı bulunamadı); orada tahmin yazmadım.

## Menü / ilk izlenim

| Örnek | Alınan kalıp | HOLO'daki durum | Karar |
|---|---|---|---|
| Royal Match | İlk 10 bölüm kısa ve kolay, sık sık "iyi gittin" onayı; ilk zor bölüm geç gelir; canlı etkinlik ilk oturumun sonunda başlar | Verimizde 1. bölümden 7. bölüme gelenler yarıya iniyor (106 -> 53) | İlk bölümlerde onay sıklığı artırılmalı (yapıldı: bölüm sonu ödülü, hedef satırı) |
| Subway Surfers | Her gün kendini yenileyen mini hedef; 5 gün üst üste tamamlayınca büyük kutu | Giriş takvimi var, 7. gün büyük ödül var; geri dönüş 7. günde %12 | 7 günlük seriye "büyük kutu" eklenebilir |
| Clash Royale (HB-META-125'ten) | Sabit alt menü, açılışta ücretsiz ödül | Ana menü köşe ikonları, açılış ödülü giriş penceresi | Mevcut, korunur |

## Oyun içi

| Örnek | Alınan kalıp | HOLO'daki durum | Karar |
|---|---|---|---|
| Royal Match | "Az kaldı" (near-miss) heyecan verir, oyuncu tekrar dener | Kayıp ekranı yalnızca yüzde gösteriyor | **Yapıldı:** %80 ve üstünde "ÇOK YAKIN" vurgusu |
| Alto's Odyssey | Her seviyede 3 küçük, isteğe bağlı hedef; hedefler erken öğretir, sonra zorlaşır | Günlük/haftalık görev var, bölüm başına hedef yok | Bölüm başına 3 mini hedef (bitir / 3 yıldız / par süre) planlandı |
| Geometry Dash | Zorluk ve ödül dengesi; zorlu bölüm sonrası kozmetik açılır | Skin açma bölüm ödülüne bağlı | Mevcut |

## Ekonomi / satın alma

| Örnek | Alınan kalıp | HOLO'daki durum | Karar |
|---|---|---|---|
| Crossy Road | Oyunda kazanılan paraya "ödül makinesi": rastgele karakter, tekrar çıkabilir; isteğe bağlı ödüllü reklam; herhangi bir karakter alınca otomatik reklam kalkar | Skin alan oyuncu %13; elmasın çoğu canlanmaya gidiyor | Skin satışı için rastgele skin makinesi (100 elmas) önerilir |
| Subway Surfers | Gizemli kutu = rastgele ödül havuzu; sezon avı: jeton topla, sınırlı karakter kazan; arkadaştan para | Yıldız sandığı, etkinlikler, arkadaş hediyesi var | Sezon jetonu: etkinlik skini için bölüm başına jeton |
| Geometry Dash | Harcanabilir (elmas, orb) ve harcanamaz (yıldız) para ayrı; günde 2 ücretsiz sandık; orb -> anahtar -> sandık | Yıldız (harcanamayan kazanç) ve elmas var; günlük ücretsiz sandık yok | Günlük 1-2 ücretsiz sandık eklenebilir |
| Hybrid-casual raporları | Gelirin %40-50'si satın alma; başlangıç paketi, fiyat basamakları, önce harcama kaynağı sonra kazanç | 9 satın alma, 3 elmas bölüm ödülü yeni kaynak | Başlangıç paketi (ilk 3 gün) önerilir; harcama kalemi (skin makinesi) ödülle birlikte açılmalı |

## Bu belgenin sonucu (öncelik sırası)

1. Near-miss vurgusu (yapıldı, aşağıdaki commit).
2. Bölüm sonu şans ödülü (yapıldı, sunucu yayını bekliyor).
3. Rastgele skin makinesi (skin satışı için).
4. Başlangıç paketi (ilk 3 gün tek seferlik).
5. Günlük ücretsiz sandık + 7 gün seri büyük kutu.
6. Bölüm başına 3 mini hedef.
7. Arkadaş hayaleti ve "seni geçti" bildirimi.

## Dikkat

- Rastgele ödüller ve kutular bazı ülkelerde kumar kuralına girebilir; olasılıklar oyunda gösterilmeli ve gerçek parayla rastgele kutu satılmamalı (yalnız oyunda kazanılan elmasla).
- Çocuk kullanıcılar: oyunun yaş derecelendirmesi ve reklam politikası kontrol edilmeli.

## Günlük bölüm neden işlemedi (veri, 02.11.2026)

- 12 günde yalnızca 16 oyuncu, 26 deneme. Haftanın bölümünü 0 oyuncu oynadı. Arkadaş bağlantısı 3, davet 0.
- Neden: günlük bölüm herkes için **10-100 arasından tek bir bölümdü** (tek deneme). Aktif oyuncunun ortalama %19'u o günün bölümünü açmıştı; 106 aktif oyuncudan 68'i çoğu günü oynayamıyordu. Ödül 10 elmastı.
- Yani sorun yalnızca görünmezlik değil, **amacın oyuncuya uymamasıydı**.
- Yapılan: seviye bandı (3-12 / 13-30 / 31-60 / 61-100, her bandın kendi sıralaması), ödül 25 (+15 üç yıldız), üst üste gün serisi (+5 elmas/gün, 6 güne kadar), ana menüde canlı kart ve günlük bildirim.
- Henüz ölçülmedi: yayından sonra günlük bölüm oynayan sayısına bakılmalı (`daily_runs`). Haftanın bölümü için aynı kontrol sırada.

## İkinci tur: daha derin araştırma ve ekonomi denetimi (02.11.2026)

Kaynaklar sektör blogları ve analiz şirketlerinin yazıları; çoğu birincil veri vermiyor, rakamlar kaynaklar arasında çelişiyor. Yön gösterir, kanıt değildir.

### Dış bulgular
| Konu | Bulgu | Kaynak türü | Karar |
|---|---|---|---|
| İlk oturum | Hangi adımda çıkıldığına bakmadan "ortalama" bakmak yanıltır; tutorial içinde çıkış = uzunluk, ilk birkaç bölümden sonra çıkış = zorluk; 90 sn'lik anlatım yerine 3 mini görev + kozmetik ödül tek bir vakada D1'i %18'den %38'e çıkarmış | analiz blogları (tek vaka) | Bölüm bölüm huni ölçümü eklendi (l1..l15 start/clear/fail) |
| Seri (streak) | Kayıp korkusu seriyi tutar; "seri dondurma" tek kaçırılan günü affederek sert çıkışı önler; titiz bir nedensel çalışma bulunamadı | Duolingo blogu + analizler | Seri tek günlük toleransla yumuşatıldı (haftada 1 gün affedilir) |
| Hayalet yarışı | Arkadaşın ya da lider tablosundakinin hayaleti, girdi kaydı olduğu için hile denetimi de sağlar; elde tutma verisi yok | geliştirici yazıları | "Yolu göster" bu kalıpla yapıldı |
| Türkiye | D1 ~%19, D30 ~%1 (küresel altı), kullanıcıların %76'sı Android, yerli gelirin ~%97'si puzzle | pazar raporları (çelişkili) | İlk günü ve ilk haftayı ölç; Android öncelikli |
| Ekonomi | Kaynaklar sönümden büyükse enflasyon; yeni kaynak eklemeden önce sönüm denetle | ekonomi tasarım yazıları | Aşağıdaki denetim |

### HOLO ekonomi denetimi (son 14 gün, 104 aktif oyuncu)
- Ücretsiz elmas kaynağı toplam 105.186; bunun **89.300'ü "hediye"** (98 oyuncu, kişi başı ~900). Hediye hariç kaynak yalnızca ~16.000 (oyuncu/gün ~11 elmas).
- Harcama 99.440 (canlanma 65.440, kalkan 10.200). Hediye hariç gelirle harcama arasında ~6 kat açık var: harcamayı hediye finanse ediyor.
- Toplam bakiye 317.868 (oyuncu başına ~2.160).
- CLAUDE.md notu: hediyenin varsayılanı **15 Kasım 2026'dan sonra 0'a** çekilecek (`alter table players alter column gift set default 0`). O gün ücretsiz gelir ~%85 düşer; canlanma (20 elmas) alışkanlığı finansmansız kalır.
- Bu yüzden bölüm sonu elmas, şans ödülü, sektör ve günlük ödüller (oyuncu/gün tahmini 40-100 elmas) hediyenin yerini tutmak için gerekli, gereksiz şişirme değil. Yine de ölçülmeli: `wallet_log` ile oyuncu başına net elmas/gün.

### Ölçüm planı (yayından sonra)
1. `funnel_events`: `l1..l15_start/clear/fail` ile hangi bölümde kim bırakıyor.
2. `daily_runs`: günlük bölümü oynayan oyuncu sayısı (önce 16 / 12 gün).
3. `wallet_log`: kaynak/sönüm oranı, `lvlwin`, `lvldrop`, `sectorwin`, `dlevel`.
4. 7. gün geri dönüş (önce ~%12).

## Üçüncü tur: ekran ekran denetim (03.11.2026)

Dış kalıplar (aynı sektör yazıları, birincil veri sınırlı): ana ekran tek merkez, özellikler tam ekran değil açılır pencere (Clash Royale analizi); ana ekranda öne çıkan etkinlik ama "özellik kalabalığı" eleştirisi (Brawl Stars eleştirisi); profil = kimlik numarası + ilerleme sayıları + koleksiyon yüzdesi (Brawl Stars profili); ücretsiz yol cömert kalmalı (Brawl Pass ücretsiz yol yazısı); titreşim ve ses için ayrı kapatma (oyun erişilebilirlik rehberi).

| Ekran | Bulunan eksik | Yapılan |
|---|---|---|
| Profil | Yalnızca isim/bayrak düzenleme; kimlik, ilerleme ve koleksiyon yok | Pilot kartı (kod, bölüm, yıldız, 3 yıldız, S+, sonsuz rekor, skin %); düzenleme karttan açılır |
| Bölüm seçimi | Açılmamış bölümler hiç görünmüyordu (kilit çizimi koda vardı ama döngü bitiyordu); sektör ödülü görünmüyordu | Sektörün kalanı kilitli kutucuklarla, sektör finalinde +100 |
| Görevler | Tamamlanmamış görev "KİLİTLİ" yazıyordu; "1 levels" çoğul hatası | "DEVAM EDİYOR" (kilitsiz), "1 level" |
| Ayarlar | Bildirim kapatma yoktu (oyun hatırlatma planlıyor) | "Hatırlatmalar" düğmesi; kapatınca planlı bildirimler iptal (Android/iOS) |
| Ana ekran | Sektör hedefi, günün bölümü kartı | Önceki tur |

Henüz yapılmayanlar (öncelik sırası): bedava kapsül (4 saatte bir), skin makinesi (elmasla rastgele skin, tekrar = iade), başlangıç paketi (ilk 3 gün, mağaza ürünü gerekir), mağaza ve skin ekranı ayrıntı denetimi, öğretici sonrası ilk 3 bölüm için mini görevler.

## Dördüncü tur: veriyle derinleştirme (03.11.2026)

Kaynak: Supabase `funnel_events` (25 Ekim - 2 Kasım, 80 oyuncu), `wallet_log`, `players`. Örneklem küçük; kesin sonuç değil, yön gösterir.

| Bulgu | Sayı | Anlamı |
|---|---|---|
| Level 1'e başlayan 56 oyuncudan geçemeyen | 14 (%25) | En kolay bölüm (zorluk puanı 14,7) ama en büyük sızıntı; l2/l3/l5 temizleme oranı %93-95. Sorun bölüm zorluğu değil ilk yanışlardan sonraki deneyim |
| Level 1'i geçenlerin ortalama yanışı | 5,2 (en çok 31) | Öğretici sonrası kontrol alışması uzun sürüyor |
| 1 günden uzun kalan / 3 günden uzun / 7 günden uzun | 40 / 27 / 2 (80 içinde) | 7. gün penceresi henüz kısa; D7 yorumlanamaz |
| Yeni oyuncu (app_open ilk gün) | 15-19/gün (26-28 Ekim) → 2-5/gün (30 Ekim sonrası) | Düşüş edinim tarafında, oyun içinde değil |
| Bakiye ortancası | 1045 (%90'ı 3600 üstü değil, %90'ı 500 üstü) | Mevcut oyuncular zengin; bölüm başına +3 elmas onlar için görünmez, yeni oyuncu için anlamlı |
| Elmas harcaması | canlanma 66k, prestij skin 46k, skin 28k (22 oyuncu), kalkan 10k | 147 oyuncudan yalnız 22'si skin almış; çoğunun 1000+ elması var → skin değeri algısı zayıf (deneme imkânı yok) |

Yapılan: başarısızlık ekranında elmas yetmeyince en büyük düğme gri "ELMAS YETMİYOR" ölü düğmesiydi, altında paralı paketler vardı. Hediye kalkınca her yeni oyuncu bunu görecek. Artık ölü düğme yok: reklamla devam üstte, ücretsiz kalkan/yeniden dene ana eylem, paketler küçük ve ikincil (`store_assets/menu_ui/fail_poor_noad.png`, `fail_poor_ad.png`).

Sıradakiler (veri destekli): (1) level 1-3'te 3. yanıştan sonra yolu göster/kalkanı kendiliğinden öner, (2) skin "bir bölüm dene" (satın almadan önce), (3) yeni oyuncu elmas akışı hediye sonrası için ölçüm.

### Dış kaynaklar: neden tutmuyor (03.11.2026, hepsi blog/forum/sektör yazısı; birincil veri değil)

- Hiper-casual ölçütleri kaynaklara göre değişir: D1 yaklaşık %20-35, D7 %5-10, D30 %1-3 ([Juego Studio](https://www.juegostudio.com/blog/how-to-increase-user-retention-and-increase-your-games-lifetime), [MWM](https://mwm.ai/glossary/retention), [Segwise](https://segwise.ai/blog/mobile-gaming-app-user-retention-strategies.md)). GameAnalytics 2025 tüm türlerde D1 ortancası ~%22, D7 ~%4 ([özet](https://gamedevreports.substack.com/p/gameanalytics-mobile-gaming-benchmarks)). Yani bu türde çoğu oyuncunun gitmesi normal; asıl soru ilk oturumda ne kadar kaybettiğimiz.
- İlk oturumda terk nedenleri: karışık öğretici, zorluk sıçraması, teknik sorun ([AppFollow](https://appfollow.io/blog/mobile-game-retention)); D1 zayıfsa onboarding, D7 zayıfsa alışkanlık sorunudur ([AppAgent](https://appagent.com/?p=61637)).
- Crossy Road ekibi: tek dokunuş tek başına tutmadı; kontrol hissi, toplama (karakterler), sosyal paylaşım ve doğru anda puan isteme öne çıktı ([PocketGamer.biz](https://www.pocketgamer.biz/crossy-road-sharing-retention/)).
- Geometry Dash: kademeli zorluk + "bir deneme daha" döngüsü + müzikle senkron ([özet, zayıf kaynak](https://program.londondesignfestival.com/update2025/news/geometry-dash-classic)).
- İlk bölüm neredeyse kaybedilemez olmalı; takılana kolaylaştırıcı bir araç verilmeli ([Unity FTUE](https://unity.com/how-to/10-first-time-user-experience-tips-games), forum yorumları).

HOLO verisiyle eşleşme (25 Ekim-2 Kasım): 81 oyuncunun 29'u uygulamayı yalnızca bir kez açmış; 16 oyuncu hiç bölüm geçmemiş, 13'ü 3 günden uzun süredir yok; level 1'de geçenlerin ortalama yanışı 5,2. Esnek (rolling) D1 yaklaşık %51 (39/76), D3 %39 (26/67), D7 yalnızca 8 uygun oyuncu (1 dönen) - ölçüt tanımı farklı olduğu için sektör tablosuyla doğrudan karşılaştırılamaz.

Yapılan: "yolu göster" artık hiçbir oyuncunun koşusu yokken bölümün kendi doğrulanmış çözümünü (`ref_taps`) gösteriyor (3. yanıştan sonra, her bölümde). Her bildirim "BAŞARIM AÇILDI" etiketiyle çıkıyordu; etiket artık yalnız gerçek başarımlarda.

## Beşinci tur: menü, mağaza, bildirim görünümü (3 Kasım 2026)
Kaynaklar zayıf (blog ve danışman yorumu, ilk elden değil; oyunun içinde ayrıca doğrulanmadı):
- Royal Match mağazası: "Popular" / "Best Value" etiketleri yalnız seçili paketlerde ([Gamigion](https://www.gamigion.com/game-shop-best-practices-royal-match-from-dream-games/)).
- Brawl Stars: tek odak, az teklif ([Pratt SI eleştirisi](https://ixd.prattsi.org/2025/02/design-critique-brawl-stars/)).
- Toast: kullanıcıyı kesmeyen, kendiliğinden kapanan, düşük önemli mesajlar için ([Microsoft toast yönergesi](https://learn.microsoft.com/cs-cz/windows/apps/design/shell/tiles-and-notifications/toast-ux-guidance)).
Uyarlanan: elmas paketlerinde POPÜLER (350) ve EN AVANTAJLI (2500) rozeti + paket başına "+%N" (en küçük pakete göre elmas/para oranı); bildirim şeridi 700x116 yerine 620x92, "BAŞARI KİLİDİ AÇILDI" etiketi kalktı, başlığın içinde zaten var. Etkisi (dönüşüm) yayından sonra `wallet_log` / `purchases` ile ölçülecek.
