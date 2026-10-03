"""Seasonal events (1.0.6): a few weeks with their own name, colour and reward track.

While an event runs, every star collected in the endless climb also counts as event points; reaching each tier of
the track pays diamonds (and the last one a pile of stars for the Yıldız Avcısı skins). The menu shows a banner for the
running event; the missions screen shows its track. The server pays a tier once, only for an event that is running
(or ended less than three days ago) - supabase/functions/scores/wallet.ts earnClaim "event" (tools/gen_wallet_data.py).
"""
import datetime

# id, (tr name, en name), start, end (inclusive), colour, [(points, diamonds, stars), ...]
EVENTS = [
    ("autumn26", ("Kozmik Sonbahar", "Cosmic Autumn"), "2026-10-01", "2026-10-31", (255, 140, 60),
     [(50, 30, 0), (150, 60, 0), (300, 100, 0), (600, 150, 50)]),
    ("frost26", ("Buzul Gecesi", "Frost Night"), "2026-11-15", "2026-12-15", (120, 210, 255),
     [(50, 30, 0), (150, 60, 0), (300, 100, 0), (600, 150, 50)]),
    ("newyear27", ("Yeni Yıl Yıldızları", "New Year Stars"), "2026-12-20", "2027-01-15", (255, 215, 90),
     [(60, 40, 0), (180, 70, 0), (360, 110, 0), (720, 180, 60)]),
]


def _d(s):
    y, m, d = (int(x) for x in s.split("-"))
    return datetime.date(y, m, d)


def current(today=None):
    """The running event (dict) or None."""
    today = today or datetime.date.today()
    for eid, names, start, end, col, tiers in EVENTS:
        if _d(start) <= today <= _d(end):
            return {"id": eid, "names": names, "start": start, "end": end, "color": col, "tiers": tiers,
                    "days_left": (_d(end) - today).days + 1}
    return None


def name(ev, lang):
    return ev["names"][0] if lang == "tr" else ev["names"][1]


def state(save):
    """This device's progress in the running event: {"id", "points", "claimed": [tier indices]}."""
    ev = current()
    st = save.data.setdefault("event", {"id": "", "points": 0, "claimed": []})
    if ev and st.get("id") != ev["id"]:
        st.update(id=ev["id"], points=0, claimed=[])
    return ev, st


def add_points(save, n):
    ev, st = state(save)
    if ev and n > 0:
        st["points"] = int(st.get("points", 0)) + int(n)
        save.save()


def claimable(save):
    ev, st = state(save)
    if not ev:
        return []
    return [i for i, (pts, _g, _s) in enumerate(ev["tiers"]) if st["points"] >= pts and i not in st["claimed"]]


def claim(save, i):
    ev, st = state(save)
    if not ev or i in st["claimed"] or st["points"] < ev["tiers"][i][0]:
        return None
    pts, gems, stars = ev["tiers"][i]
    st["claimed"].append(i)
    save.earn("event", f"{ev['id']}_{i}", gems)
    if stars:
        save.add_star_coins(stars)
    save.save()
    return gems, stars
