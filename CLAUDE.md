# HOLO — proje rehberi

HOLO: İki Küre, Tek Nabız. Dikey ekranda tek dokunuşla oynanan refleks/ritim oyunu. Android (`com.hologame.holo`)
ve iOS'ta (App Store uygulama no. 6819440077) yayında. Oyuncu Türkçe konuşur; açıklamalar ve mesajlar Türkçe yazılır,
kod ve commit mesajları İngilizce kalır.

## Değişmez kurallar

1. **Oyun içi ekonomi sunucuda tutulur, cihazda değil.**
   - Elmas bakiyesi, hediyeler, ödüller ve harcamalar `players.diamonds` ve `wallet_log` üzerinden sunucuda yürür.
     Cihazdaki bakiye (`save_manager.set_server_balance`) sadece sunucunun söylediğini gösterir.
   - Her kazanç ve harcama `supabase/functions/scores/wallet.ts` içindeki sunucu tablosuyla fiyatlanır ya da sınırlanır.
     `(oyuncu, sebep, ref)` benzersizdir, bu yüzden tekrar gönderim çift sayılmaz.
   - Fiyat, ödül ve sınır değişince istemcideki sabiti (ör. `shop.py`) de değiştir, ama doğrunun kaynağı sunucudur.
     `tools/gen_wallet_data.py` ile `wallet_data.ts` yeniden üretilir.
   - İstemciden gelen bir sayıya ("şu kadar elmas ekle") asla güvenme. Sunucu kendi kuralıyla hesaplar ve günlük güvenlik sınırları koyar.
2. **Uygulama içi satın almalar sunucuda doğrulanır.**
   - **Google Play:** `play.ts` satın alma token'ını Google Play Developer API ile doğrular.
   - **App Store:** `apple.ts` işlemi App Store Server API ile doğrular; anahtar yoksa eski `verifyReceipt` kullanılır.
   - Doğrulanmayan, beklemede olan ya da başka hesaba ait (obfuscated account id uymayan) satın alma kredilendirilmez.
   - Her token `purchases.token_hash` ile tek kez işlenir.
   - `dev-` token'ları sadece sunucu açıkça izin verirse (`devPurchases()`) geçer; yayında kapalıdır.
3. **Bir işi "bitti" demeden önce test et ve kanıtını göster.**
   - Kanıt şunlardan biri olur: test çıktısı, ölçüm, ekran görüntüsü ya da önce/sonra karşılaştırması.
   - "Çalışıyor olmalı" yetmez. Test edilemeyen bir şey varsa bunu açıkça söyle.
   - Bölüm değişikliğinden sonra en az şunlar gösterilir:
     - 100 bölümün 3 yıldızla bittiği,
     - hata, boşluk ve kural denetimleri,
     - geliştiriciye önce/sonra önizleme resimleri.
   - **Derlemeden önce geliştiriciye sor.**

## Proje yapısı

| Yol | Görev |
|---|---|
| `main.py` | Giriş noktası (masaüstü ve Android) |
| `holo.py` | Oyun döngüsü, ekran durumları, kamera, sunum (`run`, `draw`, `_present`) |
| `sim.py` | **Deterministik** fizik (60 Hz). Oyun, çözücü ve sunucu aynı mantığı kullanır; `SIM_VERSION` |
| `level_manager.py` | Bölüm çizimi (statik katmanlar bir kez, hareketliler her karede) |
| `ui.py`, `theme.py`, `fonts.py`, `gfx.py`, `render_cache.py` | Arayüz, mağaza, modallar, önbellekli çizim |
| `save_manager.py` | Yerel kayıt (`save_data.json`); bakiye sunucudan gelir |
| `online.py` | Sunucu istemcisi (thread'li kuyruk, imzalı istekler, sıralama, cüzdan, hayalet, raporlar) |
| `shop.py`, `skin_catalog.py`, `skins.py` | Mağaza, skinler, günün indirimi |
| `ads.py`, `ads_ios.py` | AdMob (Android: `android_src/org/holo/ads`, iOS: rubicon köprüsü) |
| `storekit_ios.py` | iOS satın alma (StoreKit) |
| `endless.py`, `endless_view.py`, `arena.py` | Sonsuz mod ve arena modu |
| `olo.py`, `olo_lines*.py` | Maskot Olo (tepkiler, 4 dil) |
| `perfstat.py` | Gerçek telefonlardan kare süresi raporu (kind `perf`) |
| `locales.py` | Metinler: tr / en / de / es |
| `levels/level{1..100}.json` | Bölümler (`ref_taps` = doğrulanmış çözüm yolu) |
| `levelgen/` | Bölüm üretici, çözücü, zorluk araçları (`respeed.py`, `sector_fix.py`, `difficulty.py`, `passmodel.py`) |
| `levelgen/legacy_levels/` | Yayındaki eski sürümün bölümleri (sunucu eski oyunların koşularını bunlarla doğrular) |
| `supabase/functions/scores/` | Yayındaki sunucu (Deno/TypeScript Edge Function) |
| `supabase/schema.sql` | Veritabanı şeması |
| `server/` | Aynı protokolün eski Python sürümü (yerel test) |
| `android_src/` | Java köprüleri: Billing, Ads, Google Sign-In, bildirim (WorkManager) |
| `tools/` | Testler, dışa aktarma, mağaza (App Store Connect) ve ekran görüntüsü araçları |
| `.github/workflows/` | Android ve iOS derleme, mağaza otomasyonu |

## Teknolojiler

- **Oyun:** Python 3.11 (Android) / 3.13 (masaüstü), pygame 2.6.1
- **Android:** Buildozer + python-for-android, pyjnius, Google Play Billing 8, AdMob + UMP, Credential Manager (Google ile giriş), WorkManager
- **iOS:** pygame-ios + rubicon-objc, StoreKit, Google Mobile Ads; derleme GitHub Actions'ta macOS üzerinde
- **Sunucu:** Supabase Edge Function (Deno, TypeScript) + Supabase Postgres (proje `btpiblrrsjmhuacwkopr`, bölge ap-northeast-2)
- **CI:** GitHub Actions (repo `murselsaylan/holo-game`, herkese açık)

## Supabase tabloları

Tabloların hepsinde RLS açık ve politika yok. Erişim yalnızca Edge Function'ın servis bağlantısıyla yapılır.

| Tablo | İçerik |
|---|---|
| `players` | Oyuncu: `id`, `secret`, `name`, `country`, `levels`, `score`, `stars`, **`diamonds`** (sunucu bakiyesi), `gift`, `recovery`, `google`, `google_email`, `assist_revives_used`, `assist_shields_used` |
| `bests` | Oyuncu ve bölüm başına en iyi doğrulanmış koşu: `score`, `stars`, `time`, `swaps`, `rank`, `taps` (tekrar oynatma), `assists` |
| `wallet_log` | Her elmas hareketi: `delta`, `balance`, `reason` (ör. `ad`, `daily`, `spend:skin:x`, `endless_prize`), `ref`; `UNIQUE(player_id, reason, ref)` |
| `purchases` | Doğrulanmış satın almalar: `token_hash` (PK), `product`, `order_id`, `diamonds` |
| `endless_bests` | Sonsuz mod: hafta ve oyuncu başına en iyi tırmanış (`metres`, `taps`, `nonce`) |
| `saves` | Bulut kayıt kopyası (hesap kurtarma) |
| `reports` | Çökme, isim şikâyeti ve performans raporları (`kind`: `fault` / `crash` / `name` / `perf`) |

## Komutlar

```bash
# oyunu çalıştır (masaüstü)
python main.py

# bölüm/sim değiştiyse sunucu verisini yeniden üret
python tools/export_ts_data.py          # levels_data.ts + golden.json (+ LEGACY eski sürümler)
python tools/revive_golden.py           # revive_golden.json
python tools/endless_golden.py 120      # endless_golden.json (v4)
python tools/endless_golden.py --legacy 120   # endless_golden_v3.json (eski oyunlar)

# sunucu testleri (deno: pip paketi "deno"); tür denetimi kapalı çalıştırılır
cd supabase/functions/scores
for f in *_test.ts tests/*_test.ts; do deno run -A --no-check $f; done

# sunucuyu yayınla (Supabase CLI bu bilgisayarda giriş yapmış durumda)
npx --yes supabase@latest functions deploy scores --project-ref btpiblrrsjmhuacwkopr --no-verify-jwt --use-api

# istemci testleri ve ölçümler
python tools/smoke_test.py
python tools/ads_test.py
python tools/perf.py 10 61 98           # bölüm başına güncelleme / çizim süresi

# bölüm araçları
python levelgen/respeed.py 61,62        # dizilişi koruyup hıza göre yeniden zamanla ve doğrula
python levelgen/sector_fix.py           # sektör aralıkları raporu (--fix ile düzeltme)
python levelgen/difficulty.py           # zorluk puanları
```

### Derleme ve yayın

- **Android:**
  - Etiket yükle: `git tag android-vX.Y.Z-rN && git push origin android-vX.Y.Z-rN`. Etiketlenen commit'in mesajında `[skip ci]` **olmamalı**, yoksa derleme çalışmaz.
  - AAB `builds` dalına (`aab/holo-<sürüm>.aab`) ve Actions artifact'ına gelir.
  - `buildozer.spec` içindeki `android.numeric_version` Play'e yüklenen her pakette artmalıdır.
  - İmza anahtarı yalnızca GitHub secrets'tadır; anahtar ve şifre asla repoya ya da log'a girmez.
- **iOS:**
  - `ios-v*` etiketi derler ve TestFlight'a gönderir.
  - `store-v*` / `submit-v*` etiketleri mağaza sayfasını ve gönderimi yönetir.
  - `status-*` etiketi inceleme durumunu `ci-logs` dalına yazar.
  - Simülatör testi (`ios.yml`) sadece elle (`workflow_dispatch`) ya da `ios-test-*` etiketiyle çalışır; macOS dakikaları pahalıdır, bütçe sıfırdır.
- **Uyumluluk:** Sunucu, güncellenmemiş eski oyunları da kabul eder:
  - bölüm sürümüne göre `LEGACY` kullanır,
  - sonsuz modda v2/v3/v4,
  - canlandırmada `R`/`R2`/`R3`.
  
  Değişiklik yaparken eski istemcileri bozma; ilgili testler `tests/assist_test.ts`, `parity_endless_test.ts` ve `handler_test.ts`.

## Bölüm kuralları (geliştiricinin kararları)

- Var olan bölümlerin dizilişine sormadan dokunma; hız ve zorluk değişikliği `respeed.py` ile yapılır, diziliş korunur.
- Bir engel türü, orijinal oyunda ilk tanıtıldığı bölümden önce eklenmez. Örneğin dönen lazer en erken 61. bölümde kullanılır.
- Engeller düz duvar parçalarına konur; çıkıntı yanına, başlangıç ve bitişe 200 pikselden yakın yere konmaz.
- Boş bölüm olmaz: yol boyunca hiçbir şeyle karşılaşılmayan parça yaklaşık 600 pikseli geçmemeli (`sector_fix.emptiness`).
- Uzama/kısalma alanı engele (hareketli duvar, spinner, mayın, lazer) 100 px'ten yakın olmaz, başlangıç ve bitişe konmaz; takip eden duvarlı bölümlerde uzama alanı duvarın tetik çizgisinin hemen ilerisindedir; dar delik kapısının (kısalma gerektiren) önündeki kısalma alanı silinmez.
- Her bölüm çözülebilir olmalı: referans çözüm 3 yıldızla bitmeli (`tools/audit_new_levels.py`).
- Her değişiklikten sonra önce/sonra önizleme resimlerini göster ve onay al.
