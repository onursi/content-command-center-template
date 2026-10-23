"""Gemeinsame Einstellungen für Server, MCP und Agent-Auslöser.

Reihenfolge (spätere gewinnen):
1. config.example.json (Standardwerte, liegt im Repo)
2. config.json        (deine eigene Fassung, wird nicht eingecheckt)
3. .env / Umgebungsvariablen (CCC_PORT, CCC_HOST, CCC_AGENT_AKTIV, CCC_CLAUDE_BEFEHL, CCC_ERLAUBTE_HOSTS, CCC_TOKEN)

Relative Pfade gelten ab dem Ordner dieser Datei. Keine Abhängigkeiten außer der Standardbibliothek.
"""
import json
import os
import secrets
import shutil
import urllib.parse
from pathlib import Path

HIER = Path(__file__).resolve().parent


def _env_datei_laden():
    datei = HIER / ".env"
    if not datei.is_file():
        return
    for zeile in datei.read_text(encoding="utf-8").splitlines():
        zeile = zeile.strip()
        if not zeile or zeile.startswith("#") or "=" not in zeile:
            continue
        k, v = zeile.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _mischen(basis, neu):
    for k, v in neu.items():
        if isinstance(v, dict) and isinstance(basis.get(k), dict):
            _mischen(basis[k], v)
        else:
            basis[k] = v
    return basis


def _pfad(p):
    pp = Path(os.path.expandvars(os.path.expanduser(str(p))))
    return (pp if pp.is_absolute() else HIER / pp).resolve()


_env_datei_laden()
_roh = json.loads((HIER / "config.example.json").read_text(encoding="utf-8"))
if (HIER / "config.json").is_file():
    _mischen(_roh, json.loads((HIER / "config.json").read_text(encoding="utf-8")))

CONFIG = _roh
HOST = os.environ.get("CCC_HOST", CONFIG["server"]["host"])
PORT = int(os.environ.get("CCC_PORT", CONFIG["server"]["port"]))
BASE_URL = f"http://127.0.0.1:{PORT}" if HOST in ("0.0.0.0", "::") else f"http://{HOST}:{PORT}"
ANZEIGENAME = CONFIG.get("anzeigename", "Content-Pipeline")

DATA_FILE = _pfad(CONFIG["daten"]["inhalte"])
STATE_FILE = _pfad(CONFIG["daten"]["stand"])

# Board-Adresse  ->  Ordner auf der Platte
MEDIEN = tuple((f"{name}/", _pfad(ordner)) for name, ordner in CONFIG["medien"].items())
UPLOAD_DIR = _pfad(CONFIG["medien"]["media_uploads"])   # Rohaufnahmen aus dem Board
AUTO_DIR = _pfad(CONFIG["medien"]["media_auto"])        # Arbeitsordner des Schnitt-Agenten

_agent = CONFIG["agent"]
AGENT_AKTIV = os.environ.get("CCC_AGENT_AKTIV", str(_agent["aktiv"])).lower() in ("1", "true", "ja", "yes")
CLAUDE_BEFEHL = os.environ.get("CCC_CLAUDE_BEFEHL", _agent["claude_befehl"])
AGENT_CWD = _pfad(_agent["arbeitsverzeichnis"])
AGENT_ARGUMENTE = list(_agent.get("claude_argumente", []))
AGENT_WERKZEUGE = list(_agent.get("erlaubte_werkzeuge", []))   # --allowedTools (leer = nicht setzen)
PAUSE_NACH_LAUF = int(_agent.get("pause_minuten", 10)) * 60
MAX_LAUFZEIT = float(_agent.get("max_laufzeit_minuten", 180)) * 60   # hängender Agent wird danach beendet
# art -> {auftrag, modell, chrome, aktiv, werkzeuge}
AGENT_ARTEN = {art: {"auftrag": w["auftrag"], "modell": w["modell"], "chrome": bool(w.get("chrome")),
                     "aktiv": bool(w.get("aktiv", True)),
                     "werkzeuge": AGENT_WERKZEUGE + list(w.get("erlaubte_werkzeuge_zusatz", []))}
               for art, w in _agent["arten"].items()}

# ---------------------------------------------------------------- Sicherheit
# Nur Anfragen an diese Hostnamen werden beantwortet (Schutz gegen DNS-Rebinding und fremde Webseiten).
_sicher = CONFIG.get("sicherheit", {})
ERLAUBTE_HOSTS = {"127.0.0.1", "localhost", "::1"}
ERLAUBTE_HOSTS |= {str(h).strip().lower().rstrip(".") for h in _sicher.get("erlaubte_hosts", []) if str(h).strip()}
ERLAUBTE_HOSTS |= {h.strip().lower().rstrip(".") for h in os.environ.get("CCC_ERLAUBTE_HOSTS", "").split(",") if h.strip()}
if HOST not in ("0.0.0.0", "::", ""):
    ERLAUBTE_HOSTS.add(HOST.lower())
TOKEN_AKTIV = os.environ.get("CCC_TOKEN", str(_sicher.get("token", True))).lower() in ("1", "true", "ja", "yes")
TOKEN_DATEI = HIER / ".ccc-token"


def hostname(wert):
    """'host:port', '[::1]:8899' oder eine URL -> reiner Hostname in Kleinbuchstaben (oder '')."""
    wert = (wert or "").strip()
    if not wert:
        return ""
    if "://" not in wert:
        wert = "http://" + wert
    try:
        return (urllib.parse.urlsplit(wert).hostname or "").lower().rstrip(".")
    except ValueError:
        return ""


def host_erlaubt(wert):
    return hostname(wert) in ERLAUBTE_HOSTS


def token():
    """Geteiltes Geheimnis zwischen Server, Board und MCP. Wird beim ersten Aufruf zufällig erzeugt
    und in .ccc-token abgelegt (nicht eingecheckt). Leer, wenn sicherheit.token = false."""
    if not TOKEN_AKTIV:
        return ""
    try:
        t = TOKEN_DATEI.read_text(encoding="utf-8").strip()
        if t:
            return t
    except OSError:
        pass
    t = secrets.token_urlsafe(32)
    TOKEN_DATEI.write_text(t, encoding="utf-8")
    return t

# Platzhalter in den Agent-Aufträgen (geplante-aufgaben/*.md), z. B. {{YOUTUBE_KANAL}}
PLATZHALTER = {k.upper(): str(v) for k, v in CONFIG.get("kanaele", {}).items()}
PLATZHALTER["ANZEIGENAME"] = ANZEIGENAME


def erster_start():
    """Beim ersten Start die Demodaten übernehmen, damit das Board nicht leer ist."""
    demo = HIER / "demo"
    if not DATA_FILE.is_file() and (demo / "data.json").is_file():
        shutil.copyfile(demo / "data.json", DATA_FILE)
    if not STATE_FILE.is_file() and (demo / "state.json").is_file():
        shutil.copyfile(demo / "state.json", STATE_FILE)
    for _, ordner in MEDIEN:
        ordner.mkdir(parents=True, exist_ok=True)
