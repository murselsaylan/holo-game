# Sıralama sunucusunu ücretsiz yayınlamak (Render + Neon)

İki ücretsiz parça birlikte çalışır:

* **Render** (ücretsiz web servisi): sunucu kodunu çalıştırır, `https://....onrender.com` adresi ve HTTPS verir.
  15 dk boşta kalınca uyur, ilk istekte ~1 dk'da uyanır. Diski geçicidir (her yeniden başlatmada silinir).
* **Neon** (ücretsiz Postgres): skorları **kalıcı** tutar, bu yüzden Render'ın geçici diski sorun olmaz.

> Hesap açmak/giriş yapmak senin yapman gereken kısımlar. Ücretsiz planların koşulları değişebilir; Render bir ödeme yöntemi isterse
> ücretsiz servis onsuz askıya alınabilir (Render belgesi), o durumda sorun olarak bana yaz.

## 1) Kodu GitHub'a koy
Depoda gizli dosya olmamalı: `.gitignore` zaten `save_data*.json` (oyuncu sırrın), `*.db`, `.venv` vb. dosyaları dışarıda bırakır.
```bash
git init
git add .
git status          # save_data.json ve .venv görünmemeli!
git commit -m "HOLO"
git branch -M main
git remote add origin https://github.com/KULLANICI/holo.git
git push -u origin main
```
(Zaten bir GitHub deposu varsa yalnızca yeni dosyaları — `render.yaml`, `requirements-server.txt`, `server/` — commit edip push et.)

## 2) Neon'da veritabanı
1. neon.com → ücretsiz hesap → **Create project**.
2. **Connection string**'i kopyala: `postgresql://kullanici:parola@ep-....neon.tech/neondb?sslmode=require`
   Bu parola gizlidir; yalnızca Render'a yapıştıracaksın, GitHub'a ya da bana yazma.

### Neon yerine Supabase (olur)
Supabase'in **Postgres**'ü aynı işi görür; sunucu koduna dokunmaya gerek yok. (Supabase'in *Edge Function*'ları TypeScript/Deno'dur; skoru
Python'da yeniden oynatan doğrulama orada çalışmaz, o yüzden sunucu yine Render'da kalır.)
1. supabase.com → **New project** (bölgeyi yakın seç, veritabanı parolası belirle).
2. Üstteki **Connect** → **Session pooler** → URI'yi kopyala: `postgresql://postgres.PROJEKODU:[PAROLA]@aws-0-....pooler.supabase.com:5432/postgres`
   * **Doğrudan bağlantıyı (db.xxx.supabase.co) kullanma:** yalnızca IPv6'dır, Render'dan bağlanamayabilir. *Session pooler* IPv4'tür.
   * *Transaction pooler* (port 6543) yerine **Session pooler** (port 5432) kullan.
   * Parolada `@ : / #` gibi özel karakter varsa `%40 %3A %2F %23` olarak kodla ya da parolayı harf/rakamdan seç.
3. Bu dizeyi Render'da `DATABASE_URL` olarak kullan.
* **Dikkat:** ücretsiz Supabase projesi **1 hafta hiç etkinlik olmazsa duraklatılır**; panelden **Restore** ile geri açman gerekir.
  Oyuncu az/hiç yoksa Neon bu açıdan daha rahattır.

## 3) Render'da servis
1. render.com → giriş → **New → Blueprint** → GitHub deposunu seç (`render.yaml` otomatik okunur).
2. `DATABASE_URL` istenince Neon bağlantı dizesini yapıştır. **Apply / Deploy**.
3. Bitince servis adresi görünür, örn. `https://holo-scores.onrender.com`. Tarayıcıda `/api/health` aç → `{"ok": true, ...}`.

## 4) Test ve oyuna bağlama
```bash
.venv\Scripts\python.exe tools\check_server.py https://holo-scores.onrender.com --full
```
Hepsi PASS ise `config.json` içindeki `"server_url"` alanına adresi yaz ve APK'yı yeniden derle. (Adresi bana yazarsan bunu ben yaparım.)

## Bilmen gerekenler
* **İlk açılış yavaş:** uyuyan servis ilk istekte ~1 dk'da uyanır. Oyun açılışta sunucuyu uyandırır, gönderimler başarısız olursa
  kuyrukta bekleyip sonra otomatik tekrar denenir.
* **Skor doğrulama yavaş olabilir:** ücretsiz Render 0.1 CPU verir; uzun bölümlerin tekrar oynatılması birkaç saniye sürebilir
  (istemci 90 sn bekler).
* **Bölümleri yeniden ürettiysen** `levels/` ve `sim.py` değişikliklerini push et; Render otomatik yeniden dağıtır. Aksi halde sunucu
  eski bölümle doğrular ve yeni istemcinin gönderimlerini "level version mismatch" ile reddeder.
* **Yedek:** Neon panelinden veritabanını dışa aktarabilirsin. Veritabanı oyuncu sırlarını içerir, paylaşma.
