# Instagram-Skills für Claude Code

Die Ordner `.claude/skills/ig-*` sind eine unveränderte Kopie von
https://github.com/Jakeschincariol/instagram-agent-skill
(Stand: Commit `d03c56b`, MIT-Lizenz, siehe `LICENSE` in diesem Ordner).

- 13 Befehle: `/ig-reel`, `/ig-viral`, `/ig-caption`, `/ig-carousel`, `/ig-story`,
  `/ig-profile`, `/ig-plan`, `/ig-human`, `/ig-comment`, `/ig-reply`, `/ig-dm`,
  `/ig-repurpose`, `/ig-audit`.
- Sie gelten nur für Claude Code in diesem Repo. JARVIS selbst nutzt sie nicht.
- Die Python-Skripte nutzen nur die Standardbibliothek und kein Netzwerk.
- Die Skills schreiben nur Entwürfe. Gepostet wird nichts.

## Deine Stimme
Die Skills lesen `~/.claude/instagram/voice.md`. Vorlage: `voice.md` in diesem
Ordner. Kopieren und ausfüllen:

    mkdir -p ~/.claude/instagram && cp .claude/skills/_instagram/voice.md ~/.claude/instagram/voice.md
