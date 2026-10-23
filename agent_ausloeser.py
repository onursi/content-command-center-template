"""Agent-Auslöser für das Content Command Center: dem Agenten Bescheid geben, statt ihn nach Uhrzeit laufen zu lassen.

Ersetzt zeitgesteuerte Routinen (z. B. alle 30 Minuten), die meist nur „nichts fällig“ melden
und dabei jedes Mal eine volle KI-Sitzung kosten.

So arbeitet er:
- Läuft als Hintergrund-Thread im Server (server.py). Prüft OHNE KI (0 Tokens), ob Arbeit da ist – mit denselben Regeln
  wie die MCP-Werkzeuge faellige_uploads / schnitt_auftraege.
- Wird sofort geweckt, wenn sich im Board etwas ändert (Einplanen, „Jetzt posten“, Rohaufnahme hochgeladen, Freigabe, Korrektur),
  sonst prüft er einmal pro Minute (für Termine, deren Uhrzeit erreicht wird).
- Nur wenn Arbeit da ist, startet er Claude Code ohne Fenster (`claude -p`) mit dem Auftrag aus geplante-aufgaben/<name>.md.
  Platzhalter wie {{YOUTUBE_KANAL}} werden aus config.json ersetzt.
  Je Art läuft höchstens ein Agent gleichzeitig. Nach einem Lauf wartet er 10 Minuten, bevor er für dieselbe Art erneut startet
  (Schutz gegen Endlosschleifen, falls ein Lauf nichts am Stand ändert); eine Änderung im Board hebt die Wartezeit auf.
- Protokoll: agent-laeufe/<datum>_<art>.log und server.log.
Abschalten: "agent.aktiv": false in config.json (Standard) oder Datei AUSLOESER-AUS anlegen.
"""
import json
import os
import shutil
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path

import einstellungen as E

WEB_DIR = E.HIER
LOG_DIR = WEB_DIR / "agent-laeufe"
CWD = str(E.AGENT_CWD)
AUS = WEB_DIR / "AUSLOESER-AUS"
PAUSE_NACH_LAUF = E.PAUSE_NACH_LAUF

# art: (Auftragsdatei, Modell, mit Chrome) – aus config.json
ARTEN = E.AGENT_ARTEN

wecker = threading.Event()
_laeufe = {}          # art -> Popen
_letzter_start = {}   # art -> Zeitstempel
_log = print


def wecken():
    """Vom Server aufgerufen, wenn sich der Stand ändert."""
    _letzter_start.clear()          # Board-Änderung hebt die Wartezeit auf
    wecker.set()


def _stand():
    data = json.loads(E.DATA_FILE.read_text(encoding="utf-8"))
    try:
        state = json.loads(E.STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        state = {}
    items = state.get("items", {})
    for it in data.get("items", []):
        e = dict(it); e.update(items.get(it["id"], {}))
        yield e


def _upload_faellig():
    jetzt = datetime.now()
    out = []
    for e in _stand():
        plan = e.get("plan") or {}
        if e.get("entfernt") or not plan.get("zeit"):
            continue
        try:
            if datetime.fromisoformat(plan["zeit"]) > jetzt:
                continue
        except ValueError:
            continue
        fehler = e.get("fehler") or {}
        laeuft = e.get("upload_laeuft") or {}
        for p in plan.get("plattformen", []):
            if e.get(p) or p in fehler:
                continue
            seit = laeuft.get(p)
            if seit and (jetzt - datetime.fromisoformat(seit)).total_seconds() < 45 * 60:
                continue
            out.append(f"{e['id']}:{p}")
    return out


AGENT_DRAN = {"wartet", "korrektur", "rohschnitt_ok", "korrektur_video"}


def _schnitt_faellig():
    out = []
    for e in _stand():
        a = e.get("auto") or {}
        st = a.get("status")
        if e.get("entfernt") or not st:
            continue
        if st == "in_arbeit":
            try:
                alt = (datetime.now() - datetime.fromisoformat(a.get("seit", "2000-01-01T00:00:00"))).total_seconds()
            except ValueError:
                alt = 0
            if alt < 3 * 3600:
                continue
            st = a.get("vorher") or "wartet"
        if st in AGENT_DRAN:
            out.append(f"{e['id']}:{st}")
    return out


def _auftrag(datei):
    text = (WEB_DIR / "geplante-aufgaben" / datei).read_text(encoding="utf-8")
    if text.startswith("---"):
        text = text.split("---", 2)[2]
    for k, v in E.PLATZHALTER.items():
        text = text.replace("{{" + k + "}}", v)
    return text.strip()


def _starten(art, grund):
    datei, modell, chrome = ARTEN[art]
    LOG_DIR.mkdir(exist_ok=True)
    logdatei = LOG_DIR / f"{datetime.now():%Y-%m-%d_%H%M%S}_{art}.log"
    exe = shutil.which(E.CLAUDE_BEFEHL) or shutil.which(E.CLAUDE_BEFEHL + ".cmd") or shutil.which(E.CLAUDE_BEFEHL + ".exe")
    if not exe:
        _log("Agent-Auslöser: 'claude' nicht gefunden, kein Start"); return
    cmd = [exe, "-p", "--model", modell, *E.AGENT_ARGUMENTE]
    if chrome:
        cmd.append("--chrome")
    f = open(logdatei, "w", encoding="utf-8")
    f.write(f"Start {datetime.now():%Y-%m-%d %H:%M:%S} · Modell {modell} · Grund: {', '.join(grund)}\n\n"); f.flush()
    p = subprocess.Popen(cmd, cwd=CWD, stdout=f, stderr=subprocess.STDOUT, stdin=subprocess.PIPE,
                         creationflags=0x08000000 if os.name == "nt" else 0)   # Windows: kein Konsolenfenster
    p.stdin.write(_auftrag(datei).encode("utf-8")); p.stdin.close()   # Auftrag über die Standardeingabe
    _laeufe[art] = p
    _letzter_start[art] = time.time()
    _log(f"Agent-Auslöser: {art}-Agent gestartet ({modell}) wegen {', '.join(grund)} -> {logdatei.name}")


def _runde():
    if not E.AGENT_AKTIV or AUS.exists():
        return
    for art, pruefen in (("upload", _upload_faellig), ("schnitt", _schnitt_faellig)):
        p = _laeufe.get(art)
        if p and p.poll() is None:
            continue                                   # läuft noch
        if p:
            _log(f"Agent-Auslöser: {art}-Agent beendet (Code {p.returncode})")
            _laeufe.pop(art, None)
        if time.time() - _letzter_start.get(art, 0) < PAUSE_NACH_LAUF:
            continue
        try:
            grund = pruefen()
        except Exception as ex:
            _log(f"Agent-Auslöser: Prüfung {art} fehlgeschlagen: {ex}")
            continue
        if grund:
            _starten(art, grund)


def starten(log=print):
    global _log
    _log = log

    def schleife():
        time.sleep(15)          # Server erst hochfahren lassen
        _log("Agent-Auslöser bereit (0 Tokens im Leerlauf)." if E.AGENT_AKTIV
             else "Agent-Auslöser aus (agent.aktiv = false). Das Board funktioniert trotzdem.")
        while True:
            try:
                _runde()
            except Exception as ex:
                _log(f"Agent-Auslöser Fehler: {ex}")
            wecker.wait(60)
            wecker.clear()
            time.sleep(2)       # mehrere schnelle Änderungen zusammenfassen

    threading.Thread(target=schleife, daemon=True, name="agent-ausloeser").start()
