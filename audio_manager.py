import os
import math
import wave
import struct
import random
import sys
import pygame
import paths
import audio_tracks

AUDIO_DIR = paths.asset("audio")

def ensure_audio_dir():
    try:
        os.makedirs(AUDIO_DIR, exist_ok=True)
    except OSError:
        pass

def clamp(val, min_val=-32767, max_val=32767):
    return max(min_val, min(max_val, int(val)))

def write_wav(filename, samples, sample_rate=44100):
    ensure_audio_dir()
    filepath = os.path.join(AUDIO_DIR, filename)
    with wave.open(filepath, 'w') as wav:
        wav.setnchannels(1)  # mono
        wav.setsampwidth(2)   # 16-bit
        wav.setframerate(sample_rate)
        packed = struct.pack(f"<{len(samples)}h", *[clamp(s) for s in samples])
        wav.writeframes(packed)
    return filepath

def generate_swap_sfx():
    sample_rate = 44100
    duration = 0.09
    num_samples = int(sample_rate * duration)
    samples = []
    for i in range(num_samples):
        t = i / sample_rate
        progress = i / num_samples
        # Rapid upward pitch sweep 400Hz to 850Hz with smooth sine + triangle overtone
        freq = 400 + 450 * (progress ** 0.5)
        phase = 2 * math.pi * freq * t
        env = (1 - progress) ** 1.5 * math.sin(progress * math.pi)
        val = (math.sin(phase) * 0.7 + (2 * (phase / math.pi % 2) - 1) * 0.3) * env * 24000
        samples.append(val)
    return write_wav("sfx_swap.wav", samples, sample_rate)

OLO_VOICE = (520, 590, 660, 740, 830)        # Olo's talking blips: one pitch per letter group


def generate_olo_blip(k):
    """A 50 ms cartoon-voice blip (Olo typing out a line): square-ish, pitch sliding down a little."""
    sample_rate = 44100
    n = int(sample_rate * 0.05)
    base = OLO_VOICE[k]
    samples, phase = [], 0.0
    for i in range(n):
        p = i / n
        freq = base * (1.10 - 0.18 * p) * (1 + 0.02 * math.sin(i / sample_rate * 2 * math.pi * 38))
        phase += 2 * math.pi * freq / sample_rate
        s = math.sin(phase)
        tone = 0.6 * s + 0.4 * (1 if s >= 0 else -1) * 0.6 + 0.15 * math.sin(phase * 2)
        env = min(1.0, i / (sample_rate * 0.004)) * (1 - p) ** 1.8
        samples.append(tone * env * 13000)
    return write_wav(f"sfx_olo_{k + 1}.wav", samples, sample_rate)


def generate_reverse_sfx():
    sample_rate = 44100
    duration = 0.16
    num_samples = int(sample_rate * duration)
    samples = []
    for i in range(num_samples):
        t = i / sample_rate
        progress = i / num_samples
        # Laser phase sweep downwards then upwards
        freq = 900 - 400 * math.sin(progress * math.pi)
        phase = 2 * math.pi * freq * t
        env = (1 - progress) * math.sin(progress * math.pi * 0.5)
        # FM modulation
        mod = math.sin(2 * math.pi * 45 * t) * 80
        val = math.sin(2 * math.pi * (freq + mod) * t) * env * 22000
        samples.append(val)
    return write_wav("sfx_reverse.wav", samples, sample_rate)

def generate_star_sfx():
    sample_rate = 44100
    duration = 0.35
    num_samples = int(sample_rate * duration)
    samples = []
    for i in range(num_samples):
        t = i / sample_rate
        progress = i / num_samples
        env = math.exp(-6 * progress)
        # Sparkle chords: 1046Hz (C6), 1318Hz (E6), 1567Hz (G6), 2093Hz (C7)
        c6 = math.sin(2 * math.pi * 1046.5 * t) * 0.3
        e6 = math.sin(2 * math.pi * 1318.5 * t) * 0.3
        g6 = math.sin(2 * math.pi * 1567.9 * t) * 0.25
        c7 = math.sin(2 * math.pi * 2093.0 * t) * 0.25
        # Shimmer vibrato
        shimmer = 1 + 0.15 * math.sin(2 * math.pi * 18 * t)
        val = (c6 + e6 + g6 + c7) * env * shimmer * 25000
        samples.append(val)
    return write_wav("sfx_star.wav", samples, sample_rate)

def generate_die_sfx():
    sample_rate = 44100
    duration = 0.45
    num_samples = int(sample_rate * duration)
    samples = []
    rng = random.Random(42)
    for i in range(num_samples):
        t = i / sample_rate
        progress = i / num_samples
        env = (1 - progress) ** 2.2
        # Deep bass drop 150Hz -> 30Hz
        bass_freq = max(25, 150 - 120 * progress)
        bass = math.sin(2 * math.pi * bass_freq * t) * 0.6
        # Noise explosion crunch
        noise = (rng.random() * 2 - 1) * 0.4 * (1 - progress ** 0.5)
        val = (bass + noise) * env * 28000
        samples.append(val)
    return write_wav("sfx_die.wav", samples, sample_rate)

def generate_win_sfx():
    sample_rate = 44100
    duration = 0.85
    num_samples = int(sample_rate * duration)
    samples = [0.0] * num_samples
    notes = [
        (523.25, 0.00, 0.25),  # C5
        (659.25, 0.12, 0.25),  # E5
        (783.99, 0.24, 0.30),  # G5
        (1046.50, 0.36, 0.48), # C6
    ]
    for freq, start_time, note_dur in notes:
        start_idx = int(start_time * sample_rate)
        note_samples = int(note_dur * sample_rate)
        for j in range(note_samples):
            idx = start_idx + j
            if idx >= num_samples:
                break
            t = j / sample_rate
            env = math.exp(-3.5 * (j / note_samples))
            val = (math.sin(2 * math.pi * freq * t) * 0.7 +
                   math.sin(4 * math.pi * freq * t) * 0.25) * env * 18000
            samples[idx] += val
    return write_wav("sfx_win.wav", samples, sample_rate)

def generate_click_sfx():
    sample_rate = 44100
    duration = 0.04
    num_samples = int(sample_rate * duration)
    samples = []
    for i in range(num_samples):
        t = i / sample_rate
        progress = i / num_samples
        env = (1 - progress) ** 3
        freq = 800 - 300 * progress
        val = math.sin(2 * math.pi * freq * t) * env * 18000
        samples.append(val)
    return write_wav("sfx_click.wav", samples, sample_rate)

def generate_warp_sfx():
    sample_rate = 44100
    duration = 0.22
    num_samples = int(sample_rate * duration)
    samples = []
    for i in range(num_samples):
        t = i / sample_rate
        prog = i / num_samples
        env = math.sin(prog * math.pi) ** 0.8
        freq = 300 + 700 * math.sin(prog * math.pi * 0.8)
        mod = math.sin(2 * math.pi * 35 * t) * 60
        val = math.sin(2 * math.pi * (freq + mod) * t) * env * 22000
        samples.append(val)
    return write_wav("sfx_warp.wav", samples, sample_rate)

def generate_shield_sfx():
    sample_rate = 44100
    duration = 0.28
    num_samples = int(sample_rate * duration)
    samples = []
    for i in range(num_samples):
        t = i / sample_rate
        prog = i / num_samples
        env = math.exp(-7 * prog)
        # Resonant chime 880Hz + 1760Hz
        tone = math.sin(2 * math.pi * 880 * t) * 0.6 + math.sin(2 * math.pi * 1760 * t) * 0.4
        val = tone * env * 24000
        samples.append(val)
    return write_wav("sfx_shield.wav", samples, sample_rate)

def generate_near_miss_sfx():
    sample_rate = 44100
    duration = 0.08
    num_samples = int(sample_rate * duration)
    samples = []
    rng = random.Random(99)
    for i in range(num_samples):
        t = i / sample_rate
        prog = i / num_samples
        env = math.sin(prog * math.pi)
        noise = (rng.random() * 2 - 1) * 0.4
        whistle = math.sin(2 * math.pi * (1400 - 600 * prog) * t) * 0.6
        val = (noise + whistle) * env * 17000
        samples.append(val)
    return write_wav("sfx_near_miss.wav", samples, sample_rate)

def generate_combo_sfx():
    sample_rate = 44100
    duration = 0.14
    num_samples = int(sample_rate * duration)
    samples = []
    for i in range(num_samples):
        t = i / sample_rate
        prog = i / num_samples
        env = math.exp(-8 * prog)
        val = math.sin(2 * math.pi * 1318.5 * t) * env * 20000
        samples.append(val)
    return write_wav("sfx_combo.wav", samples, sample_rate)

def generate_heartbeat_sfx():
    sample_rate = 44100
    duration = 0.38
    num_samples = int(sample_rate * duration)
    samples = [0] * num_samples

    # Two cardiac pulses: Lub (t=0 to 0.13s), Dub (t=0.18 to 0.32s)
    pulses = [
        (0.00, 0.13, 64.0, 42.0, 1.0),
        (0.18, 0.14, 52.0, 36.0, 0.82)
    ]

    for start_t, dur, f_start, f_end, amp_factor in pulses:
        s_idx = int(start_t * sample_rate)
        p_samples = int(dur * sample_rate)
        for j in range(p_samples):
            idx = s_idx + j
            if idx >= num_samples:
                break
            t = j / sample_rate
            prog = j / p_samples
            env = math.sin(prog * math.pi) ** 1.8
            freq = f_start - (f_start - f_end) * prog
            val = (math.sin(2 * math.pi * freq * t) * 0.85 + math.sin(4 * math.pi * freq * t) * 0.15) * env * 29000 * amp_factor
            samples[idx] = clamp(samples[idx] + val)

    return write_wav("sfx_heartbeat.wav", samples, sample_rate)

def generate_synthwave_bgm(bpm=135, filename="bgm_synthwave.wav"):
    """Generates an upbeat energetic synthwave loop (~10.66s at 135 BPM, or high-tempo variant)"""
    sample_rate = 44100
    beats_per_bar = 4
    num_bars = 6
    total_beats = beats_per_bar * num_bars
    beat_dur = 60.0 / bpm
    total_dur = total_beats * beat_dur
    total_samples = int(sample_rate * total_dur)
    samples = [0.0] * total_samples
    fast = bpm > 140

    # Bass notes sequence across bars (frequencies in Hz)
    # Chord progression: Am -> F -> C -> G -> F -> E
    root_notes = [
        110.0, # A2
        87.31, # F2
        130.81,# C3
        98.00, # G2
        87.31, # F2
        82.41  # E2
    ]

    # Synth lead arpeggio scales (Am pentatonic / natural minor)
    lead_arps = [
        [440.0, 523.25, 659.25, 880.0, 659.25, 523.25, 659.25, 783.99], # Am
        [349.23, 440.0, 523.25, 698.46, 523.25, 440.0, 523.25, 659.25], # F
        [523.25, 659.25, 783.99, 1046.5, 783.99, 659.25, 783.99, 880.0],# C
        [392.00, 493.88, 587.33, 783.99, 587.33, 493.88, 587.33, 659.25],# G
        [349.23, 440.0, 523.25, 698.46, 523.25, 440.0, 523.25, 659.25], # F
        [329.63, 415.30, 493.88, 659.25, 493.88, 415.30, 493.88, 587.33],# E maj
    ]

    rng = random.Random(1337)

    for bar in range(num_bars):
        bar_start_time = bar * 4 * beat_dur
        root = root_notes[bar % len(root_notes)]
        arp = lead_arps[bar % len(lead_arps)]

        # 1. Driving Bassline (16th notes pulse: 16 per bar)
        sixteenth_dur = beat_dur / 4.0
        bass_gain = 5200 if fast else 4500
        for step in range(16):
            step_time = bar_start_time + step * sixteenth_dur
            start_idx = int(step_time * sample_rate)
            dur_samples = int(sixteenth_dur * 0.9 * sample_rate)
            octave_mult = 2.0 if (step % 2 == 1) else 1.0
            freq = root * octave_mult

            for j in range(dur_samples):
                idx = start_idx + j
                if idx >= total_samples:
                    break
                t = j / sample_rate
                env = (1 - (j / dur_samples)) ** 2.0
                saw = 0.6 * math.sin(2 * math.pi * freq * t) + \
                      0.3 * math.sin(4 * math.pi * freq * t) + \
                      0.15 * math.sin(6 * math.pi * freq * t)
                samples[idx] += saw * env * bass_gain

        # 2. Kick drum on beats 1, 2, 3, 4
        kick_gain = 9800 if fast else 8500
        for b in range(4):
            kick_time = bar_start_time + b * beat_dur
            start_idx = int(kick_time * sample_rate)
            kick_dur = 0.16
            kick_samples = int(kick_dur * sample_rate)
            for j in range(kick_samples):
                idx = start_idx + j
                if idx >= total_samples:
                    break
                t = j / sample_rate
                prog = j / kick_samples
                env = (1 - prog) ** 3
                freq = max(35, 160 * (1 - prog * 0.9))
                kick_val = math.sin(2 * math.pi * freq * t) * env * kick_gain
                samples[idx] += kick_val

        # 3. Snare / Clap on beats 2 and 4
        for b in (1, 3):
            snare_time = bar_start_time + b * beat_dur
            start_idx = int(snare_time * sample_rate)
            snare_dur = 0.2
            snare_samples = int(snare_dur * sample_rate)
            for j in range(snare_samples):
                idx = start_idx + j
                if idx >= total_samples:
                    break
                prog = j / snare_samples
                env = (1 - prog) ** 2.5
                noise = (rng.random() * 2 - 1) * 3500 * env
                body = math.sin(2 * math.pi * 180 * (j / sample_rate)) * env * 3000
                samples[idx] += (noise + body)

        # 4. Hi-hat on offbeats (every 8th note)
        eighth_dur = beat_dur / 2.0
        for step in range(8):
            hat_time = bar_start_time + step * eighth_dur + (eighth_dur * 0.5)
            start_idx = int(hat_time * sample_rate)
            hat_dur = 0.05
            hat_samples = int(hat_dur * sample_rate)
            for j in range(hat_samples):
                idx = start_idx + j
                if idx >= total_samples:
                    break
                prog = j / hat_samples
                env = (1 - prog) ** 4
                noise = (rng.random() * 2 - 1) * (2100 if fast else 1800) * env
                samples[idx] += noise

        # 5. Synth Arpeggio Lead (8th notes)
        for step in range(8):
            lead_time = bar_start_time + step * eighth_dur
            start_idx = int(lead_time * sample_rate)
            lead_note_dur = eighth_dur * 0.95
            lead_samples = int(lead_note_dur * sample_rate)
            freq = arp[step % len(arp)]

            for j in range(lead_samples):
                idx = start_idx + j
                if idx >= total_samples:
                    break
                t = j / sample_rate
                prog = j / lead_samples
                env = math.sin(prog * math.pi * 0.85) * (1 - prog * 0.5)
                square = 1.0 if math.sin(2 * math.pi * freq * t) > 0 else -1.0
                tone = 0.5 * math.sin(2 * math.pi * freq * t) + 0.3 * square
                samples[idx] += tone * env * (4200 if fast else 3600)

    return write_wav(filename, samples, sample_rate)

class AudioManager:
    def __init__(self):
        self.sounds = {}
        self.music_volume = 0.6
        self.sfx_volume = 0.8
        self.muted = False
        self.initialized = False
        self.current_track = None

        self._init_pygame_audio()
        self._ensure_all_assets()
        self._load_sounds()

    def _init_pygame_audio(self):
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=1024)
            self.initialized = True
        except Exception as e:
            print("Audio Init warning:", e)
            self.initialized = False

    def _ensure_all_assets(self):
        ensure_audio_dir()
        needed = {
            "sfx_swap.wav": generate_swap_sfx,
            "sfx_reverse.wav": generate_reverse_sfx,
            "sfx_star.wav": generate_star_sfx,
            "sfx_die.wav": generate_die_sfx,
            "sfx_win.wav": generate_win_sfx,
            "sfx_click.wav": generate_click_sfx,
            "sfx_warp.wav": generate_warp_sfx,
            "sfx_shield.wav": generate_shield_sfx,
            "sfx_near_miss.wav": generate_near_miss_sfx,
            "sfx_combo.wav": generate_combo_sfx,
            "sfx_heartbeat.wav": generate_heartbeat_sfx,
            **{f"sfx_olo_{k + 1}.wav": (lambda k=k: generate_olo_blip(k)) for k in range(len(OLO_VOICE))},
            "bgm_synthwave.wav": lambda: generate_synthwave_bgm(135, "bgm_synthwave.wav"),
            "bgm_synthwave_fast.wav": lambda: generate_synthwave_bgm(162, "bgm_synthwave_fast.wav"),
        }
        audio_tracks.ensure_all()
        for name, generator in needed.items():
            path = os.path.join(AUDIO_DIR, name)
            if not os.path.exists(path) or os.path.getsize(path) < 100:
                try:
                    generator()
                except Exception as e:
                    print(f"Error generating {name}:", e)

    def _load_sounds(self):
        if not self.initialized:
            return
        sound_files = [
            "sfx_swap", "sfx_reverse", "sfx_star", "sfx_die", "sfx_win", "sfx_click",
            "sfx_warp", "sfx_shield", "sfx_near_miss", "sfx_combo", "sfx_heartbeat",
            "sfx_bounce", "sfx_smash", "sfx_chase", "sfx_fxend", "sfx_coin", "sfx_tension_rise", "sfx_tick",
        ] + [f"sfx_olo_{k + 1}" for k in range(len(OLO_VOICE))]
        for name in sound_files:
            path = os.path.join(AUDIO_DIR, f"{name}.wav")
            if os.path.exists(path):
                try:
                    snd = pygame.mixer.Sound(path)
                    snd.set_volume(self.sfx_volume)
                    self.sounds[name] = snd
                except Exception as e:
                    print(f"Failed to load {name}:", e)

    def suspend(self):
        """iOS, going to the background: close the audio device. SDL does not pause it there by itself, and the
        system may take the audio queue away while the app sleeps - the first sound after coming back then waited
        for a dead audio thread and the system ended the frozen app (1.0.7: tap after returning = app closed)."""
        if not self.initialized:
            return
        self._resume_track = self.current_track
        try:
            pygame.mixer.music.stop()
            pygame.mixer.stop()
            pygame.mixer.quit()
        except Exception as e:
            print("audio suspend:", e)
        self.sounds = {}
        self.current_track = None
        self.initialized = False

    def resume(self):
        """Back in front: open the audio device again, reload the effects and restart the music that played."""
        if self.initialized:
            return
        self._init_pygame_audio()
        self._load_sounds()
        track = getattr(self, "_resume_track", None)
        if track:
            self.play_music(track, fade_ms=300)

    def play_sfx(self, name, volume=None):
        if not self.initialized or self.muted or self.sfx_volume <= 0.01:
            return
        snd = self.sounds.get(name)
        if snd:
            vol = self.sfx_volume if volume is None else min(1.0, max(0.0, volume * self.sfx_volume))
            snd.set_volume(vol)
            snd.play()

    def play_music(self, track_name="bgm_synthwave", loop=True, fade_ms=500):
        if not self.initialized:
            return
        path = os.path.join(AUDIO_DIR, f"{track_name}.wav")
        if not os.path.exists(path):
            if track_name.endswith("_fast"):
                fallback = track_name[:-5]
                fb_path = os.path.join(AUDIO_DIR, f"{fallback}.wav")
                if os.path.exists(fb_path):
                    path = fb_path
                    track_name = fallback
        if os.path.exists(path):
            try:
                vol = 0.0 if self.muted else self.music_volume
                if self.current_track != track_name:
                    pygame.mixer.music.stop()
                    pygame.mixer.music.load(path)
                    self.current_track = track_name
                    pygame.mixer.music.set_volume(vol)
                    pygame.mixer.music.play(-1 if loop else 0, fade_ms=fade_ms)
                    return
                pygame.mixer.music.set_volume(vol)
                if not pygame.mixer.music.get_busy():
                    pygame.mixer.music.play(-1 if loop else 0)
            except Exception as e:
                print("Music playback error:", e)

    def stop_music(self):
        if self.initialized:
            try:
                pygame.mixer.music.stop()
                self.current_track = None
            except Exception:
                pass

    def set_music_volume(self, vol):
        self.music_volume = max(0.0, min(1.0, vol))
        if self.initialized and not self.muted:
            try:
                pygame.mixer.music.set_volume(self.music_volume)
            except Exception:
                pass

    def set_sfx_volume(self, vol):
        self.sfx_volume = max(0.0, min(1.0, vol))
        for snd in self.sounds.values():
            snd.set_volume(self.sfx_volume)

    def toggle_mute(self):
        self.muted = not self.muted
        if self.initialized:
            if self.muted:
                pygame.mixer.music.set_volume(0.0)
            else:
                pygame.mixer.music.set_volume(self.music_volume)
        return self.muted
