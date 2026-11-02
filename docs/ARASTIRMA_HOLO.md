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
