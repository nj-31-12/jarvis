# 18 – Version 5: KI-Modelle, Freigabezentrale und Skills

## 1. KI-Modellverwaltung (Phase A)

**Grundsatz:** Jedes Modell ist gesperrt, das nicht ausdrücklich erlaubt ist.

| Modell | Darf arbeiten? |
|---|---|
| Eingebautes Testmodell `mock` | Ja. Es läuft offline und kostenlos, keine Daten verlassen den Rechner. |
| Jedes andere Modell | Nur wenn **alle** Bedingungen unten erfüllt sind. |

**Bedingungen für ein externes Modell**, z. B. später über OpenRouter. Jede einzelne braucht deine Entscheidung:
1. In `config/jarvis.json` gibt es einen Eintrag unter `ai.models`.
2. Dort steht `"approved": true`.
3. Dort steht `"privacy_reviewed_on"` mit dem Datum deiner Datenschutzprüfung. Sie gilt höchstens 180 Tage.
4. Dort steht `"cost_per_call_eur"` (größer als 0 und höchstens 1 €), damit die Kostenbremse greift.
5. Dort steht `"key_env"`: nur der **Name** der Schlüssel-Variable, z. B. `JARVIS_OPENROUTER_KEY`.
6. Der Schlüssel selbst steht **nur** in `.env` (Rechte 600).
7. Zusätzlich gilt `privacy.external_ai_allowed: true`.

Auch dann gelten weiter:
- Jede Anfrage läuft durch die Datenschutz-Schranke. Zugangsdaten, Bankdaten, E-Mail-Adressen, Telefonnummern und deine geschützten Begriffe werden vorher entfernt.
- Vertrauliche Notizen gelangen ohnehin nie in den Kontext.

**Beispiel (nur zur Erklärung, bitte nicht ohne Entscheidung eintragen):**
```json
"ai": {
  "active_model": "mock",
  "models": {
    "openrouter-beispiel": {
      "kind": "external", "provider": "openrouter", "approved": false,
      "privacy_reviewed_on": "2026-11-15", "key_env": "JARVIS_OPENROUTER_KEY",
      "cost_per_call_eur": 0.01, "tasks": ["chat"]
    }
  }
}
```

**Was jetzt technisch verhindert wird:**
- **Schlüssel in der Konfiguration:** Steht ein API-Schlüssel in `config/jarvis.json`, startet JARVIS nicht und sagt dir, wo er steht.
- **Falsche Selbstauskunft:** Ein Modell, das „ich bin lokal“ behauptet, ist trotzdem gesperrt. Das war die Schwäche aus Version 4.2.
- **Protokoll:** Jeder Zugriffsversuch wird festgehalten, ob erlaubt oder gesperrt. Gespeichert werden nur Modell, Aufgabe, Entscheidung und Textlänge, nie Inhalte oder Schlüssel.
- **Übersicht:** Welche Modelle wie freigegeben sind, zeigt dieser Befehl (nur lesen):
  ```bash
  python3 -m jarvis ki-status
  ```

**Alte Chat-Antworten:**
- **Alte `/suche`-Antworten:** Antworten aus Schritt 3 zeigen Notiz-Auszüge ohne Quellenangabe. Sie werden jetzt vorsorglich zurückgehalten. Ansehen oder schwärzen geht wie bisher nach Passwort-Bestätigung.
- **Befehlsausgaben** wie `/offen`, `/suche` oder `/status` gehen nie als Verlauf an ein Modell.

## 2. Freigabezentrale (Phase B)

Im Browser unter **Freigaben**:
- offene Aktionen mit Beschreibung, betroffenen Konten, betroffenen Daten, möglichen Kosten und dem genauen Inhalt;
- die Schaltflächen **Genehmigen** und **Ablehnen**;
- ein **Sicherheitsprotokoll** (nur Art, Zeit und Kennungen, keine Inhalte);
- die **Notabschaltung**.

**Regeln, die der Code erzwingt:**
- **Nur die gezeigte Fassung:** Eine Freigabe gilt nur für genau die angezeigte Fassung. Beschreibung, Konten, Daten und Kosten sind Teil der Signatur.
- **Änderung braucht neue Freigabe:** Ändert JARVIS eine Aktion, entsteht eine **neue** Aktion. Die alte wird „ersetzt“ und kann nicht mehr genehmigt werden.
- **Manipulation:** Wurde der gespeicherte Inhalt verändert, wird die Freigabe verweigert und der Vorfall protokolliert.
- **Genehmigen** braucht ein Prüf-Häkchen **und** dein Passwort. Es gibt keine automatische Genehmigung.
- **Ablehnen** geht immer, dabei passiert nichts.
- **Gesperrt bleiben** Bestellungen, Zahlungen und Bankzugriffe, auch mit Freigabe (deine Regel 8).
- **Simuliert:** Alle Ausführungen sind weiterhin nur simuliert. Sie landen als Datei in `data/sandbox/outbox/`.

**Genehmigen im Browser einschalten** (Standard: aus, Ablehnen geht trotzdem). Trage in `config/jarvis.json` ein:
```json
"web": {"host": "127.0.0.1", "port": 8765, "session_minutes": 30, "approvals_enabled": true, "users": ["nj"]}
```
Danach JARVIS neu starten. Der Sicherheitscheck weist dann darauf hin, dass das Genehmigen im Browser eingeschaltet ist.

## 3. Skills (Phase C)

Es gibt sechs Skills: Internetrecherche, Gmail, Kalender, Shopify, Obsidian-Wissensdatenbank und Tagesbriefing.

- **Anfangszustand:** Alle Skills sind anfangs **aus**.
- **Einschalten:** Im Browser unter **Skills** „Aktivierung beantragen“ klicken, dann in der Freigabezentrale genehmigen.
- **Ausschalten:** Geht jederzeit sofort. Dabei werden alle Berechtigungen entzogen.
- **Berechtigungen:** Jede Operation braucht genau eine benannte Berechtigung. Mehr Rechte gibt es nur über eine neue Freigabe (`grant_permission`).
- **Was direkt passiert:** Lesen und Entwürfe.
- **Was nur vorgeschlagen wird:** E-Mail senden, Termin eintragen und Produkt ändern. Diese Aktionen warten in der Freigabezentrale.
- **Adapter:** Zurzeit gibt es nur **Testadapter**. Sie arbeiten mit erfundenen Daten, ohne Internet und ohne Konto. Ein Test prüft, dass kein Netzwerkzugriff stattfindet.
- **Ausnahmen:** „Wissen“ liest dein `data/vault` (ohne vertrauliche Notizen) und schreibt nur neue Notizen in `00_Inbox/JARVIS`. Das Tagesbriefing nutzt nur Skills, die du eingeschaltet hast.
- **Echte Verbindungen** (Gmail, Google Kalender, Shopify, Websuche) kommen erst nach deiner ausdrücklichen Freigabe, jede einzeln.
