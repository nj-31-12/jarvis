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
FX_VERSION = "2"
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


def iron_fx(wav_bytes: bytes, pitch: float = PITCH) -> bytes:
    """Wendet die Effektkette auf eine 16-Bit-Mono-WAV an und gibt eine neue WAV zurück."""
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
    x = [float(s) for s in src]
    # 0. Tiefer und ruhiger: neu abtasten (lineare Interpolation)
    if pitch and 0.5 < pitch < 1.0 and len(x) > 1:
        n_out = int((len(x) - 1) / pitch)
        last = len(x) - 1
        res0 = [0.0] * n_out
        for i in range(n_out):
            pos = i * pitch
            k = int(pos)
            frac = pos - k
            nxt = x[k + 1] if k < last else x[k]
            res0[i] = x[k] + (nxt - x[k]) * frac
        x = res0
    # 1. Hochpass + Tiefpass (einpolig)
    hp_a = math.exp(-2 * math.pi * 120 / rate)
    lp_a = math.exp(-2 * math.pi * 5500 / rate)
    y, prev_x, prev_hp, prev_lp = [0.0] * len(x), 0.0, 0.0, 0.0
    for i, v in enumerate(x):
        hp = hp_a * (prev_hp + v - prev_x)
        prev_x, prev_hp = v, hp
        prev_lp = (1 - lp_a) * hp + lp_a * prev_lp
        y[i] = prev_lp
    # 2.–4. Verdopplung, Ringmodulation, Echo
    d1, d2 = int(rate * 0.011), int(rate * 0.085)
    w_ring = 2 * math.pi * 38 / rate
    out = [0.0] * (len(y) + d2)
    for i, v in enumerate(y):
        dbl = y[i - d1] if i >= d1 else 0.0
        mixed = v + 0.45 * dbl
        mixed = mixed * (0.92 + 0.08 * math.sin(w_ring * i))
        out[i] += mixed
        out[i + d2] += 0.18 * mixed
    # 5. Normalisieren auf ~90 %
    peak = max(1.0, max(abs(v) for v in out)) if out else 1.0
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


def _say_to_wav(text: str, voice: str | None, effect: bool = True) -> bytes:
    if not shutil.which("say"):
        raise VoiceUnavailable("Die Mac-Stimme (say) ist hier nicht verfügbar.")
    fd, tmp = tempfile.mkstemp(suffix=".wav", dir=str(cache_dir()))
    os.close(fd)
    try:
        cmd = ["say", "--file-format=WAVE", "--data-format=LEI16@22050", "-o", tmp]
        if voice:
            cmd += ["-v", voice]
        profile = replace(NARRATOR, words_per_minute=SPEAK_WPM if effect else NARRATOR.words_per_minute)
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


def jarvis_voice(text: str, effect: bool = True) -> bytes:
    """WAV mit JARVIS-Stimme. Zwischenspeicher im Temp-Ordner (gleicher Text = keine neue Berechnung)."""
    text = (text or "").strip()[:MAX_TEXT_CHARS]
    if not text:
        raise VoiceUnavailable("Kein Text zum Vorlesen.")
    key = hashlib.sha256(f"{FX_VERSION}|{effect}|{text}".encode("utf-8")).hexdigest()[:32]
    path = cache_dir() / f"{key}.wav"
    if path.exists():
        return path.read_bytes()
    voice = next((v for v in NARRATOR.mac_voices if v in _mac_voices()), None)
    audio = _say_to_wav(text, voice, effect)
    if effect:
        audio = iron_fx(audio)
    path.write_bytes(audio)
    files = sorted(cache_dir().glob("*.wav"), key=lambda p: p.stat().st_mtime)
    for old in files[:-CACHE_FILES]:                     # nur eigene Zwischenspeicher-Dateien aufräumen
        try:
            old.unlink()
        except OSError:
            pass
    return audio
