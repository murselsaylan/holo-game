# Ödüllü reklamları açmak (AdMob)

Kod hazır ama kapalı. Açmak için:

1. **AdMob hesabı** aç (admob.google.com, Play geliştirici hesabındaki Google hesabıyla). Ödeme/vergi bilgilerini sen gir.
2. AdMob'da uygulamayı ekle (Google Play'den "HOLO", com.hologame.holo) → **Uygulama kimliği** `ca-app-pub-XXXX~YYYY`.
3. Bir **Ödüllü (Rewarded)** reklam birimi oluştur → **Reklam birimi kimliği** `ca-app-pub-XXXX/ZZZZ`.
4. Bu iki kimliği bana ver. Ben şunları yaparım:
   - `config.json` → `"admob_rewarded_id": "<reklam birimi kimliği>"`
   - `android_optional/org/holo/ads/RewardedBridge.java` → `android_src/org/holo/ads/`
   - `buildozer.spec` → `android.gradle_dependencies` sonuna `com.google.android.gms:play-services-ads:24.4.0`,
     `android.meta_data = com.google.android.gms.ads.APPLICATION_ID=<uygulama kimliği>`
     (bu satır olmadan SDK uygulamayı açılışta çökertir — o yüzden kimlikler gelmeden eklenmedi)
   - Mağazaya "reklam izle → +3 elmas" ve sonsuz modda "reklam izle → canlan" düğmeleri.
5. **Play Console**: Uygulama içeriği → *Reklamlar* → "Evet, reklam içeriyor"; *Veri güvenliği* formuna reklam kimliği
   (Advertising ID) ve AdMob'un topladığı verileri ekle; hedef kitlede 13 yaş altı varsa AdMob'da çocuklara uygun ayarları aç.
6. `app-ads.txt`: AdMob'un verdiği satırı geliştirici web sitesine koy (Play'deki web sitesi adresi).
