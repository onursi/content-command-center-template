# Einrichtung per Agent

Öffne Claude Code (oder einen anderen Coding-Agenten mit Terminal) **in diesem Ordner** und kopiere alles
zwischen den beiden Linien hinein. Der Agent richtet das Content Command Center ein und fragt dich nur, was er wissen muss.

---

Richte in diesem Ordner das „Content Command Center“ ein (README.md erklärt, was es ist). Sprich Deutsch mit mir,
kurz und einfach. Arbeite Schritt für Schritt und sag nach jedem Schritt in einem Satz, was passiert ist.

Regeln für dich:
- Ändere nichts außerhalb dieses Ordners, außer der MCP-Anmeldung bei Claude Code in Schritt 6.
- Schreib keine Passwörter, Tokens oder API-Schlüssel in Dateien, die eingecheckt werden. `.env` und `config.json` bleiben lokal (stehen in `.gitignore`).
- Schalte den Agent-Auslöser NICHT ein, solange ich es nicht ausdrücklich sage.
- Lade nichts hoch und poste nichts.

1. **Prüfen:** Betriebssystem, `python --version` (mindestens 3.10; unter Windows ggf. `py`), `claude --version`, `ffmpeg -version` (optional).
   Fehlt Python oder Claude Code, sag mir, wie ich es installiere, und halte an.
2. **Abhängigkeit:** `python -m pip install -r requirements.txt` (nur das Paket `mcp`). Bei Fehlern die Meldung kurz erklären.
3. **Fragen an mich** (alle auf einmal, mit Vorschlag in Klammern):
   - Wie soll das Board heißen? (Name deines Kanals)
   - Name deines YouTube-Kanals und dein TikTok-Konto (für die Kontoprüfung des Upload-Agenten; „weiß nicht“ ist ok)
   - In welchem Ordner liegen deine fertigen Videos und Cover? (erst mal leer lassen = Demodaten)
   - Port (8899)
4. **Einstellungen schreiben:** `config.example.json` nach `config.json` kopieren und meine Antworten eintragen
   (`anzeigename`, `kanaele.youtube_kanal`, `kanaele.tiktok_konto`, `medien.media_packages`, `server.port`).
   `agent.aktiv` bleibt `false`. Nur wenn der Port vom Standard abweicht: `.env.example` nach `.env` kopieren und `CCC_PORT` setzen.
5. **Board starten** im Hintergrund, ohne sichtbares Fenster: Windows `start.cmd`, sonst `./start.sh`.
   Dann prüfen, dass `http://127.0.0.1:<port>/api/config` antwortet und `/data.json` die Demovideos liefert.
   Ist der Port belegt oder gesperrt, schlag einen anderen vor und trag ihn in `.env` ein.
6. **MCP anmelden:** mit dem absoluten Pfad dieses Ordners und dem Python, das in Schritt 2 benutzt wurde:
   `claude mcp add --scope user kommandozentrale -- <python> <absoluter-pfad>/mcp_server.py`
   Gibt es den Namen schon, frag mich vorher, ob du ihn ersetzen sollst. Danach `claude mcp list` zeigen.
7. **Testlauf:** `python mcp_test.py` ausführen. Erwartet: Liste der Werkzeuge und am Ende `ALLES OK`.
   Schlägt etwas fehl, Ursache suchen und beheben, aber keine Tests abschwächen.
8. **Abschluss:** Sag mir
   - die Adresse des Boards,
   - dass der MCP verbunden ist (in einer neuen Claude-Code-Sitzung z. B. „Zeig mir mein Board“ sagen),
   - wie ich eigene Videos eintrage (Abschnitt „Eigene Videos eintragen“ im README),
   - und was ich vor dem Einschalten der Agenten tun muss: `geplante-aufgaben/upload.md` und `schnitt.md` lesen und anpassen,
     die Grenzen im README lesen (der Auslöser startet `claude -p` ohne Rückfragen), dann `"agent": {"aktiv": true}` setzen.
   Optional anbieten: Autostart beim Hochfahren (Windows: Verknüpfung zu `start.cmd` im Autostart-Ordner) – nur auf mein Ja.

---
