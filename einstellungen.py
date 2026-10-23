"""Gemeinsame Einstellungen für Server, MCP und Agent-Auslöser.

Reihenfolge (spätere gewinnen):
1. config.example.json (Standardwerte, liegt im Repo)
2. config.json        (deine eigene Fassung, wird nicht eingecheckt)
3. .env / Umgebungsvariablen (CCC_PORT, CCC_HOST, CCC_AGENT_AKTIV, CCC_CLAUDE_BEFEHL)

Relative Pfade gelten ab dem Ordner dieser Datei. Keine Abhängigkeiten außer der Standardbibliothek.
"""
import json
import os
import shutil
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
PAUSE_NACH_LAUF = int(_agent.get("pause_minuten", 10)) * 60
AGENT_ARTEN = {art: (w["auftrag"], w["modell"], bool(w.get("chrome"))) for art, w in _agent["arten"].items()}

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
