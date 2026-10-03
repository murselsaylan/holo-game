"""Achievements: purely local (no server needed). Progress comes from save stats and event counters."""
import locales

# id, source, target, (tr title, tr description), (en title, en description)
# source: "stat:levels" (highest cleared), "stat:stars", "stat:srank", or a counter name.
ACHIEVEMENTS = [
    ("first_orbit", "stat:levels", 1, ("İlk Yörünge", "1. bölümü bitir"), ("First Orbit", "Clear level 1")),
    ("rookie", "stat:levels", 10, ("Çaylak Pilot", "10. bölüme ulaş"), ("Rookie Pilot", "Clear level 10")),
    ("void_walker", "stat:levels", 25, ("Boşluk Gezgini", "25. bölüme ulaş"), ("Void Walker", "Clear level 25")),
    ("quantum", "stat:levels", 50, ("Kuantum Ustası", "50. bölüme ulaş"), ("Quantum Master", "Clear level 50")),
    ("omega", "stat:levels", 75, ("Omega Yolcusu", "75. bölüme ulaş"), ("Omega Traveller", "Clear level 75")),
    ("cosmic", "stat:levels", 100, ("Kozmik Zirve", "100. bölümü bitir"), ("Cosmic Apex", "Clear level 100")),
    ("stars_25", "stat:stars", 25, ("Yıldız Avcısı", "Toplam 25 yıldız topla"), ("Star Hunter", "Collect 25 stars")),
    ("stars_100", "stat:stars", 100, ("Yıldız Tozu", "Toplam 100 yıldız topla"), ("Stardust", "Collect 100 stars")),
    ("stars_250", "stat:stars", 250, ("Takımyıldızı", "Toplam 250 yıldız topla"), ("Constellation", "Collect 250 stars")),
    ("smasher", "smash", 10, ("Duvar Kırıcı", "10 çatlak duvar kır"), ("Wall Smasher", "Smash 10 cracked walls")),
    ("aegis", "shield_pop", 10, ("Aegis Kalkanı", "Kalkanla 10 kez kurtul veya bariyer geç"), ("Aegis", "Use the shield 10 times")),
    ("tiny", "shrink", 15, ("Minik Pilot", "15 kez küçül"), ("Tiny Pilot", "Shrink 15 times")),
    ("heavy", "grow", 15, ("Ağır Sıklet", "15 kez büyü"), ("Heavyweight", "Grow 15 times")),
    ("warp", "boost", 40, ("Warp Sürücü", "40 hızlandırıcıya dokun"), ("Warp Drive", "Touch 40 boost pads")),
    ("runner", "chase", 8, ("Kaçış Ustası", "8 kovalayan duvardan kaç"), ("Escape Artist", "Trigger 8 chaser walls")),
    ("grazer", "graze", 100, ("Sıyırıcı", "100 kez duvarı sıyır"), ("Grazer", "Graze walls 100 times")),
    ("combo4", "combo4", 1, ("Ritim Kralı", "x4 ritim çarpanına ulaş"), ("Rhythm King", "Reach a x4 combo")),
    ("s_rank", "stat:srank", 1, ("Kusursuz", "Bir bölümde S+ derece al"), ("Flawless", "Get an S+ rank")),
    ("never_quit", "deaths", 100, ("Pes Etmem", "100 kez yeniden dene"), ("Never Quit", "Try again 100 times")),
    # 1.0.6: mastery
    ("three_star_10", "stat:three_star", 10, ("Üçlü Yıldız", "10 bölümü 3 yıldızla bitir"), ("Triple Star", "3-star 10 levels")),
    ("three_star_30", "stat:three_star", 30, ("Yıldız Koleksiyonu", "30 bölümü 3 yıldızla bitir"), ("Star Collection", "3-star 30 levels")),
    ("three_star_60", "stat:three_star", 60, ("Yıldızların Efendisi", "60 bölümü 3 yıldızla bitir"), ("Lord of Stars", "3-star 60 levels")),
    ("srank_10", "stat:srank", 10, ("Kusursuz Seri", "10 bölümde S+ al"), ("Flawless Run", "Get S+ on 10 levels")),
    ("comeback", "revive", 1, ("Geri Dönüş", "Bir kez canlan ve devam et"), ("Comeback", "Revive once and carry on")),
    # 1.0.6: endless climb
    ("climb_100", "stat:endless_m", 100, ("Tırmanışçı", "Sonsuz modda 100 m'ye çık"), ("Climber", "Reach 100 m in the endless climb")),
    ("climb_500", "stat:endless_m", 500, ("Bulutların Üstü", "Sonsuz modda 500 m'ye çık"), ("Above the Clouds", "Reach 500 m in the endless climb")),
    ("climb_1000", "stat:endless_m", 1000, ("Yörünge Kaçışı", "Sonsuz modda 1000 m'ye çık"), ("Escape Velocity", "Reach 1000 m in the endless climb")),
    ("endless_stars_100", "stat:endless_stars", 100, ("Yıldız Toplayıcı", "Sonsuz modda 100 yıldız topla"), ("Star Gatherer", "Collect 100 endless stars")),
    ("endless_stars_500", "stat:endless_stars", 500, ("Galaksi Hazinesi", "Sonsuz modda 500 yıldız topla"), ("Galaxy Hoard", "Collect 500 endless stars")),
    ("star_streak", "star_streak5", 1, ("Yıldız Fırtınası", "Sonsuz modda x5 yıldız serisi yap"), ("Star Storm", "Make a x5 star streak")),
    ("endless_25", "endless_runs", 25, ("Durmak Yok", "25 sonsuz tırmanış yap"), ("No Stopping", "Play 25 endless climbs")),
    # 1.0.6: collection and loyalty
    ("collector_10", "stat:skins", 10, ("Koleksiyoncu", "10 skine sahip ol"), ("Collector", "Own 10 skins")),
    ("collector_25", "stat:skins", 25, ("Büyük Koleksiyon", "25 skine sahip ol"), ("Grand Collection", "Own 25 skins")),
    ("loyal_7", "stat:login_best", 7, ("Sadık Pilot", "7 gün üst üste giriş yap"), ("Loyal Pilot", "Log in 7 days in a row")),
    ("loyal_30", "stat:login_days", 30, ("Gezegen Sakini", "30 gün giriş yap"), ("Resident", "Log in on 30 days")),
    ("daily_10", "daily_done", 10, ("Görev Adamı", "10 günlük görev tamamla"), ("On Duty", "Complete 10 daily missions")),
]
BY_ID = {a[0]: a for a in ACHIEVEMENTS}


def title(a):
    return a[3][0] if locales.get_language() == "tr" else a[4][0]


def desc(a):
    return a[3][1] if locales.get_language() == "tr" else a[4][1]


def counters(save):
    return save.data.setdefault("counters", {})


def bump(save, key, n=1):
    c = counters(save)
    c[key] = int(c.get(key, 0)) + n


def value(save, source):
    if source == "stat:levels":
        return save.highest_cleared
    if source == "stat:stars":
        return save.get_total_stars()
    if source == "stat:srank":
        return sum(1 for s in save.stats.values() if s.get("rank") == "S+")
    if source == "stat:three_star":
        return sum(1 for s in save.stats.values() if s.get("stars", 0) >= 3)
    if source == "stat:endless_m":
        return int(save.data.get("endless", {}).get("best_m", 0))
    if source == "stat:endless_stars":
        return int(save.data.get("star_coins_total", 0))
    if source == "stat:skins":
        return len(save.data.get("unlocked_skins", []))
    if source == "stat:login_best":
        return int(save.data.get("login", {}).get("best", 0))
    if source == "stat:login_days":
        return int(save.data.get("login", {}).get("days", 0))
    return int(counters(save).get(source, 0))


def progress(save, a):
    return min(a[2], value(save, a[1])), a[2]


def unlocked_ids(save):
    return save.data.setdefault("achievements", [])


def check(save):
    """Return the achievements that became complete since the last call (and remember them)."""
    got = unlocked_ids(save)
    fresh = []
    for a in ACHIEVEMENTS:
        if a[0] not in got and value(save, a[1]) >= a[2]:
            got.append(a[0])
            fresh.append(a)
    if fresh:
        save.save()
    return fresh
