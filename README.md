# HOLO — iki küre, tek nabız (mobil sürüm)

Dikey ekran, tek dokunuşla oynanan, 100 bölümlük zor bir refleks/ritim oyunu. Dokun → yörünge değişir.
Pygame ile yazıldı; Android'e Buildozer ile paketlenir. Küresel sıralama için küçük bir sunucu içerir.

## Çalıştırma (masaüstü)

```bash
.venv\Scripts\python.exe main.py
```

Pencere telefon oranındadır (9:16). Fare tıklaması = dokunuş. `SPACE/↑` yörünge değiştirir, `ESC` duraklatır, `R` yeniden başlatır.

## Mimari

| Dosya | Görev |
|---|---|
| `sim.py` | Saf-Python, **deterministik** fizik çekirdeği (sabit 60 Hz). Oyun, çözücü ve sunucu aynı kodu kullanır. |
| `holo.py` | Oyun döngüsü (sabit adım + interpolasyon, kamera, ekran durumları). |
| `level_manager.py` | Bölüm çizimi (statik katman bir kez çizilir; kamera destekli, bölümler ekrandan uzun olabilir). |
| `ui.py` | Dokunmatik, dikey arayüz (kaydırmalı liste, büyük butonlar, ekran klavyesi ile isim girişi). |
| `online.py` | Sıralama istemcisi (thread'li, çevrimdışı kuyruk, sunucu saatine göre imza). |
| `supabase/functions/scores/` | Yayındaki sıralama sunucusu: TypeScript (Supabase Edge Function): `sim.ts` (fizik), `handler.ts` (rotalar + hile kontrolleri), `store_pg.ts` (Postgres). |
| `server/leaderboard_server.py` | Aynı protokolün Python sürümü (yerel test/alternatif; sqlite ya da Postgres). |
| `levelgen/` | Bölüm üretici + **çözücü**: her bölüm gerçek fizik üzerinde bir bot tarafından oynanıp doğrulanır. |
| `tools/` | `verify_all.py`, `smoke_test.py` (gerçek oyun döngüsü), `server_test.py` (istemci+sunucu+hile denemeleri), `screens.py`, `perf.py`. |

## Zorluk nasıl tasarlandı

| Bölümler | Arena boyu (px) | Dönüş hızı | Koridor (px) | Güvenlik payı* (px) | Ort. hamle | Ort. süre | Gizli hızlanma (bölüm sonunda) |
|---|---|---|---|---|---|---|---|
| 1–20 | 1611 | 1.0× | 316 | 54.8 | 18 | 22 sn | +25% |
| 21–40 | 1971 | 1.14× | 281 | 38.4 | 21 | 25 sn | +31% |
| 41–60 | 2529 | 1.26× | 263 | 21.0 | 44 | 37 sn | +36% |
| 61–80 | 3388 | 1.38× | 242 | 16.8 | 45 | 37 sn | +41% |
| 81–100 | 4374 | 1.49× | 226 | 18.2 | 71 | 53 sn | +46% |

En uzun bölüm L92: 134 hamle / 82 sn. Bölüm 100: 69 hamle, 57 sn, 1.54× hız (bitişte ≈2.3×), güvenlik payı 12 px; arena boyu 4870 px.
**Dürüst not:** güç kapıları geniş koridor ister (dar koridorda büyümüş orb ya da kalkan bariyeri geçişi çözülemez oluyor), bu yüzden geç bölümlerde koridor eskisinden biraz geniş (≈250 px); zorluğu kapı + tehlike kombinasyonları, açık alan denemeleri ve bölüm uzunluğu getiriyor. 64 bölümde en az bir güç kapısı var.

\* **Güvenlik payı** = yörüngenin yarıçapına eklenebilecek en büyük ek yarıçap (px) — yani *en iyi oyunun* hâlâ
tolere edebileceği hata. 12 px, en sıkışık hamlede kabaca ±25 ms zamanlama toleransı demektir. Çözücü her bölümde
bunu ölçer; payı tabanın altına düşen bölüm otomatik gevşetilir, yani hiçbir bölüm "imkânsız" çıkmaz.

* 5 sektör, her biri yeni bir mekanik getirir: koridor/seken duvar → süpürücü piston + **Aegis bariyerleri / çatlak duvarlar** → **küçülme boğazları / kaçış koşuları** / mikro geçit → lazer/döner kol → hepsi bir arada.
* Bölümler bir çözücü (beam-search bot) tarafından gerçek fizik üzerinde **oynanıp kanıtlanır**; her bölüm `ref_taps` (kanıtlı çözüm) içerir ve
  3 yıldız her zaman mümkündür (yıldızlar bu kazanan yörüngeden türetilir). Bölüm başında yalnızca ilk dokunuşa kadar 3.5 sn güvenli yörünge vardır;
  dokunduktan sonra dokunulmazlık yoktur (duvardan atlama açığı bu yüzden kapalıdır).
* **Dürüst not:** zorluk çözücüyle ölçülmüştür, insan oyun testiyle değil. Eğri yanlış hissettirirse `levelgen/plan.py`
  (`difficulty`, `margin_target`, `speed_of`, `height_of`) içindeki eğrileri değiştirip yeniden üretin.

Bölümleri yeniden üretmek / doğrulamak:

```bash
.venv\Scripts\python.exe levelgen\gen.py 1 100                 # üret + doğrula (14 çekirdekte ~1 saat)
.venv\Scripts\python.exe levelgen\gen.py --only=30,44          # yalnızca belirli bölümler
.venv\Scripts\python.exe levelgen\remeasure.py                 # fizik değişince tüm bölümleri yeniden doğrular
.venv\Scripts\python.exe tools\verify_all.py                   # 100 bölümün referans çözümünü gerçek simülasyonda oynatır
.venv\Scripts\python.exe levelgen\preview.py 1 10              # screenshots\sheet_1_10.png
```

## Güç alanları artık zorunlu ("kapılar")

Küçülme, büyüme, kalkan ve hızlanma eskiden süstü. Şimdi bölümlerde **ilgili güç olmadan geçilemeyen kapılar** var
(`levelgen/gates.py`; üretici her kapıyı çözücüyle **"güçsüz çözülemez"** diye doğrular, gerekirse sıkılaştırır):

| Güç | Kapı | Neden zorunlu |
|---|---|---|
| Küçülme (mavi alan, 10 sn) | 112–136 px'lik dar boğaz | Küçülünce çift kısalır (100→62 px) ve yarıçap 9'a iner; normal çift sığmaz |
| Büyüme (yeşil alan, 10 sn) | Çatlak (kırılabilir) duvar | Yalnızca büyük orb (yarıçap ≥ 21) duvarı parçalar, küçük orb ölür |
| Kalkan (pickup) | İnce enerji bariyeri | Bariyer normalde ölümcül; kalkanla içinden geçilir (bariyerin içindeyken dokunulmazlık uzar) |
| Hızlanma (sarı alanlar) | Kaçış koşusu | Koşu bölgesine girince arkandan bir duvar kovalamaya başlar; hızlanmadan yetişemezsin |

Öğretim: 7. bölüm çatlak duvar, 11. kalkan bariyeri, 15. küçülme boğazı, 18. kaçış koşusu; ilk yaklaşmada bir ipucu şeridi çıkar.
Kalibrasyon araçları: `levelgen/gate_lab*.py`. Sim v5 (`SIM_VERSION`) bu mekanikleri içerir; `sim.ts` aynı şekilde güncellendi.

## Her bölüm eşsiz

* **Serbest biçimli rotalar** (`wander`): ızgarasız, rastgele uzunluk ve konumlu koridor bacakları; her bölümün kendi tohumu var.
* **Açık alan türleri:** `arena` (kayan kapı, tam genişlik lazer, döner kollar, çift boşluklu duvar, sütun ormanı, kepenk sıraları),
  `gates` (bölme duvarları), `chambers` (kapılarla bağlı odalar, oda ölçüleri rastgele), `mines`. Kapılar (küçülme/büyüme/kalkan) açık alanlarda da var.
* **Yeni tehlikeler:** zikzak bariyer (`baffle`), huni, kapanan kepenk (`shutter`), ikiz döner; koridor genişliği bacak başına değişir.
* **Bölüm başına stil:** her bölümün tehlike hızı/lazer periyodu/boyutu farklı; tehlike seti sektör havuzundan rastgele seçilir, yerleşim eşit aralıklı değil.
* **Benzerlik denetimi:** `python levelgen/similar.py` rotaları ızgaraya çizip (aynalama dahil) karşılaştırır; `--fix` çok benzeyeni yeniden çeker (`levelgen/variants.json`).
* `levelgen/plan_check.py`: çözücüsüz kuru çalıştırma; `levelgen/sheet.py 1 50`: tüm bölümlerin önizleme levhası.

## Kalkan, seken duvar, duvar hatası (sim v8)
* **Kalkan:** duraklat düğmesinin yanındaki düğme (elindeki kalkanı takar, yoksa 10 elmasa alır ve anında takar). Ölüm ekranında kalkan satın alma **yok** — önceden, oyun sırasında alınır. Satın alınmış kalkan harcanırsa o koşu sıralamaya gönderilmez.
* **Seken duvar (kinetik tampon):** çarpınca dönüş yönü tersine döner **ve 0.7 sn hız fırlatması** verir; ~39 bölümde ve arena "seken duvar" sıralarında var.
* **"Duvara takılıp ölme" hatası düzeltildi:** kalkan bir duvara çarpıp sekince artık sabit bir süre değil, **gerçekten temiz olana kadar** (en fazla 1 sn) dokunulmazlık sürüyor — önceden dokunulmazlık duvarın içindeyken bitip ölüme yol açabiliyordu. `tools/wallstuck_test.py` bunu tekrar üretip doğruluyor.
* **Sim v8:** ilk dokunuş öncesi doğuş korumasında orb duvara girmez, seker; kalkan duvara çarpınca hayalet gibi geçmek yerine geri seker (enerji bariyeri hariç).

## Bölüm üretimi: boşluk, tekrar ve imkânsız zamanlama düzeltmeleri
Kullanıcı geri bildirimi: bazı bölümler çok kolay/boş kalıyordu (üretici, hedeften kolay çıkan bölümü zorlaştırmayı hiç denemiyordu) ve bazı
bölümler (ör. 51) yalnızca kare-mükemmel dokunuşla geçilebiliyordu. İkisi de düzeltildi:
* **Sıkılaştırma geçişi:** bir bölüm hedeften çok daha kolay çıkarsa (`levelgen/gen.py`), üretici artık ekstra tehlike ekleyip zorluğu
  hedefe yaklaştırıyor (önceden yalnızca çok zor çıkan bölümler gevşetiliyordu, kolay çıkanlar hiç zorlaştırılmıyordu).
* **Yeniden tohum:** bir yerleşim tam tehlike sayısıyla hiç çözülemiyorsa (geometrik olarak, hıza bakılmaksızın), üretici artık tehlikeleri
  azaltmadan önce birkaç farklı rota/yerleşim dener — çoğu "boş" bölüm, aslında hiç uymayan bir yerleşimin tehlikelerinin çıkarılmasıydı.
* **Zamanlama sağlamlığı:** referans çözüm artık yalnızca "kazanıyor" değil, her dokunuş ±2 kare (33 ms) kaydırılınca da çoğunlukla
  kazanıyor mu diye test ediliyor (`jitter_rate`); değilse alternatif bir çözüm aranıyor. Bazı bölümler yine de doğası gereği hassas kalabilir —
  bunlar `tools/level_qa.py` çıktısında görülür.
* **Test araçları:** `python tools/level_qa.py` (referans çözüm, doğuş güvenliği, yavaş oyuncu modeliyle çözülebilirlik, zamanlama sağlamlığı);
  `python levelgen/rebalance.py --fix` zorluk sıralaması dışı kalanları yeniden çeker; `python levelgen/similar.py --fix` birbirine çok benzeyenleri yeniden çeker.

## Test araçları (geçici) ve yayın modu

`config.json` içinde `"test_tools": true` (ya da `"dev_unlock_all": true`) iken: ana menüde **BÖLÜMLER** (bölüm seçimi), oyun içi **Duraklat** menüsünde
**< ÖNCEKİ / SONRAKİ >**, **OTOPİLOT** (çözümü kendisi oynar, bölüm bitince sonrakine geçer) ve **ÖLÜMSÜZ**. Araç kullanılan koşu kaydedilmez ve sunucuya gönderilmez.
**Yayın sürümü:** `test_tools`, `dev_unlock_all`, `dev_free_purchases` = false yapılınca bölüm seçimi ve tüm araçlar kaybolur; oyuncu yalnızca açtığı
bölümlerden devam eder.

## Uzay teması ve gerilim

* **Sektör = uzay sahnesi:** ALPHA ORBITAL (halkalı gaz devi, kraterli buz ayı), PULSAR VOID (pulsar + istasyon gövdesi), QUANTUM
  (kristaller, altıgen kafes), EVENT HORIZON (kara delik, lav kayası), OMEGA VOID (süpernova, obsidyen). Her bölümde tohumlu nebula,
  yıldız katmanı, paralaks (arka plan kameradan yavaş kayar), kuyruklu yıldızlar. Kod: `space_art.py`.
* **Gizli hızlanma:** `sim.py` içinde dönüş hızı ilerlemeyle `1 + ramp·ilerleme^2.2` çarpanıyla artar (ilk yarıda fark edilmez, son
  kısım sprint). Hız HUD'da hiçbir yerde gösterilmez. Fizik değiştiği için tüm bölümler yeniden çözüldü (`levelgen/resolve.py`).
* **Gerilim işaretleri (istemci):** ilerleme %50'yi geçince kalp atışı sesi hızlanır, ekran kenarlarında kırmızı nabız parlar,
  uzay tozu çizgileri belirir ve hızla uzar; hedef ekran dışındaysa yön oku çıkar.
* **Ek:** kişisel en iyi koşunun **hayaleti** (ayarlardan kapatılır), bölüm giriş kartı (sektör/isim, 20'nin katlarında "PATRON BÖLÜM"),
  menülerde uzay arka planı.

* **80 görünüm, 16 katalog:** her katalogda 5 skin, Efsanevi → Sıradan. Sıradanlar bölüme ulaşınca, 8 "Özel" başarımla açılır; gerisi mağazadan elmasla (Efsanevilerin gerçek para seçeneği de var). Ayrıca tüm skinleri elmasla satan özel "Değerli Madenler" kataloğu (Cosmic Diamond oyundaki en pahalı öğe: 1500 elmas / $14.99). Tanım: `skin_catalog.py`, rehber: `docs/MONETIZATION.md`.
* **Test modu (geçici):** `config.json` içinde `"dev_unlock_all": true` iken tüm bölümler ve görünümler seçilebilir (kayıt dosyasına
  yazılmaz, menüde kırmızı "TEST MODU" etiketi görünür). Yayından önce `false` yap ya da satırı sil.
* **Uzay kokpiti arayüzü:** koyu cam paneller, neon hatlı düğmeler (sektör renkleri), yıldız parıltıları; yuvarlak köşeler tek "tatlı" dokunuş; yeni "tatlı" skinler (Mochi Pal, Mint Blob, Lemon Chick,
  Berry Kitty, Cloud Bunny) ve **mağaza** (elmas paketleri, kalkan, skinler) — bkz. `docs/MONETIZATION.md`.
* **Ses:** menü için müzik kutusu, her sektör için ayrı müzik (`audio_tracks.py`, saf Python ile üretilir), kırılma/kovalama/mağaza sesleri.
  **Dürüst not:** müzikleri ben dinleyemem; notaları müzik kuramıyla yazdım, beğenmezsen `audio_tracks.SPECS` içindeki akor/tempo değerlerini değiştirip
  `python audio_tracks.py` çalıştır.
* **Başarımlar** (19 adet, yerel; 8'i skin verir), ilk açılışta "nasıl oynanır" kartı, titreşim ayarı, `crash.log` (kayıt klasöründe).
* Animasyonlu menü sahnesi (yıldız, kuyruklu yıldız, sürüklenen asteroitler), oyun içinde sürüklenen asteroitler, sektör renginde solucan deliği
  hedefi, bölüm bitince ışık hızı (warp) efekti.

## Küresel sıralama

Sıralama = **çözülen bölüm sayısı**, eşitlikte **bölüm başına en iyi skorların toplamı**. Skoru istemci göndermez;
istemci bölümün **dokunuş kaydını** yollar, sunucu aynı simülasyonda yeniden oynatıp skoru/yıldızı kendisi hesaplar
(HMAC imzalı, zaman damgalı, saniyede insanüstü dokunuş hızı reddedilir). Bkz. `tools/server_test.py`.

Sunucu:

```bash
python server/leaderboard_server.py --port 8787 --db holo_scores.db
```

**Yayın:** sıralama sunucusu TypeScript'e çevrildi (`supabase/functions/scores/`, Supabase Edge Function + Postgres, tek ücretsiz platform). Rehber: `supabase/DEPLOY.md`. `sim.ts`, `sim.py`'nin birebir karşılığıdır (`node supabase/functions/scores/parity_test.ts`). Python sunucusu (`server/`) yerel geliştirme içindir; alternatif barındırma: `server/DEPLOY_RENDER_NEON.md`. Dışarıdan test: `tools/check_server.py`.
Başka bir barındırıcıda çalıştırırsan `config.json` içindeki `server_url` değerini değiştir.
Sunucu `sim.py` ve `levels/` klasörüne ihtiyaç duyar (aynı repo). `holo_scores.db` düzenli yedeklenmelidir.

**Sınırlar (dürüst not):** Tekrar oynatma doğrulaması "skor uydurmayı" engeller, fakat bir botun insan gibi
oynayıp geçerli bir kayıt üretmesini engelleyemez. Kaba dokunuş-hızı kontrolü dışında bot tespiti yoktur.
Küfürlü isim filtresi yoktur.

## Android

Bu Windows bilgisayarda WSL kurulu değil (kurmak yönetici yetkisi ister). APK'yı **Google Colab** ile derle:
`python tools\make_apk_zip.py` → `holo_apk_source.zip` oluşur → `HOLO_APK_OLUSTURUCU.ipynb`'yi Colab'da aç, hücreleri çalıştır, zip'i yükle, APK iner.
(Alternatif: klasörü GitHub'a yükleyip `.github/workflows/apk.yml` iş akışını çalıştır.) Aşağıdaki Buildozer notları yerel Linux içindir.

Buildozer yalnızca Linux/macOS'ta çalışır (Windows'ta WSL2 kullanın):

```bash
pip install buildozer
buildozer android debug        # bin/holo-5.0.0-*-debug.apk
```

`buildozer.spec` hazırdır (dikey, INTERNET izni, arm64+armv7). iOS: Pygame iOS'u desteklemez; iOS için oyunun
başka bir motora (Godot/Unity) taşınması gerekir — `sim.py`, `levels/*.json` ve sunucu protokolü motordan bağımsızdır.

## Testler

```bash
.venv\Scripts\python.exe tools\smoke_test.py 1 5 25 60 100   # gerçek oyun döngüsünde referans çözümleri oynatır
.venv\Scripts\python.exe tools\server_test.py                # istemci + sunucu + hile denemeleri
```

## Not: eski kayıt

Bölümler yeniden tasarlandığı için eski ilerleme (v1) taşınmaz; profil adı, bayrak, açılmış görünümler ve ayarlar korunur.
Eski dosya `save_data.v1.backup.json` olarak yedeklenir. Eski betikler `legacy/` içindedir.
