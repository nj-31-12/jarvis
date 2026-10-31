"""Profile für Noahs tatsächliche Geschäftsbereiche (Phase 2, Schritt 4).

Grundlage: Noahs Profil vom 30.10.2026. Alles hier ist „laut deiner Angabe“, keine von JARVIS
geprüfte Tatsache. Status-Werte trennen klar: aktiv · Ausbildung · laufend · Idee.

JARVIS legt Profile nur als NEUE Entwürfe in 00_Inbox/JARVIS an. Du prüfst sie und verschiebst sie
selbst nach 02_Projekte. Existiert für einen Bereich schon ein Profil (egal wo), wird keins angelegt.
"""
from __future__ import annotations

from .knowledge import KnowledgeBase
from .obsidian import Vault

PROFILE_SOURCE = "Noahs Profil vom 30.10.2026"

PROJECTS = [
    {
        "slug": "nj-coaching", "name": "NJ Coaching / NYoung.Coaching", "status": "aktiv", "art": "Unternehmen",
        "angaben": ["Fitnessberatung, Trainingsprogramme, Ernährungsberatung, Muskelaufbau, Gewichtsreduktion "
                    "und digitale Coaching-Angebote",
                    "Fitness-Community mit mehreren Hundert Mitgliedern",
                    "Programm „You vs. You“ organisiert"],
        "kennzahlen": ["Community-Mitglieder", "Zahlende Coaching-Kunden", "Umsatz pro Monat (€)",
                       "Anfragen pro Monat", "Teilnehmer „You vs. You“"],
        "hinweise": ["Eigene Marke, getrennt von Scent Edit / WYLD NOTES.",
                     "Keine Heilversprechen; Gesundheitsaussagen vorsichtig formulieren."],
        "themen": ["NYoung.Coaching", "Fitness und Ernährungsberatung", "Community-Management"],
    },
    {
        "slug": "scent-edit", "name": "Scent Edit / WYLD NOTES", "status": "aktiv", "art": "Projekt (Affiliate)",
        "angaben": ["Eigenständiges Parfüm-Affiliate-Projekt",
                    "Kanäle: Shopify, Instagram, TikTok, Pinterest"],
        "kennzahlen": ["Shop-Besucher pro Monat", "Affiliate-Klicks", "Affiliate-Umsatz/Provision (€)",
                       "Follower Instagram", "Follower TikTok", "Pinterest-Aufrufe"],
        "hinweise": ["Eigenständige Marke, getrennt von Fitness.",
                     "Affiliate-Links und Werbung kennzeichnen (§ 5a UWG)."],
        "themen": ["Scent Edit und Parfüm-Affiliate-Marketing", "Shopify und E-Commerce"],
    },
    {
        "slug": "social-media", "name": "Social Media & Content", "status": "aktiv", "art": "Querschnitt für alle Marken",
        "angaben": ["Content-Strategien, Werbekampagnen, KI-Videos und Automatisierung",
                    "Werkzeuge: Canva, HeyGen, Higgsfield"],
        "kennzahlen": ["Beiträge pro Woche", "Reichweite pro Monat", "Neue Follower pro Monat",
                       "Werbebudget pro Monat (€)"],
        "hinweise": ["Veröffentlichungen nur nach deiner Freigabe; JARVIS erstellt nur Entwürfe.",
                     "Kosten für Werkzeuge im 20-€-Rahmen von JARVIS sind davon getrennt zu betrachten."],
        "themen": ["Social Media und Content-Produktion", "KI-Automatisierung"],
    },
    {
        "slug": "young-living", "name": "Young Living Network-Marketing", "status": "aktiv",
        "art": "Network-Marketing (Vertriebspartner)",
        "angaben": ["Aktiver Geschäftsbereich (laut deiner Angabe vom 30.10.2026)"],
        "kennzahlen": ["Eigene Kosten pro Monat (Bestellungen, Material) (€)", "Provisionen pro Monat (€)",
                       "Gewinn nach Kosten (€)", "Kundinnen/Kunden", "Zeitaufwand pro Woche (Std.)"],
        "hinweise": ["Realistisch rechnen: Laut veröffentlichten Einkommensübersichten verdient die Mehrheit der "
                     "Partner wenig. Immer Gewinn NACH Kosten und Zeit betrachten.",
                     "Keine Heil- oder Wirkversprechen für Öle (Heilmittelwerbegesetz, UWG). Werbung kennzeichnen.",
                     "Eigenständig von NJ Coaching und Scent Edit / WYLD NOTES halten, außer du entscheidest es anders."],
        "themen": ["Young Living Network-Marketing"],
    },
    {
        "slug": "automobil", "name": "Automobilbranche", "status": "Ausbildung", "art": "Ausbildung + langfristige Idee",
        "angaben": ["Ausbildung zum Automobilkaufmann: kaufmännische Prozesse, Kundenservice",
                    "Langfristige Ideen: Fahrzeughandel, Vermietung, digitale Dienstleistungen (noch nicht aktiv)"],
        "kennzahlen": ["Ausbildungsjahr", "Nächster Prüfungstermin", "Lernstunden pro Woche"],
        "hinweise": ["Keine vertraulichen Daten des Ausbildungsbetriebs in JARVIS oder Obsidian speichern.",
                     "Eigene Vorhaben in der Branche vorher auf Konkurrenz zum Ausbildungsbetrieb prüfen."],
        "themen": ["Automobilbranche und Fahrzeughandel"],
    },
    {
        "slug": "ideen", "name": "Ideen-Pool", "status": "Idee", "art": "Noch keine aktiven Unternehmen",
        "angaben": ["KI-Agentur (Idee)", "Webdesign (Idee)", "Digitale Produkte (Idee)",
                    "Online-Marketing (Idee)", "Sportbekleidung (Idee)"],
        "kennzahlen": ["Bewertete Ideen", "Laufende Tests (z. B. Warteliste)", "Ergebnis des letzten Tests"],
        "hinweise": ["Ideen sind nicht automatisch aktive Unternehmen.",
                     "Bewertung nach Kosten, Risiken, Aufwand, Ertrag und Umsetzbarkeit."],
        "themen": ["Neue digitale Geschäftsmodelle", "Webdesign und Softwareentwicklung", "KI-Automatisierung"],
    },
    {
        "slug": "lernen", "name": "Lernen & Organisation", "status": "laufend", "art": "Persönliche Entwicklung",
        "angaben": ["Interessen: KI, Automatisierung, E-Commerce, Fitness, Ernährung, Social Media, Webdesign",
                    "JARVIS soll beim Lernen und bei der Organisation unterstützen"],
        "kennzahlen": ["Lernstunden pro Woche", "Abgeschlossene Kurse/Bücher", "Offene Lernziele"],
        "hinweise": ["Ausbildung hat Vorrang."],
        "themen": ["Weiterbildung und persönliche Entwicklung", "Unternehmensführung und Organisation"],
    },
]


def profile_markdown(p: dict) -> str:
    rows = "\n".join(f"| {k} | | |" for k in p["kennzahlen"])
    return "\n".join([
        "> Entwurf von JARVIS. Bitte prüfen und ergänzen. Danach selbst nach `02_Projekte` verschieben.",
        "",
        "## Status",
        f"**{p['status']}** · {p['art']}",
        "",
        f"## Angaben (laut {PROFILE_SOURCE})",
        *[f"- {a}" for a in p["angaben"]],
        "",
        "## Ziel für die nächsten 90 Tage",
        "_Bitte ergänzen._",
        "",
        "## Kennzahlen",
        "| Kennzahl | Wert | Stand (Datum) |",
        "|---|---|---|",
        rows,
        "",
        "## Engpass",
        "_Was bremst gerade am meisten?_",
        "",
        "## Nächster Schritt",
        "_Ein konkreter Schritt, der diese Woche machbar ist._",
        "",
        "## Offene Entscheidungen",
        "_Bitte ergänzen._",
        "",
        "## Hinweise und Abgrenzung",
        *[f"- {h}" for h in p["hinweise"]],
        "",
        "## Verknüpfte Themen",
        ", ".join(p["themen"]),
    ])


def profile_status(kb: KnowledgeBase) -> list[dict]:
    """Für jeden Bereich: fehlt · Entwurf (Inbox) · übernommen (anderer Ordner). Liest nur Metadaten."""
    found: dict = {}
    for n in kb.notes(include_confidential=True):
        if n.meta.get("typ") == "bereichsprofil" and n.meta.get("bereich"):
            found.setdefault(n.meta["bereich"], []).append(n)
    result = []
    for p in PROJECTS:
        notes = sorted(found.get(p["slug"], []), key=lambda n: -n.mtime)
        if not notes:
            state, note = "fehlt", None
        else:
            adopted = [n for n in notes if not n.relpath.startswith("00_Inbox/")]
            note = adopted[0] if adopted else notes[0]
            state = "übernommen" if adopted else "Entwurf"
        result.append({"project": p, "state": state, "note": note})
    return result


def create_missing_drafts(vault: Vault, kb: KnowledgeBase) -> list[str]:
    """Legt NUR für fehlende Bereiche einen neuen Entwurf an. Gibt die Dateinamen zurück."""
    created = []
    for entry in profile_status(kb):
        if entry["state"] != "fehlt":
            continue
        p = entry["project"]
        path = vault.write_draft(f"Bereichsprofil {p['name']}", profile_markdown(p), ["bereichsprofil"],
                                 extra_meta={"typ": "bereichsprofil", "bereich": p["slug"],
                                             "bereich_status": p["status"], "vertraulich": "nein"})
        created.append(path.name)
    kb.refresh(force=True)
    return created
