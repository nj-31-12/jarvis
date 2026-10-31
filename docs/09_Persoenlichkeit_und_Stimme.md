# 09 – Persönlichkeit und Stimme

## Persönlichkeit
Die Persönlichkeit steht als normaler Text in `config/persona.md`. Du kannst sie selbst anpassen, Programmierkenntnisse brauchst du dafür nicht.

Kurzfassung:
- Ruhig, souverän und strategisch, wie ein erfahrener Unternehmer.
- Freundlich, ehrlich und kritisch, mit dezentem, trockenem Humor.
- Trennt immer Fakt, Schätzung und hypothetisches Beispiel.
- Schließt mit höchstens drei konkreten nächsten Schritten.

**Wichtig:** Die Persönlichkeit ist eine Stilvorgabe für das Sprachmodell. Die **Sicherheitsregeln hängen nicht davon ab.** Sie sind im Code erzwungen. Selbst wenn jemand den Persönlichkeitstext ändert, bleiben Freigabeschicht, Sperren und Kostenbremse aktiv.

Im Prototyp antwortet noch ein Simulator. Die Persönlichkeit wirkt erst, wenn ein echtes Sprachmodell angebunden ist (Phase 3, über Hermes, nach deiner Kostenfreigabe).

## Stimme: vorbereitet, noch stumm
`jarvis/speech.py` enthält:
- `VoiceProfile`: gewünschter Klang (tief, ruhig, warm, deutsch), Tempo 0,95, Tonhöhe etwas tiefer.
- `TextToSpeech` und `SpeechToText`: feste Schnittstellen, damit die Stimme später austauschbar ist.
- `speakable()`: macht Text vorlesbar (entfernt Tabellen, Emojis und Formatierung).
- Die aktive Stimme ist `SilentTTS`. Sie erzeugt kein Audio, damit nichts installiert werden muss.

## Optionen für die echte Stimme (Entscheidung später, jeweils 🔐)

| Option | Klang | Kosten | Offline | Installation | Bemerkung |
|---|---|---|---|---|---|
| macOS-Stimme (`say`) | ordentlich, eher mechanisch | 0 € | ja | nein (evtl. Stimme in den Systemeinstellungen nachladen) | sofort testbar, siehe unten |
| Piper (Open Source) | gut, natürlich | 0 € | ja | ja | gute Wahl für den Server |
| Cloud-Stimmen (z. B. OpenAI TTS, ElevenLabs) | sehr hochwertig | nutzungsabhängig bzw. Abo | nein | nein | Preise vor Aktivierung prüfen; Budget beachten |

Für eine tiefe, hochwertige Stimme sind Cloud-Stimmen am stärksten. Sie kosten aber Geld und schicken Text an Dritte. **Empfehlung:** Erst Piper auf dem Server (kostenlos), Cloud-Stimmen nur nach deiner Freigabe und mit festem Limit.

### Schon heute ausprobieren (ohne Installation)
Diese Befehle nutzen nur, was auf deinem Mac bereits vorhanden ist.

Vorhandene deutsche Stimmen anzeigen:
```bash
say -v '?' | grep de_DE
```

Eine männliche Stimme ausprobieren, falls die Liste „Markus“ oder „Yannick“ enthält:
```bash
say -v Markus -r 165 "Guten Morgen. Ich habe drei Geschäftsideen für dich vorbereitet."
```

## Spracheingabe (später)
- **Über Telegram:** Hermes wandelt Sprachnachrichten automatisch in Text um (Whisper).
- **Im Browser:** Firefox unterstützt keine eingebaute Spracherkennung. Deshalb wird Audio aufgenommen und an den eigenen Server geschickt (Whisper lokal, kostenlos). Das kommt erst mit dem Server.
