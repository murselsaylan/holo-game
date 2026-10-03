# Mağaza ve Google Play satın almaları

## Ekonomi
* **Para birimi: Elmas.** Başlangıçta 20 elmas; her başarım +5 elmas verir. Gerisi mağazadan elmas paketi alınarak kazanılır.
* **Elmas paketleri (tüketilebilir):** 100 / 350 / 1000 / 2500 elmas.
* **Kalkan:** 10 elmas (en fazla 5 stok). Oyun içinde duraklat düğmesinin yanındaki kalkan düğmesinden alınır ve anında takılır.
  Ölüm ekranında artık kalkan satın alma seçeneği yok — kalkanı önceden, oyun sırasında almalısın.
  Satın alınmış kalkan harcanırsa o koşu sıralamaya gönderilmez (sunucu koşuyu yeniden oynayamaz); bölüm ilerlemesi yine sayılır.
* **Bahşiş / bağış ve "Devam et (elmasla)" özelliği yok.** Reklam da yok.

## 80 görünüm, 16 katalog (her katalogda 5 skin: Efsanevi → Sıradan)
| Nadirlik | Nasıl alınır | Fiyat |
|---|---|---|
| 1 EFSANEVİ (16 skin) | Elmasla **veya gerçek parayla** (Play ürünü `skin_<id>`) | 500 elmas / $4.99 (biri hariç) |
| 2 DESTANSI (16) | Mağazada elmasla | 350 elmas |
| 3 NADİR (16) | Mağazada elmasla | 250 elmas |
| 4 ÖZEL (16) | 8'i **başarım ödülü**, 8'i mağazada | 150 elmas |
| 5 SIRADAN (15) | **Bölüme ulaşınca** otomatik açılır (0, 5, 10 ... 100) | ücretsiz |

**"Değerli Madenler" özel kataloğu:** 5 skin (Cosmic Diamond / Nova Platinum / Solar Gold / Lunar Silver / Stardust Bronze),
hepsi mağazadan (bölümle açılan yok), her biri kendi nadirliğindeki normal fiyattan daha pahalı.
**Cosmic Diamond oyundaki en pahalı öğe:** 1500 elmas veya **$14.99** (diğer efsanevilerin 3 katı).

Toplam: 15 bölüm ile, 8 başarımla, 57 mağazadan alınıyor. Katalog tanımı: `skin_catalog.py` (sıra, fiyat, kaynak tek yerde).

## Play Console'da oluşturman gereken ürünler (20 adet, kimlikler birebir)
Hepsi **Uygulama içi ürün (in-app product)**, tek seferlik.

* **Elmas paketleri (tüketilebilir)**: `pack_100` ($0.99), `pack_350` ($2.99), `pack_1000` ($6.99), `pack_2500` ($14.99)
* **Efsanevi skinler (tüketilemez)**, $4.99 (Cosmic Diamond hariç): `skin_cyber_phantom`, `skin_supernova`, `skin_event_horizon`, `skin_big_bang`, `skin_quantum_lattice`, `skin_saturn_ring`, `skin_galaxy_cat`, `skin_rainbow_unicorn`, `skin_royal_crown`, `skin_nova_heart`, `skin_sakura_fox`, `skin_leviathan`, `skin_void_walker`, `skin_snow_leopard`, `skin_rocket_bunny`
* **En pahalı skin**: `skin_diamond_prestige` — **$14.99**

Yerel fiyatı mağaza kendisi gösterir. Diğer skinler yalnızca elmasla alınır, onlar için Play ürünü açman gerekmez.

## Ödeme arka ucu (`shop.py`, `config.json`)
| ayar | anlamı |
|---|---|
| (hiçbiri) | Fiyatlar görünür ama satın alma düğmeleri "yakında" der |
| `"dev_free_purchases": true` | **TEST**: her satın alma anında başarılı olur, para çekilmez. Yayından önce kaldır |
| `"billing": "android"` | Google Play Faturalandırma (Play sürümü zip'inde otomatik açılır) |

## Play sürümü için adımlar (sen yapacaksın: hesap/ödeme bilgisi girmem)
1. Google Play Console geliştirici hesabı (tek seferlik ücret), ödeme profili ve vergi bilgileri.
2. Uygulamayı oluştur. **Gizlilik politikası URL'si** zorunlu, hazır ve yayında:
   **https://claude.ai/artifact/Ubg1s8A7QDxL8fNSU8UR5z**
   "Veri güvenliği" formu: toplanan veri = takma ad, ülke, oyun skorları, rastgele oyuncu kimliği (sıralama için); ödeme bilgisi Google'da kalır; veri satılmaz.
3. Yukarıdaki 20 ürünü oluştur.
4. `python tools\make_apk_zip.py --release` → `holo_release_source.zip` (test araçları kapalı, bölüm seçimi yok, faturalandırma açık).
   `HOLO_AAB_OLUSTURUCU.ipynb` bunu Colab'da **imzalı AAB**'ye çevirir (anahtar otomatik üretilir; `holo-upload.jks` + `holo-keystore-bilgi.txt` dosyalarını sakla).
5. AAB'yi **iç test** kanalına yükle, lisans test kullanıcısı hesabıyla satın almayı dene (test kartıyla ücret çıkmaz).

## Play kuralları (2026)
* **Play Billing Library 8+** zorunlu (bridge v8.3.0 için yazıldı), **hedef API 36** (`buildozer.spec`'te ayarlı).
* Dijital ürünler yalnızca Play Faturalandırma ile satılmalı (dış ödeme bağlantısı yok).
* Rastgele ödüllü kutu/loot box yok; her ürünün içeriği ve fiyatı açık.

## Elmas cüzdanı ve satın almalar sunucuda (1.0.3)
* **Elmas bakiyesi sunucuda** (`players.diamonds`). Telefondaki sayı yalnızca kopya; her kazanç ve harcama `scores`
  fonksiyonundaki `/api/wallet` üzerinden geçer ve `wallet_log` tablosuna **bir kez** yazılır (aynı istek tekrar gelirse sayılmaz).
* Fiyatları ve ödülleri **sunucu** belirler: `supabase/functions/scores/wallet_data.ts` oyunun kendi kataloğundan üretilir.
  Fiyat, başarım, günlük görev veya paket değiştirince: `python tools\gen_wallet_data.py` → fonksiyonu yeniden yükle.
* Eski sürümden gelen oyuncunun telefonundaki elmaslar ilk senkronizasyonda **olduğu gibi** aktarılır (sınır yok).
* Hediye: `UPDATE players SET gift = gift + 1000;` → oyuncu oyunu açınca "HEDİYE: +1000 ELMAS" görür.

### Gerçek parayla satın alma nasıl işler
1. Oyuncu Play'de öder. Satın alma telefonda **tüketilmez / onaylanmaz**, `iap_pending` olarak kayıt dosyasına yazılır.
2. Oyun satın alma belirtecini (token) sunucuya yollar. Sunucu **Google Play Developer API** ile sorar:
   ödendi mi, bekliyor mu, iptal mi; satın alma **bu oyuncunun hesabına mı** ait (`obfuscatedAccountId`).
3. Ödendiyse elmas / skin hesaba yazılır. Belirteç `purchases` tablosunda tutulur: **aynı belirteç ikinci kez sayılmaz**,
   başka bir hesap kullanamaz.
4. Ancak sunucu "tamam" dedikten sonra telefon paketi tüketir (`consume`) veya skini onaylar (`acknowledge`).
5. Arada uygulama kapanırsa / internet giderse: Play satın almayı bitmemiş tutar, oyun bir sonraki açılışta tekrar gönderir,
   sunucu "zaten işlendi" der ve telefon bitirir. **Para kaybolmaz, iki kez sayılmaz.**
6. Bekleyen ödeme (nakit vb.) ödenince otomatik gelir. Sahte / iptal edilmiş belirteç reddedilir, hiçbir şey verilmez.
7. Parayla veya elmasla alınmış skinler sunucuda kayıtlı: yeni telefon / yeniden kurulum / hesap kurtarmada geri gelir.

### Yayından ÖNCE yapılması şart: hizmet hesabı (sunucunun Google'a sorabilmesi için)
Bu yapılmazsa sunucu satın almaları doğrulayamaz, oyuncu "Ödeme onaylanıyor..." görür ve **Google 3 gün içinde onaylanmayan
satın almayı iade eder.** Adımlar:
1. Google Cloud Console → Play Console'a bağlı projede **IAM → Hizmet hesapları → Hizmet hesabı oluştur**.
2. Hizmet hesabında **Anahtarlar → Anahtar ekle → JSON** (dosya iner; kimseyle paylaşma, git'e koyma).
3. Play Console → **Kullanıcılar ve izinler → Yeni kullanıcı davet et** → hizmet hesabının e-postası →
   uygulama izni: **"Finansal verileri görüntüle"** ve **"Siparişleri ve abonelikleri yönet"**.
4. Supabase → Project Settings → **Edge Functions → Secrets**: `GOOGLE_PLAY_SA_JSON` = JSON dosyasının **tamamı**.
   (Paket adı farklıysa `PLAY_PACKAGE`, varsayılan `com.hologame.holo`.)
5. İç test kanalında lisans test hesabıyla her paketi ve bir skini satın al; bakiye ve skin gelmeli, paket tekrar alınabilmeli.
* `WALLET_DEV_PURCHASES=1` yalnızca test sunucusu içindir (`dev_free_purchases` test sürümü "dev-" belirteçleri); canlıda **asla** açma.
* Play sürümünde `buildozer.spec` içindeki `android.gradle_dependencies` ve `android.add_src` satırlarını aç.

### Testler
`supabase/functions/scores/tests/` (Node 22: `node --experimental-strip-types tests/wallet_test.ts` vb.):
cüzdan kuralları, doğrulanmış satın alma (tekrar, bekleyen, sahte, başka hesap, Google kesintisi) ve gerçek RSA anahtarıyla
Google OAuth + Play API akışı (sahte Google sunucusuyla).

## Dürüst notlar
* `android_src/.../BillingBridge.java` gerçek Play Billing kütüphanesiyle **derlenmedi** (yalnızca API taslaklarıyla derleme
  denetiminden geçti). İlk iç test turunda küçük düzeltmeler gerekebilir.
* Sıralama etkilenmez (skorlar sunucuda yeniden oynatılır). Elmas ve satın alınan skinler artık sunucuda; diğer yerel ilerleme
  (bölümler, başarım sayaçları) hâlâ telefonda.
