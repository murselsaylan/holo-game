"""Procedural music + extra sound effects (pure Python, no dependencies). Files are generated once into assets/audio and
shipped with the app:  python audio_tracks.py   (re-generates everything)

Music: one loop per place -- a music-box lullaby for the menus and a distinct track for each of the five sectors, getting
faster and denser as the campaign goes on.  Sound effects: cracked-wall smash, chaser siren, effect-over sweep, purchase chime.
"""
import math
import os
import random
import struct
import wave

import paths

SR = 22050
AUDIO_DIR = paths.asset("audio")


def _clamp(v):
    return -32767 if v < -32767 else (32767 if v > 32767 else int(v))


def write_wav(name, samples, rate=SR):
    os.makedirs(AUDIO_DIR, exist_ok=True)
    path = os.path.join(AUDIO_DIR, name)
    with wave.open(path, "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(struct.pack(f"<{len(samples)}h", *[_clamp(s) for s in samples]))
    return path


def mtof(m):
    return 440.0 * 2.0 ** ((m - 69) / 12.0)


def _wave(kind, ph):
    """One oscillator sample for phase `ph` (radians)."""
    if kind == "sine":
        return math.sin(ph)
    if kind == "tri":
        x = (ph / (2 * math.pi)) % 1.0
        return 4.0 * abs(x - 0.5) - 1.0
    if kind == "square":
        return 0.55 * math.sin(ph) + 0.3 * (1.0 if math.sin(ph) > 0 else -1.0)
    if kind == "saw":
        x = (ph / (2 * math.pi)) % 1.0
        return 0.5 * (2.0 * x - 1.0) + 0.35 * math.sin(ph)
    if kind == "bell":
        return math.sin(ph + 1.6 * math.sin(ph * 2.0)) * 0.7 + math.sin(ph * 3.01) * 0.12
    return math.sin(ph)


def note(buf, start, dur, freq, amp, kind="sine", attack=0.006, curve=2.0, vib=0.0):
    i0 = int(start * SR)
    n = int(dur * SR)
    if n <= 0:
        return
    end = min(len(buf), i0 + n)
    w = 2 * math.pi * freq / SR
    att = max(1, int(attack * SR))
    for j in range(0, end - i0):
        prog = j / n
        env = (1.0 - prog) ** curve
        if j < att:
            env *= j / att
        f = w * j
        if vib:
            f += vib * math.sin(j * 0.0009)
        buf[i0 + j] += _wave(kind, f) * env * amp


def pad(buf, start, dur, freqs, amp):
    i0 = int(start * SR)
    n = int(dur * SR)
    end = min(len(buf), i0 + n)
    ws = [2 * math.pi * f / SR for f in freqs]
    for j in range(0, end - i0):
        prog = j / n
        env = math.sin(min(1.0, prog * 6.0) * math.pi / 2.0) * (1.0 - prog) ** 0.6
        v = 0.0
        for k, w in enumerate(ws):
            v += math.sin(w * j) + 0.5 * math.sin(w * j * 1.004 + k)
        buf[i0 + j] += v * env * amp / max(1, len(ws))


def kick(buf, start, amp=9000):
    i0 = int(start * SR)
    n = int(0.16 * SR)
    for j in range(min(n, len(buf) - i0)):
        p = j / n
        f = max(38.0, 165.0 * (1 - p * 0.92))
        buf[i0 + j] += math.sin(2 * math.pi * f * j / SR) * (1 - p) ** 3 * amp


def snare(buf, start, rng, amp=3800):
    i0 = int(start * SR)
    n = int(0.17 * SR)
    for j in range(min(n, len(buf) - i0)):
        p = j / n
        buf[i0 + j] += ((rng.random() * 2 - 1) * amp + math.sin(2 * math.pi * 190 * j / SR) * amp * 0.7) * (1 - p) ** 2.4


def hat(buf, start, rng, amp=1500, length=0.045):
    i0 = int(start * SR)
    n = int(length * SR)
    for j in range(min(n, len(buf) - i0)):
        buf[i0 + j] += (rng.random() * 2 - 1) * amp * (1 - j / n) ** 4


def chord_tones(root, q):
    third = {"m": 3, "M": 4, "d": 3}[q]
    fifth = 6 if q == "d" else 7
    return [root, root + third, root + fifth, root + 12]


def build(spec, seed):
    rng = random.Random(seed)
    beat = 60.0 / spec["bpm"]
    bars = spec["bars"]
    total = bars * 4 * beat
    buf = [0.0] * int(total * SR)
    chords = spec["chords"]
    step16 = beat / 4.0
    for bar in range(bars):
        root, q = chords[bar % len(chords)]
        tones = chord_tones(root, q)
        t0 = bar * 4 * beat
        if spec.get("pad"):
            pad(buf, t0, 4 * beat, [mtof(m + 12) for m in tones[:3]], spec["pad"])
        for s in range(16):
            ts = t0 + s * step16
            c = spec["bass"][s]
            if c in "xo":
                note(buf, ts, step16 * 0.9, mtof(root - 12 + (12 if c == "o" else 0)), spec["bass_amp"], spec.get("bass_kind", "saw"), curve=1.6)
            if spec.get("kick") and spec["kick"][s] == "x":
                kick(buf, ts, spec.get("kick_amp", 9000))
            if spec.get("snare") and spec["snare"][s] == "x":
                snare(buf, ts, rng, spec.get("snare_amp", 3800))
            if spec.get("hat") and spec["hat"][s] == "x":
                hat(buf, ts, rng, spec.get("hat_amp", 1500))
        arp = spec["arp"]
        step = beat / (2.0 if spec.get("arp_rate", 8) == 8 else 4.0)
        count = 8 if spec.get("arp_rate", 8) == 8 else 16
        for s in range(count):
            m = tones[arp[s % len(arp)]] + spec.get("arp_oct", 12)
            note(buf, t0 + s * step, step * 0.95, mtof(m), spec["arp_amp"], spec.get("arp_kind", "square"), curve=spec.get("arp_curve", 1.2))
        if spec.get("lead"):
            for b in range(4):
                if rng.random() < spec["lead"]:
                    m = tones[rng.randrange(0, 4)] + 24
                    note(buf, t0 + b * beat, beat * 1.6, mtof(m), spec["arp_amp"] * 0.85, "tri", attack=0.02, curve=1.0, vib=1.2)
    peak = max(1.0, max(abs(v) for v in buf))
    gain = 26000.0 / peak
    out = [v * gain for v in buf]
    fade = int(0.02 * SR)
    for k in range(fade):                                  # click-free loop point
        out[k] *= k / fade
        out[-1 - k] *= k / fade
    return out


SPECS = {
    # calm music-box lullaby for the menus
    "bgm_menu": dict(bpm=84, bars=8, chords=[(60, "M"), (57, "m"), (65, "M"), (67, "M")], pad=2600, bass="x.......x.......",
                     bass_amp=2200, bass_kind="tri", hat="................", arp=[0, 2, 1, 3, 2, 3, 1, 2], arp_kind="bell",
                     arp_amp=3000, arp_curve=2.2, arp_oct=12),
    # sector 1 keeps the original synthwave loop (bgm_synthwave.wav)
    "bgm_s2": dict(bpm=126, bars=8, chords=[(50, "m"), (46, "M"), (53, "M"), (48, "M")], pad=1800, bass="xxoxxxoxxxoxxxox", bass_amp=3600,
                   kick="x...x...x...x...", snare="....x.......x...", hat="x.x.x.x.x.x.x.x.", arp=[0, 1, 2, 3, 2, 1, 2, 3],
                   arp_amp=2900, arp_kind="square", lead=0.5),
    "bgm_s3": dict(bpm=132, bars=8, chords=[(54, "m"), (50, "M"), (57, "M"), (52, "m")], pad=1700, bass="x..x..x...x..x..", bass_amp=3800,
                   bass_kind="tri", kick="x..x..x...x...x.", snare="....x.......x..x", hat="x.xxx.xxx.xxx.x.", arp=[0, 2, 1, 3, 2, 1, 3, 2],
                   arp_rate=16, arp_amp=2500, arp_kind="bell", arp_curve=2.0, lead=0.6),
    "bgm_s4": dict(bpm=138, bars=8, chords=[(52, "m"), (53, "M"), (52, "m"), (58, "d")], pad=2000, bass="xxxxxxxxxxxxxxxx", bass_amp=3300,
                   kick="x.x.x.x.x.xxx.x.", snare="x..x..x.x..x..x.", hat="xxxxxxxxxxxxxxxx", hat_amp=1100,
                   arp=[0, 3, 1, 3, 2, 3, 1, 3], arp_amp=2700, arp_kind="saw", lead=0.7),
    "bgm_s5": dict(bpm=146, bars=8, chords=[(45, "m"), (41, "M"), (48, "M"), (43, "M"), (45, "m"), (41, "M"), (43, "M"), (40, "M")],
                   pad=2200, bass="xoxoxoxoxoxoxoxo", bass_amp=3900, kick="x...x...x...x.xx", snare="....x.......x.x.", hat="x.xxx.xxx.xxx.xx",
                   arp=[0, 1, 2, 3, 3, 2, 1, 0, 0, 2, 1, 3, 3, 1, 2, 0], arp_rate=16, arp_amp=2500, arp_kind="square", arp_oct=12, lead=0.9,
                   kick_amp=10500),
    # Fast adrenaline variants triggered during late-stage tension
    "bgm_s2_fast": dict(bpm=152, bars=8, chords=[(50, "m"), (46, "M"), (53, "M"), (48, "M")], pad=1600, bass="xxoxxxoxxxoxxxox", bass_amp=3800,
                        kick="x.x.x.x.x.x.x.x.", snare="....x.......x...", hat="xxxxxxxxxxxxxxxx", arp=[0, 1, 2, 3, 2, 1, 2, 3],
                        arp_amp=3200, arp_kind="saw", lead=0.6),
    "bgm_s3_fast": dict(bpm=158, bars=8, chords=[(54, "m"), (50, "M"), (57, "M"), (52, "m")], pad=1500, bass="xxxxxxxxxxxxxxxx", bass_amp=4000,
                        bass_kind="saw", kick="x..x..x.x.x.x.x.", snare="....x...x...x..x", hat="xxxxxxxxxxxxxxxx", arp=[0, 2, 1, 3, 2, 1, 3, 2],
                        arp_rate=16, arp_amp=2800, arp_kind="bell", arp_curve=1.8, lead=0.7),
    "bgm_s4_fast": dict(bpm=165, bars=8, chords=[(52, "m"), (53, "M"), (52, "m"), (58, "d")], pad=1800, bass="xxxxxxxxxxxxxxxx", bass_amp=3600,
                        kick="x.x.x.x.xxxxxx.x", snare="x..x..xxxx..xx.x", hat="xxxxxxxxxxxxxxxx", hat_amp=1300,
                        arp=[0, 3, 1, 3, 2, 3, 1, 3], arp_amp=3000, arp_kind="saw", lead=0.8),
    "bgm_s5_fast": dict(bpm=175, bars=8, chords=[(45, "m"), (41, "M"), (48, "M"), (43, "M"), (45, "m"), (41, "M"), (43, "M"), (40, "M")],
                        pad=2000, bass="xxxxxxxxxxxxxxxx", bass_amp=4200, kick="x.xxx.xxx.xxx.xx", snare="..x...x...x.x.x.", hat="xxxxxxxxxxxxxxxx",
                        arp=[0, 1, 2, 3, 3, 2, 1, 0, 0, 2, 1, 3, 3, 1, 2, 0], arp_rate=16, arp_amp=2800, arp_kind="saw", arp_oct=12, lead=1.0,
                        kick_amp=11500),
}


def generate_music(names=None):
    for i, (name, spec) in enumerate(SPECS.items()):
        if names and name not in names:
            continue
        write_wav(name + ".wav", build(spec, 100 + i))


# ---------------------------------------------------------------------------------------------- extra sound effects
def sfx_smash():
    rng = random.Random(7)
    n = int(0.42 * SR)
    out = []
    for j in range(n):
        p = j / n
        noise = (rng.random() * 2 - 1) * (1 - p) ** 2.2
        thump = math.sin(2 * math.pi * (110 - 70 * p) * j / SR) * (1 - p) ** 1.6
        crack = (rng.random() * 2 - 1) * (1.0 if (j % 900) < 40 and p < 0.5 else 0.0) * 0.6
        out.append((noise * 0.55 + thump * 0.9 + crack) * 22000)
    return write_wav("sfx_smash.wav", out)


def sfx_chase():
    n = int(0.75 * SR)
    out = []
    for j in range(n):
        p = j / n
        f = 560.0 if int(p * 6) % 2 == 0 else 420.0
        env = min(1.0, p * 8) * (1 - p) ** 0.7
        v = (1.0 if math.sin(2 * math.pi * f * j / SR) > 0 else -1.0) * 0.45 + math.sin(2 * math.pi * f * j / SR) * 0.5
        out.append(v * env * 16000)
    return write_wav("sfx_chase.wav", out)


def sfx_fxend():
    n = int(0.28 * SR)
    out = []
    for j in range(n):
        p = j / n
        f = 900 - 620 * p
        out.append(math.sin(2 * math.pi * f * j / SR) * (1 - p) ** 1.5 * 15000)
    return write_wav("sfx_fxend.wav", out)


def sfx_bounce():
    n = int(0.3 * SR)
    out = []
    for j in range(n):
        p = j / n
        f = 220.0 + 620.0 * math.sin(min(1.0, p * 2.2) * math.pi / 2.0) - 380.0 * max(0.0, p - 0.4)
        env = (1 - p) ** 1.8 * min(1.0, j / 60.0)
        out.append((math.sin(2 * math.pi * f * j / SR) * 0.75 + math.sin(4 * math.pi * f * j / SR) * 0.25) * env * 19000)
    return write_wav("sfx_bounce.wav", out)


def sfx_coin():
    buf = [0.0] * int(0.6 * SR)
    for k, m in enumerate((84, 88, 91, 96)):
        note(buf, k * 0.07, 0.3, mtof(m), 8000, "bell", curve=2.5)
    return write_wav("sfx_coin.wav", buf)


def sfx_tension_rise():
    n = int(0.9 * SR)
    out = []
    rng = random.Random(42)
    for j in range(n):
        p = j / n
        freq = 180.0 * (4.2 ** p)
        pulse = 0.6 + 0.4 * math.sin(2 * math.pi * (4.0 + 8.0 * p) * (j / SR))
        sine = math.sin(2 * math.pi * freq * (j / SR))
        saw = 2.0 * ((freq * (j / SR)) % 1.0) - 1.0
        tone = (sine * 0.7 + saw * 0.3) * pulse
        noise = (rng.random() * 2 - 1) * (p ** 1.8) * 0.4
        env = (math.sin(p * math.pi * 0.5) ** 1.5) * (1.0 - 0.2 * p)
        val = (tone * 0.75 + noise * 0.25) * env * 24000
        out.append(val)
    return write_wav("sfx_tension_rise.wav", out)


def sfx_tick():
    n = int(0.038 * SR)
    rng = random.Random(1337)
    out = []
    for j in range(n):
        p = j / n
        env = (1.0 - p) ** 3.5
        noise = (rng.random() * 2 - 1) * 0.75
        metal = math.sin(2 * math.pi * 5800 * j / SR) * 0.25
        val = int((noise + metal) * env * 18000)
        out.append(max(-32767, min(32767, val)))
    return write_wav("sfx_tick.wav", out)


EXTRA_SFX = {
    "sfx_bounce.wav": sfx_bounce,
    "sfx_smash.wav": sfx_smash,
    "sfx_chase.wav": sfx_chase,
    "sfx_fxend.wav": sfx_fxend,
    "sfx_coin.wav": sfx_coin,
    "sfx_tension_rise.wav": sfx_tension_rise,
    "sfx_tick.wav": sfx_tick,
}
MUSIC_FILES = [n + ".wav" for n in SPECS]


def ensure_all():
    """Create any missing file (used at start-up on desktop; on Android the shipped files are used as they are)."""
    for name, fn in EXTRA_SFX.items():
        if not os.path.exists(os.path.join(AUDIO_DIR, name)):
            try:
                fn()
            except Exception as e:
                print("audio:", name, e)
    for name, spec in SPECS.items():
        if not os.path.exists(os.path.join(AUDIO_DIR, name + ".wav")):
            try:
                write_wav(name + ".wav", build(spec, 100 + list(SPECS).index(name)))
            except Exception as e:
                print("audio:", name, e)


if __name__ == "__main__":
    import time
    t0 = time.time()
    for fn in EXTRA_SFX.values():
        fn()
    generate_music()
    print("done in", round(time.time() - t0, 1), "s")
