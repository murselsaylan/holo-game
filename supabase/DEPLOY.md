# Sıralama sunucusunu Supabase'e kurmak (tek ücretsiz platform)

Sunucu artık **TypeScript** (`supabase/functions/scores/`) ve Supabase **Edge Function** olarak çalışır; veriler aynı projenin **Postgres**'ine
yazılır. Ayrı bir sunucu (Render vb.) gerekmez, uyku/diski-silinme sorunu yoktur.
Skoru sunucuda yeniden oynatan fizik `sim.py`'nin birebir TypeScript karşılığıdır (`sim.ts`); 500 test oyununda Python ile aynı sonucu verir.

> Hesap açma/giriş adımları senin yapman gerekenlerdir. Ücretsiz plan koşulları değişebilir.

## 1) Proje
1. supabase.com → hesap → **New project** (bölge: sana yakın; bir **veritabanı parolası** belirle, not al).
2. **Project Settings → General → Reference ID** değerini kopyala (örn. `abcdefghijklmnop`).

## 2) Yükleme (bilgisayarında, oyun klasöründe; Node.js yüklü olmalı)
```bash
npx supabase login                                   # tarayıcı açılır, giriş yaparsın
npx supabase init                                    # soruları N ile geç (supabase/config.toml oluşur; functions klasörüne dokunmaz)
npx supabase link --project-ref REFERANS_KODU        # veritabanı parolasını sorar
npx supabase functions deploy scores --no-verify-jwt --use-api
```
`--no-verify-jwt` şarttır: oyun Supabase anahtarı taşımaz. Tablolar ilk istekte kendiliğinden oluşturulur ve herkese açık REST API'ye
kapatılır (RLS açık, politika yok); oyuncu sırları yalnızca fonksiyonla erişilebilir kalır.

## 3) Adres ve test
Adres: `https://REFERANS_KODU.supabase.co/functions/v1/scores` — tarayıcıda sonuna `/api/health` ekleyip aç: `{"ok":true,"sim":5,...}`.
```bash
.venv\Scripts\python.exe tools\check_server.py https://REFERANS_KODU.supabase.co/functions/v1/scores --full
```
Hepsi PASS ise `config.json` içindeki `"server_url"` alanına bu adresi yaz ve APK'yı yeniden derle.

## Bakım
* **Bölümleri ya da `sim.py`'yi değiştirdiysen:**
  ```bash
  .venv\Scripts\python.exe tools\export_ts_data.py       # levels_data.ts + golden.json yeniler
  node supabase/functions/scores/parity_test.ts          # sim.ts hâlâ sim.py ile aynı mı? (PARITY OK olmalı)
  npx supabase functions deploy scores --no-verify-jwt --use-api
  ```
  `sim.py` fiziği değiştiyse aynı değişikliği `sim.ts`'ye de yap; parity testi farkı yakalar.
* **Testler:** `node supabase/functions/scores/handler_test.ts` (rota + hile denemeleri, bellek içi veritabanıyla).
* **Sınırlar (Supabase ücretsiz):** istek başına 2 sn CPU (bir tekrar oynatma ~2–10 ms), ayda 500 bin çağrı; ücretsiz projeler
  bir hafta hiç etkinlik olmazsa duraklatılabilir — panelden **Restore** ile geri açılır.
* **Yedek:** Table Editor'dan `players` / `bests` dışa aktarılabilir; oyuncu sırları içerir, paylaşma.
* **Eski Python sunucusu** (`server/`) yerelde geliştirme/test için durur; aynı protokolü konuşur.
