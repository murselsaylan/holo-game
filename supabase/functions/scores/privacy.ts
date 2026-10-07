// Public pages served by the function itself (the OAuth consent screen and the Play listing link here):
//   GET .../scores/          -> a short page about the game
//   GET .../scores/privacy   -> the privacy policy
// Supabase serves function responses to browsers as plain text, so these pages are plain text.

export const HOME_TEXT = `HOLO - İki Küre, Tek Nabız
==========================

İki küreyi tek bir bağla döndürerek engellerden kaçtığın bir refleks oyunu.
Google Play: https://play.google.com/store/apps/details?id=com.hologame.holo

Gizlilik politikası: https://btpiblrrsjmhuacwkopr.supabase.co/functions/v1/scores/privacy
İletişim: murselsaylan5@gmail.com

HOLO - Two Orbs, One Pulse: a reflex game where you swing two orbs on one tether past obstacles.
Privacy policy: https://btpiblrrsjmhuacwkopr.supabase.co/functions/v1/scores/privacy
Contact: murselsaylan5@gmail.com
`;

export const PRIVACY_TEXT = `HOLO - GİZLİLİK POLİTİKASI
===========================
Son güncelleme: 8 Ekim 2026
Geliştirici: Mürsel Saylan - İletişim: murselsaylan5@gmail.com

HOLO, iki küreyi tek bir bağla döndürerek engellerden kaçtığın bir refleks oyunudur. Bu sayfa oyunun
sunucumuza hangi bilgileri gönderdiğini ve nelerin toplanmadığını açıklar.

1. TOPLADIĞIMIZ VERİLER
   - Takma ad ve ülke bayrağı (kendin seçersin; sıralamada görünür).
   - Rastgele oyuncu kimliği (cihazda üretilir, kimliğinle eşleşmez).
   - Bölüm ve sonsuz mod kayıtları: dokunuş zamanları, skor, yıldız, yükseklik. Sunucu bunları yeniden
     oynatarak skorların gerçekten oynanarak alındığını doğrular (hile önleme).
   - Oyun ilerlemesinin bir kopyası (hesap kurtarma için): bölümler, elmas bakiyesi, görünümler, ayarlar.
   - Google hesabı bağlama (isteğe bağlı): "Google'a bağla" dersen Google'ın doğruladığı hesap kimliğinin
     tek yönlü bir özeti (hash) ve e-posta adresinin kısaltılmış hali (ör. "mu***5@gmail.com") saklanır.
     Tam e-posta adresin ve Google şifren saklanmaz; şifreni oyun hiçbir zaman görmez.
   - Çökme raporları: oyun beklenmedik şekilde kapanırsa bir sonraki açılışta hata kaydı, oyunun o anki
     ekranı/bölümü, sürüm ve platform (Android/iOS) oyuncu kimliğinle birlikte gönderilir. Yalnızca hataları
     düzeltmek için kullanılır.

2. TOPLAMADIKLARIMIZ
   Ad soyad, tam e-posta adresi, telefon, konum, rehber, mikrofon/kamera, reklam kimliği,
   üçüncü taraf analiz veya reklam SDK'sı.

3. SATIN ALMALAR
   Uygulama içi satın almalar Google Play Faturalandırma (Android) ya da Apple App Store (iOS) ile işlenir. Kart veya ödeme bilgin bize
   hiçbir zaman ulaşmaz; yalnızca satın alma kaydı (ürün, sipariş kimliği) doğrulama için saklanır.

4. KULLANIM, SAKLAMA, PAYLAŞIM
   - Amaç: sıralamayı göstermek, skorları doğrulamak, hesabını kurtarmak, satın almaları teslim etmek.
   - Barındırma: Supabase (Postgres tabanlı sunucu).
   - Satış / paylaşım: yok. Veriler üçüncü kişilere satılmaz, paylaşılmaz, reklam için kullanılmaz.
   - Silme: murselsaylan5@gmail.com adresine oyuncu kimliğinle (oyunda Profil ekranında) yaz;
     tüm kayıtların silinir.

5. HESAP VE VERİ SİLME (HOLO)
   Hesabının ve verilerinin silinmesini istemek için:
   1) Oyunda Profil ekranını aç ve oyuncu kimliğini (Pilot ID) not al.
   2) murselsaylan5@gmail.com adresine "HOLO hesap silme" konulu bir e-posta gönder ve oyuncu kimliğini yaz.
      Hesabın bir Google hesabına bağlıysa o Google hesabından yazman yeterli.
   3) En geç 30 gün içinde silinir ve sana e-postayla bilgi verilir.
   Silinenler: takma ad, ülke, oyuncu kimliği, bölüm ve sonsuz mod kayıtları, sıralama satırları, ilerleme kopyası,
   elmas / yıldız bakiyesi, Google bağlantısı (hash ve kısaltılmış e-posta).
   Saklananlar: Google Play satın alma kayıtları (sipariş kimliği, ürün) muhasebe ve iade yükümlülükleri için
   en fazla 2 yıl saklanır, sonra silinir. Hesabı silmeden yalnızca bazı verilerin (ör. sıralama satırları veya
   Google bağlantısı) silinmesini de aynı yolla isteyebilirsin.

6. ÇOCUKLAR
   HOLO genel kitleye yöneliktir. Bilerek 13 yaş altı kullanıcılardan yukarıdakilerin dışında veri toplamayız.

7. DEĞİŞİKLİKLER
   Bu politika güncellenirse yeni sürüm bu adreste yayınlanır ve üstteki tarih değişir.


HOLO - PRIVACY POLICY (English)
===============================
Last updated: 8 October 2026 - Developer: Mürsel Saylan - Contact: murselsaylan5@gmail.com

What we collect: a nickname and country flag you choose; a random player id made on the device; your level and
endless-mode runs (tap times, score, stars, height), which the server replays to verify scores; a copy of your
game progress for account recovery; and, only if you link a Google account, a one-way hash of the Google account
id and a shortened form of its email address (e.g. "mu***5@gmail.com"). Your full email and your Google password
are never stored - the game never sees your password. If the game closes unexpectedly, the next start sends a crash
report (error log, the screen / level at that moment, version, platform) with your player id - used only to fix bugs.
What we do not collect: real name, full email, phone, location, contacts, microphone/camera, advertising id,
third-party analytics or ad SDKs.
Purchases are processed by Google Play Billing (Android) or the Apple App Store (iOS); payment details never reach us.
Data is hosted on Supabase, is never sold or shared, and is not used for advertising.
Account and data deletion (HOLO): email murselsaylan5@gmail.com with the subject "HOLO account deletion" and your
player id (Profile screen) - or write from the Google account linked to it. Within 30 days your nickname, country,
player id, level and endless runs, leaderboard rows, progress copy, diamond / star balance and Google link are
deleted. Google Play purchase records (order id, product) are kept for up to 2 years for accounting and refunds.
You can also ask for only part of your data (e.g. leaderboard rows or the Google link) to be deleted.
`;
