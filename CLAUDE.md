# Hinweise für Claude Code

## Kurzbefehl `insta@`
Wenn eine Nachricht `insta@` enthält, nutze die Instagram-Skills in `.claude/skills/ig-*`:

1. Wähle den passenden Skill für die Bitte:
   - Reel, Video, Hook, Skript → `ig-reel`
   - Caption, Bildunterschrift → `ig-caption`
   - Karussell, Swipe-Post → `ig-carousel`
   - Story → `ig-story`
   - Profil, Bio → `ig-profile`
   - Wochenplan, Contentplan → `ig-plan`
   - Was in der Nische funktioniert, Trends → `ig-viral`
   - Kommentar bei anderen → `ig-comment`
   - Antworten unter eigenem Post → `ig-reply`
   - Direktnachricht, DM, Kooperationsanfrage → `ig-dm`
   - Inhalt umwandeln (Video, Podcast, Newsletter) → `ig-repurpose`
   - Auswertung bisheriger Posts → `ig-audit`
   - Text menschlicher machen → `ig-human`
2. Falls die Skills nicht als Befehl geladen sind, lies die `SKILL.md` des Skills direkt und folge ihr.
3. Ist unklar, welcher Skill gemeint ist, frag kurz nach.
4. Jeder fertige Text läuft am Ende zusätzlich durch `ig-human`.
5. Es wird nur ein Entwurf geschrieben. Nichts wird gepostet oder gesendet.
