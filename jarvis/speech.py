"""Vorbereitung für Sprachsteuerung (STT) und Sprachausgabe (TTS).

Phase 2: Nur Schnittstellen und eine stille Platzhalter-Stimme. Es wird nichts
installiert und kein Dienst verbunden. Welche echte Stimme später genutzt wird,
entscheidest du (siehe docs/09_Persoenlichkeit_und_Stimme.md):

  - macOS-Stimme über den Befehl `say` (bereits auf deinem Mac, kostenlos, offline)
  - Piper (Open Source, offline, kostenlos – Installation nötig, 🔐)
  - Cloud-Stimmen (z. B. OpenAI TTS, ElevenLabs – kostenpflichtig, 🔐)

Jede echte Stimme muss die Klasse TextToSpeech erfüllen. So kann sie später
ausgetauscht werden, ohne den Rest von JARVIS zu ändern.
"""
from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass, field


@dataclass
class VoiceProfile:
    description: str = "tief, ruhig, warm, natürlich, deutsch"
    language: str = "de-DE"
    rate: float = 0.95      # etwas langsamer als normal wirkt souveräner
    pitch: float = -2.0     # Halbtöne; negativ = tiefer (sofern die Stimme das unterstützt)
    words_per_minute: int = 150
    sentence_pause_ms: int = 350
    paragraph_pause_ms: int = 700
    # Bevorzugte Mac-Stimmen (männlich, deutsch); die erste vorhandene wird genutzt
    mac_voices: list = field(default_factory=lambda: ["Markus", "Yannick", "Viktor"])
    # Stilanweisung für spätere hochwertige Stimmen, die Anweisungen verstehen
    style_instruction: str = ""


# Erzähler-Profil: ruhig, tief, souverän, mit dramaturgischen Pausen.
# Bewusst ein STIL – keine Nachahmung einer bestimmten echten Person.
NARRATOR = VoiceProfile(
    description="tief, ruhig, natürlich, souverän und intelligent – wie ein erfahrener Dokumentarfilm-Erzähler",
    rate=0.9,
    pitch=-3.0,
    words_per_minute=145,
    sentence_pause_ms=420,
    paragraph_pause_ms=850,
    style_instruction=("Sprich ruhig, tief und warm wie ein erfahrener Erzähler eines Dokumentarfilms. "
                       "Gelassenes Tempo, klare Betonung der Schlüsselwörter, kurze Pausen vor wichtigen Aussagen, "
                       "nie hektisch, nie übertrieben theatralisch."),
)


class TextToSpeech:
    name = "abstrakt"

    def synthesize(self, text: str, profile: VoiceProfile) -> bytes:
        raise NotImplementedError


class SpeechToText:
    name = "abstrakt"

    def transcribe(self, audio: bytes, language: str = "de") -> str:
        raise NotImplementedError


class SilentTTS(TextToSpeech):
    """Platzhalter: erzeugt kein Audio, damit alles ohne Installation testbar bleibt."""
    name = "stumm"

    def synthesize(self, text: str, profile: VoiceProfile) -> bytes:
        return b""


class DisabledSTT(SpeechToText):
    name = "aus"

    def transcribe(self, audio: bytes, language: str = "de") -> str:
        raise RuntimeError("Spracherkennung ist noch nicht eingerichtet (Phase 3, nur mit deiner Freigabe).")


def speakable(text: str, max_chars: int = 1200) -> str:
    """Bereitet Markdown-Text zum Vorlesen auf: Tabellen, Emojis, Links und Formatierung entfernen."""
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    text = re.sub(r"^\s*\|.*\|\s*$", " ", text, flags=re.M)          # Tabellenzeilen
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)               # Links -> Linktext
    text = re.sub(r"[*_`#>]+", "", text)                               # Formatierung
    text = re.sub(r"^\s*[-+]\s+", "", text, flags=re.M)                # Listenpunkte
    text = re.sub(r"[\U0001F300-\U0001FAFF☀-➿️]", "", text)  # Emojis
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_chars]


def narrate_markup(text: str, profile: VoiceProfile = NARRATOR) -> str:
    """Fügt Sprechpausen ein (macOS-Steuerbefehle [[slnc ms]]), damit es wie ein Erzähler klingt."""
    text = speakable(text.replace("[[", "").replace("]]", ""), max_chars=4000)
    text = re.sub(r"([.!?])\s+", lambda m: f"{m.group(1)} [[slnc {profile.sentence_pause_ms}]] ", text)
    text = re.sub(r"([:;—–])\s+", lambda m: f"{m.group(1)} [[slnc {profile.sentence_pause_ms // 2}]] ", text)
    return f"[[rate {profile.words_per_minute}]] {text}"


def _mac_voices() -> set:
    try:
        out = subprocess.run(["say", "-v", "?"], capture_output=True, text=True, timeout=10).stdout
    except Exception:  # noqa: BLE001
        return set()
    return {line.split()[0] for line in out.splitlines() if "de_DE" in line and line.split()}


def mac_say(text: str, profile: VoiceProfile = NARRATOR) -> str:
    """Liest Text mit der eingebauten Mac-Stimme vor (offline, kostenlos, keine Installation)."""
    if not shutil.which("say"):
        return "Vorlesen geht nur auf dem Mac (Befehl 'say' nicht gefunden)."
    available = _mac_voices()
    voice = next((v for v in profile.mac_voices if v in available), None)
    cmd = ["say"] + (["-v", voice] if voice else []) + [narrate_markup(text, profile)]
    subprocess.run(cmd, timeout=300)   # Liste statt Shell-Text: Eingaben können keine Befehle einschleusen
    if voice:
        return f"Vorgelesen mit der Stimme {voice}."
    return ("Vorgelesen mit der Standardstimme. Für eine tiefere Stimme: Systemeinstellungen → Bedienungshilfen → "
            "Gesprochene Inhalte → Systemstimme → Anpassen → eine deutsche Männerstimme (z. B. Markus) laden.")


def get_tts(cfg: dict) -> TextToSpeech:
    # Nur die stille Stimme ist aktiv. Echte Stimmen werden erst nach Freigabe ergänzt.
    return SilentTTS()


def get_stt(cfg: dict) -> SpeechToText:
    return DisabledSTT()
