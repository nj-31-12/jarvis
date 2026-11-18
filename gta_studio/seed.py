"""Start-Faktenbank. Stand: Wissen bis Mitte 2026 plus Recherche vom 18.11.2026.

WICHTIG: Vor jedem Video die Quelle selbst öffnen. Status „bestaetigt“ heißt: von Rockstar/Take-Two
öffentlich gezeigt oder gesagt. Leaks und Gerüchte bleiben gekennzeichnet, auch im Video.
"""
from __future__ import annotations

RS_VI = "https://www.rockstargames.com/VI"
RS_NEWS = "https://www.rockstargames.com/newswire"

FACTS = [
    # Release
    ("Release am 19. November 2026", "GTA 6 erscheint am 19. November 2026 für PS5 und Xbox Series X|S.",
     "release", "bestaetigt", "Rockstar Newswire", RS_NEWS),
    ("Zum Start keine PC-Version", "Für den Launch sind nur PS5 und Xbox Series X|S angekündigt. Ein PC-Termin ist nicht offiziell.",
     "release", "bestaetigt", "Rockstar Games", RS_VI),
    ("Zweimal verschoben", "Erst war Herbst 2025 geplant, dann der 26. Mai 2026 (Ankündigung 2. Mai 2025), dann der 19. November 2026 (Ankündigung 6. November 2025).",
     "release", "bestaetigt", "Rockstar Newswire", RS_NEWS),
    # Welt
    ("Leonida statt San Andreas", "GTA 6 spielt im fiktiven Bundesstaat Leonida, angelehnt an Florida.",
     "karte", "bestaetigt", "Rockstar Games", RS_VI),
    ("Sechs Regionen offiziell", "Rockstar zeigt Vice City, Leonida Keys, Grassrivers, Port Gellhorn, Ambrosia und den Mount Kalaga National Park.",
     "karte", "bestaetigt", "Rockstar Games", RS_VI),
    ("Rückkehr nach Vice City", "Vice City ist zum ersten Mal seit GTA Vice City (2002) und Vice City Stories wieder Hauptschauplatz.",
     "karte", "bestaetigt", "Rockstar Games", RS_VI),
    # Story / Figuren
    ("Zwei Hauptfiguren: Lucia und Jason", "Lucia Caminos und Jason Duval sind die beiden spielbaren Hauptfiguren.",
     "story", "bestaetigt", "Rockstar Games", RS_VI),
    ("Lucia startet im Gefängnis", "Trailer 1 beginnt mit Lucia in Haft im Leonida Penitentiary.",
     "story", "bestaetigt", "Trailer 1 (Rockstar)", RS_VI),
    ("Nebenfiguren offiziell vorgestellt", "Auf der offiziellen Seite stehen u. a. Cal Hampton, Boobie Ike, Dre'Quan Priest, Real Dimez, Raul Bautista und Brian Heder.",
     "story", "bestaetigt", "Rockstar Games", RS_VI),
    # Trailer
    ("Trailer 1 kam früher als geplant", "Trailer 1 erschien am 4. Dezember 2023, einen Tag früher, weil er vorher geleakt wurde.",
     "release", "bestaetigt", "Rockstar Games (X/Twitter)", RS_NEWS),
    ("Rekord für Trailer 1", "Trailer 1 wurde zum meistgesehenen Nicht-Musik-Video in den ersten 24 Stunden auf YouTube (rund 90 Mio. Aufrufe).",
     "release", "bestaetigt", "Guinness World Records / Presseberichte", ""),
    ("Trailer 2 auf einer PS5 aufgenommen", "Trailer 2 (6. Mai 2025) wurde laut Rockstar komplett auf einer PlayStation 5 aufgenommen, Mischung aus Gameplay und Zwischensequenzen.",
     "gameplay", "bestaetigt", "Rockstar Newswire", RS_NEWS),
    ("Social-Media-Parodie im Spiel", "Trailer 1 zeigt viele Handy-Clips im Stil von Social-Media-Videos. Das wirkt wie eine Parodie auf TikTok und Co.",
     "easter-egg", "bestaetigt", "Trailer 1 (Rockstar)", RS_VI),
    # Leak
    ("Der große Leak 2022", "Im September 2022 tauchten über 90 Videoclips einer frühen Entwicklungsversion auf. Rockstar bestätigte den Leak.",
     "leak", "bestaetigt", "Rockstar Games Stellungnahme", RS_NEWS),
    ("Leak-Material ist alt", "Die Leak-Clips zeigen einen frühen Stand. Grafik, Menüs und Details können im fertigen Spiel ganz anders sein.",
     "leak", "leak", "Analyse der Leak-Clips", ""),
    # Ungeklärt
    ("Preis des Spiels", "Spekuliert werden Preise über 70 €. Am Release-Tag im Store prüfen, bevor du eine Zahl nennst.",
     "release", "spekulation", "", ""),
    ("GTA Online für GTA 6", "Ein neuer Online-Modus gilt als sicher, Details und Start sind aber nicht offiziell bestätigt.",
     "gameplay", "geruecht", "", ""),
    ("Datenleck bei Rockstar 2026", "Presseberichte im April 2026 sprechen von einem Datenleck bei Rockstar, der Termin blieb laut Berichten bestehen. Details vor Nutzung prüfen.",
     "leak", "geruecht", "PCGamesN (April 2026)", "https://www.pcgamesn.com/gta-6-release-date"),
]


def seed(store) -> int:
    """Füllt die Faktenbank nur, wenn sie leer ist. Gibt die Anzahl neuer Fakten zurück."""
    if store.count("facts"):
        return 0
    for title, detail, category, status, source_name, source_url in FACTS:
        store.create("facts", {"title": title, "detail": detail, "category": category, "status": status,
                               "source_name": source_name, "source_url": source_url})
    return len(FACTS)
