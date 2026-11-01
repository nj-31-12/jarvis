"""JARVIS-Stimme (Version 5.3): Mac-Stimme + eigener „Assistenten-Effekt“ – offline, kostenlos, nur Standardbibliothek.

Ablauf: Text → speakable/narrate_markup (Erzähler-Pausen) → `say` schreibt eine WAV-Datei → Effektkette → WAV.
Effektkette (eigener Klang, keine Kopie einer Filmstimme):
  0. Stand 18: ca. 3 Halbtöne tiefer und ruhiger (die Mac-Stimme spricht dafür schneller, das Absenken
     verlangsamt sie wieder auf ein entspanntes Tempo von ca. 135 Wörtern pro Minute)
  1. Hochpass (~120 Hz) und sanfter Tiefpass (~5,5 kHz): warm, klar, leicht „technisch“
  2. Verdopplung mit 11 ms Versatz: voller, leicht metallischer Klang
  3. leichte Ringmodulation (38 Hz, 8 %): dezentes Funk-/Helm-Timbre
  4. kurzes Echo (85 ms, 18 %): Raum wie in einer Werkstatt-Halle
  5. Pegel normalisieren
Sicherheit: `say` wird mit Argumentliste aufgerufen (keine Shell), Text ist begrenzt, Zeitlimit, nur Temp-Ordner.
Die Stimme läuft lokal auf dem Mac; es wird nichts an einen Dienst gesendet.
"""
from __future__ import annotations

import array
import hashlib
import io
import math
import os
import shutil
import subprocess
import sys
import tempfile
import wave
from dataclasses import replace
from pathlib import Path

from .speech import NARRATOR, _mac_voices, narrate_markup

MAX_TEXT_CHARS = 2500
CACHE_FILES = 40
FX_VERSION = "3"
PITCH = 0.84                 # < 1 = tiefer (0.84 ≈ 3 Halbtöne)
SPEAK_WPM = 160              # so schnell spricht die Mac-Stimme vor dem Absenken


class VoiceUnavailable(RuntimeError):
    """Keine Mac-Stimme verfügbar (z. B. nicht auf einem Mac). Der Browser kann dann selbst vorlesen."""


def cache_dir() -> Path:
    d = Path(tempfile.gettempdir()) / "jarvis-stimme"
    d.mkdir(mode=0o700, exist_ok=True)
    return d


def _clip(v: float) -> int:
    return -32768 if v < -32768 else 32767 if v > 32767 else int(v)


# Stand 21: Stimm-Modi. „film“ = eigener Kino-Klang (kein Nachbau einer echten Stimme).
PRESETS = {
    "film": {"pitch": 0.80, "wpm": 172, "hp": 90, "lp": 5200, "radio": 0.28, "dbl": (0.009, 0.32), "ring": 0.05,
             "early": ((0.007, 0.28), (0.013, 0.20), (0.021, 0.14)), "echo": ((0.11, 0.20), (0.23, 0.09)), "sat": 0.6},
    "jarvis": {"pitch": 0.84, "wpm": 160, "hp": 120, "lp": 5500, "radio": 0.0, "dbl": (0.011, 0.45), "ring": 0.08,
               "early": (), "echo": ((0.085, 0.18),), "sat": 0.0},
    "natuerlich": {"pitch": 0.93, "wpm": 150, "hp": 80, "lp": 7000, "radio": 0.0, "dbl": (0.0, 0.0), "ring": 0.0,
                   "early": (), "echo": (), "sat": 0.0},
}
DEFAULT_PRESET = "film"


def _onepole(x: list, rate: int, hp: float = 0.0, lp: float = 0.0) -> list:
    """Einpoliger Hoch- und/oder Tiefpass."""
    out, px, php, plp = [0.0] * len(x), 0.0, 0.0, 0.0
    ha = math.exp(-2 * math.pi * hp / rate) if hp else 0.0
    la = math.exp(-2 * math.pi * lp / rate) if lp else 0.0
    for i, v in enumerate(x):
        if hp:
            h = ha * (php + v - px)
            px, php = v, h
            v = h
        if lp:
            plp = (1 - la) * v + la * plp
            v = plp
        out[i] = v
    return out


def _resample(x: list, pitch: float) -> list:
    """Tiefer und langsamer durch Neuabtastung (lineare Interpolation)."""
    if not (0.5 < pitch < 1.0) or len(x) < 2:
        return x
    n_out, last = int((len(x) - 1) / pitch), len(x) - 1
    out = [0.0] * n_out
    for i in range(n_out):
        pos = i * pitch
        k = int(pos)
        frac = pos - k
        nxt = x[k + 1] if k < last else x[k]
        out[i] = x[k] + (nxt - x[k]) * frac
    return out


def iron_fx(wav_bytes: bytes, pitch: float = PITCH, preset: str = "jarvis") -> bytes:
    """Wendet die Effektkette eines Stimm-Modus auf eine 16-Bit-WAV an und gibt eine neue WAV zurück."""
    cfg = dict(PRESETS.get(preset, PRESETS[DEFAULT_PRESET]))
    if preset == "jarvis":
        cfg["pitch"] = pitch
    with wave.open(io.BytesIO(wav_bytes), "rb") as w:
        rate, ch, width, n = w.getframerate(), w.getnchannels(), w.getsampwidth(), w.getnframes()
        raw = w.readframes(n)
    if width != 2:
        raise ValueError("Nur 16-Bit-Audio wird unterstützt.")
    src = array.array("h")
    src.frombytes(raw)
    if sys.byteorder == "big":
        src.byteswap()
    if ch == 2:                                           # Stereo → Mono
        src = array.array("h", ((src[i] + src[i + 1]) // 2 for i in range(0, len(src) - 1, 2)))
    x = _resample([float(v) for v in src], cfg["pitch"])
    y = _onepole(x, rate, hp=cfg["hp"], lp=cfg["lp"])
    if cfg["radio"]:                                      # Funk-/Helm-Anteil: schmalbandig beigemischt
        radio = _onepole(_onepole(x, rate, lp=3200), rate, hp=350)
        y = [a * (1 - cfg["radio"]) + b * cfg["radio"] * 1.8 for a, b in zip(y, radio)]
    d1, g1 = int(rate * cfg["dbl"][0]), cfg["dbl"][1]
    w_ring, ring = 2 * math.pi * 38 / rate, cfg["ring"]
    taps = [(int(rate * t), g) for t, g in cfg["early"]] + [(int(rate * t), g) for t, g in cfg["echo"]]
    tail = max([t for t, _ in taps] + [0])
    out = [0.0] * (len(y) + tail)
    for i, v in enumerate(y):
        mixed = v + (g1 * y[i - d1] if d1 and i >= d1 else 0.0)
        if ring:
            mixed *= (1 - ring) + ring * math.sin(w_ring * i)
        out[i] += mixed
        for t, g in taps:
            out[i + t] += g * mixed
    peak = max(1.0, max(abs(v) for v in out)) if out else 1.0
    if cfg["sat"]:                                        # sanfte Sättigung: wärmer, „kinohafter“
        k = cfg["sat"] * 3
        out = [(1 + k) * (v / peak) / (1 + k * abs(v / peak)) for v in out]
        peak = max(1e-9, max(abs(v) for v in out))
    gain = 0.9 * 32767 / peak
    res = array.array("h", (_clip(v * gain) for v in out))
    if sys.byteorder == "big":
        res.byteswap()
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(res.tobytes())
    return buf.getvalue()


def _say_to_wav(text: str, voice: str | None, effect: bool = True, wpm: int = SPEAK_WPM) -> bytes:
    if not shutil.which("say"):
        raise VoiceUnavailable("Die Mac-Stimme (say) ist hier nicht verfügbar.")
    fd, tmp = tempfile.mkstemp(suffix=".wav", dir=str(cache_dir()))
    os.close(fd)
    try:
        cmd = ["say", "--file-format=WAVE", "--data-format=LEI16@22050", "-o", tmp]
        if voice:
            cmd += ["-v", voice]
        profile = replace(NARRATOR, words_per_minute=wpm if effect else NARRATOR.words_per_minute)
        cmd.append(narrate_markup(text, profile))
        subprocess.run(cmd, timeout=120, check=True, capture_output=True)   # Liste, keine Shell
        return Path(tmp).read_bytes()
    except (subprocess.SubprocessError, OSError) as exc:
        raise VoiceUnavailable("Die Mac-Stimme konnte den Text nicht sprechen.") from exc
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def jarvis_voice(text: str, effect: bool = True, preset: str = DEFAULT_PRESET) -> bytes:
    """WAV mit JARVIS-Stimme im gewählten Modus. Zwischenspeicher im Temp-Ordner (gleicher Text = sofort)."""
    preset = preset if preset in PRESETS else DEFAULT_PRESET
    text = (text or "").strip()[:MAX_TEXT_CHARS]
    if not text:
        raise VoiceUnavailable("Kein Text zum Vorlesen.")
    key = hashlib.sha256(f"{FX_VERSION}|{effect}|{preset}|{text}".encode("utf-8")).hexdigest()[:32]
    path = cache_dir() / f"{key}.wav"
    if path.exists():
        return path.read_bytes()
    voice = next((v for v in NARRATOR.mac_voices if v in _mac_voices()), None)
    audio = _say_to_wav(text, voice, effect, PRESETS[preset]["wpm"])
    if effect:
        audio = iron_fx(audio, PRESETS[preset]["pitch"], preset)
    path.write_bytes(audio)
    files = sorted(cache_dir().glob("*.wav"), key=lambda p: p.stat().st_mtime)
    for old in files[:-CACHE_FILES]:                     # nur eigene Zwischenspeicher-Dateien aufräumen
        try:
            old.unlink()
        except OSError:
            pass
    return audio
