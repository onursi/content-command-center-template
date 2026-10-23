"""Kommandozentrale-MCP: verbindet das Content Command Center (Standard-Port 8899) mit KI-Agenten.

Lesen:   Board-Übersicht, Videos, Details mit Texten und Dateipfaden, fällige Uploads.
Schreiben (über den laufenden Server, Eintrag für Eintrag zusammengeführt):
         Stufe, gepostet-Häkchen, Termine, Texte, Ideen, verwerfen/zurückholen.
Hochladen macht der Agent selbst (Claude in Chrome); dieser Server lädt nichts hoch.
Start:   python mcp_server.py   (stdio, wird von Claude Code gestartet)
"""
import json
import urllib.request
from datetime import datetime
from pathlib import Path

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

import einstellungen as E

BASE = E.BASE_URL
WEB_DIR = E.HIER
AUTO_DIR = E.AUTO_DIR
MEDIEN = E.MEDIEN

STUFEN = {"skript": "Skript", "aufgenommen": "Roh", "schnitt": "Schnitt", "bereit": "Bereit", "live": "Live"}
PLATTFORMEN = {"tiktok": "TikTok", "youtube": "YouTube"}

LESEN = ToolAnnotations(readOnlyHint=True, openWorldHint=False)
SCHREIBEN = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False)

mcp = MCPServer(
    "kommandozentrale",
    title="Kommandozentrale (Content Command Center)",
    instructions=(
        "Content-Pipeline: Skript → Roh → Schnitt → Bereit → Live, Plattformen TikTok und YouTube. "
        "Hochladen nur für Videos, die einen Termin haben (der Termin ist das Ja des Nutzers) oder die der Nutzer im Chat ausdrücklich freigibt. "
        "Vor jedem Upload im YouTube-/TikTok-Studio den Kanalnamen prüfen. Nach dem Posten als_gepostet_markieren aufrufen. "
        "Texte immer aus video_details nehmen: dort ist die bearbeitete Fassung des Nutzers schon eingerechnet."
    ),
)


# ---------------------------------------------------------------- Zugriff auf den laufenden Server
def _get(pfad):
    with urllib.request.urlopen(BASE + "/" + pfad, timeout=10) as r:
        return json.loads(r.read().decode("utf-8"))


def _post(pfad, daten):
    kopf = {"Content-Type": "application/json"}
    if E.token():
        kopf["X-CCC-Token"] = E.token()      # geteiltes Token des Servers (.ccc-token)
    req = urllib.request.Request(BASE + "/" + pfad, data=json.dumps(daten).encode("utf-8"),
                                 headers=kopf, method="POST")
    with urllib.request.urlopen(req, timeout=10) as r:
        if r.status not in (200, 204):
            raise RuntimeError(f"Server antwortet {r.status}")


def _laden():
    try:
        daten, stand = _get("data.json"), _get("api/state")
    except OSError as e:
        raise RuntimeError(f"Command Center läuft nicht ({BASE}). Bitte 'python server.py' starten.") from e
    stand.setdefault("items", {}); stand.setdefault("ideen", [])
    return daten, stand


def _setzen(iid, felder):
    _post("api/item", {"id": iid, "set": felder})


def _absolut(p):
    if not p:
        return None
    for prefix, basis in MEDIEN:
        if p.startswith(prefix):
            return str(basis / p[len(prefix):])
    pp = Path(p)
    return str(pp if pp.is_absolute() else WEB_DIR / pp)


def _web(pfad):
    """Absoluten Dateipfad in eine Board-Adresse umwandeln (nur Dateien in den freigegebenen Ordnern)."""
    pp = Path(pfad).resolve()
    if not pp.is_file():
        raise ValueError(f"Datei nicht gefunden: {pfad}")
    for prefix, basis in MEDIEN:
        b = basis.resolve()
        if b in pp.parents:
            return prefix + pp.relative_to(b).as_posix()
    raise ValueError(f"Datei muss unter {AUTO_DIR} (Arbeitsordner) oder einem Medienordner liegen: {pfad}")


def _arbeitsordner(a, e):
    """Arbeitsordner aus dem Stand nur übernehmen, wenn er unter AUTO_DIR liegt; sonst Standardordner."""
    standard = AUTO_DIR / f"{datetime.now():%Y-%m-%d}_{e['id']}"
    wunsch = a.get("arbeitsordner")
    if wunsch:
        try:
            pp = Path(wunsch).resolve()
            if AUTO_DIR.resolve() in pp.parents:
                return str(pp)
        except (OSError, ValueError):
            pass
    return str(standard)


def _eintrag(item, stand):
    e = dict(item)
    e.update(stand["items"].get(item["id"], {}))
    return e


def _finden(daten, stand, iid):
    for it in daten["items"]:
        if it["id"] == iid:
            return _eintrag(it, stand)
    namen = ", ".join(i["id"] for i in daten["items"])
    raise ValueError(f"Kein Video mit id '{iid}'. Vorhanden: {namen}")


def _texte(e):
    neu = e.get("texte_neu") or {}
    return [{"name": t["name"], "text": neu.get(t["name"], t["text"]), "bearbeitet": t["name"] in neu}
            for t in (e.get("texte") or [])]


def _kurz(e):
    return {
        "id": e["id"], "titel": e.get("titel"), "take": e.get("take"),
        "stufe": STUFEN.get(e.get("stage"), e.get("stage")),
        "gepostet": {k: bool(e.get(k)) for k in PLATTFORMEN},
        "termin": e.get("plan"), "verworfen": bool(e.get("entfernt")),
        **({"upload_fehler": e["fehler"]} if e.get("fehler") else {}),
    }


# ---------------------------------------------------------------- Lesen
@mcp.tool(annotations=LESEN)
def board_uebersicht() -> dict:
    """Überblick über das ganze Board: Anzahl je Stufe, alle Videos kurz, anstehende Termine und Anzahl Ideen."""
    daten, stand = _laden()
    alle = [_eintrag(i, stand) for i in daten["items"]]
    aktiv = [e for e in alle if not e.get("entfernt")]
    termine = sorted((e for e in aktiv if (e.get("plan") or {}).get("zeit")), key=lambda e: e["plan"]["zeit"])
    return {
        "je_stufe": {name: sum(1 for e in aktiv if e.get("stage") == sid) for sid, name in STUFEN.items()},
        "videos": [_kurz(e) for e in aktiv],
        "termine": [{"id": e["id"], "titel": e.get("titel"), **e["plan"]} for e in termine],
        "verworfen": sum(1 for e in alle if e.get("entfernt")),
        "ideen": len(stand["ideen"]),
    }


@mcp.tool(annotations=LESEN)
def videos_auflisten(stufe: str | None = None, verworfene_zeigen: bool = False) -> list[dict]:
    """Videos auflisten, optional nur eine Stufe (skript, aufgenommen, schnitt, bereit, live).
    verworfene_zeigen=True listet nur die verworfenen (Archiv)."""
    daten, stand = _laden()
    out = []
    for it in daten["items"]:
        e = _eintrag(it, stand)
        if bool(e.get("entfernt")) != verworfene_zeigen:
            continue
        if stufe and e.get("stage") != stufe:
            continue
        out.append(_kurz(e))
    return out


@mcp.tool(annotations=LESEN)
def video_details(video_id: str) -> dict:
    """Alles zu einem Video: Texte (die bearbeitete Fassung des Nutzers eingerechnet), absolute Pfade zu Video,
    Thumbnail, Rohdatei und Ordner, Hinweis, Termin und was schon gepostet ist."""
    daten, stand = _laden()
    e = _finden(daten, stand, video_id)
    return {
        **_kurz(e),
        "untertitel": e.get("untertitel"), "datum": e.get("datum"), "dauer": e.get("dauer"),
        "hinweis": e.get("hinweis"),
        "dateien": {"video": _absolut(e.get("video")), "thumbnail": _absolut(e.get("bild")),
                    "roh": _absolut(e.get("roh")), "ordner": e.get("ordner")},
        "links": {**({"youtube": e["youtube_link"]} if e.get("youtube_link") else {}), **(e.get("links") or {})},
        "texte": _texte(e),
    }


@mcp.tool(annotations=LESEN)
def faellige_uploads(bis: str | None = None) -> list[dict]:
    """Videos, deren Termin erreicht ist (oder bis zum Zeitpunkt 'bis', ISO wie 2026-10-22T18:00)
    und die auf mindestens einer geplanten Plattform noch nicht gepostet sind.
    Liefert je Video die offenen Plattformen, den Videopfad und die passenden Texte."""
    daten, stand = _laden()
    grenze = datetime.fromisoformat(bis) if bis else datetime.now()
    out = []
    for it in daten["items"]:
        e = _eintrag(it, stand)
        plan = e.get("plan") or {}
        if e.get("entfernt") or not plan.get("zeit"):
            continue
        if datetime.fromisoformat(plan["zeit"]) > grenze:
            continue
        fehler = e.get("fehler") or {}
        laeuft = e.get("upload_laeuft") or {}
        def _blockiert(p):
            if p in fehler:                       # wartet auf „Erneut versuchen“ im Board
                return True
            seit = laeuft.get(p)                  # ein anderer Lauf lädt gerade hoch
            return bool(seit) and (datetime.now() - datetime.fromisoformat(seit)).total_seconds() < 45 * 60
        offen = [p for p in plan.get("plattformen", []) if not e.get(p) and not _blockiert(p)]
        if not offen:
            continue
        texte = _texte(e)
        out.append({
            "id": e["id"], "titel": e.get("titel"), "termin": plan["zeit"], "offene_plattformen": offen,
            "video": _absolut(e.get("video")), "thumbnail": _absolut(e.get("bild")),
            "texte_je_plattform": {p: [t for t in texte if PLATTFORMEN[p].lower() in t["name"].lower()] for p in offen},
            "alle_texte": texte, "hinweis": e.get("hinweis"),
        })
    return out


@mcp.tool(annotations=LESEN)
def ideen_auflisten() -> list[dict]:
    """Alle gespeicherten Video-Ideen, neueste zuerst."""
    _, stand = _laden()
    return list(reversed(stand["ideen"]))


# ---------------------------------------------------------------- Schreiben
@mcp.tool(annotations=SCHREIBEN)
def stufe_setzen(video_id: str, stufe: str) -> str:
    """Video in eine Stufe verschieben: skript, aufgenommen (=Roh), schnitt, bereit, live.
    Häkchen bleiben, wie sie sind (Live geht auch mit nur einer Plattform)."""
    if stufe not in STUFEN:
        raise ValueError(f"Unbekannte Stufe '{stufe}'. Erlaubt: {', '.join(STUFEN)}")
    daten, stand = _laden(); e = _finden(daten, stand, video_id)
    felder = {"stage": stufe}
    if stufe not in ("bereit", "live"):
        felder.update({p: False for p in PLATTFORMEN})
    _setzen(video_id, felder)
    return f"„{e.get('titel')}“ steht jetzt in {STUFEN[stufe]}."


@mcp.tool(annotations=SCHREIBEN)
def als_gepostet_markieren(video_id: str, plattform: str, link: str | None = None) -> str:
    """Nach erfolgreichem Upload aufrufen: hakt die Plattform (tiktok oder youtube) ab, speichert optional
    den Link und schiebt das Video nach Live."""
    if plattform not in PLATTFORMEN:
        raise ValueError("plattform muss tiktok oder youtube sein")
    daten, stand = _laden(); e = _finden(daten, stand, video_id)
    felder = {plattform: True, "stage": "live", f"{plattform}_gepostet_am": datetime.now().isoformat(timespec="seconds")}
    if link:
        felder["links"] = {**(e.get("links") or {}), plattform: link}
    fehler = {k: v for k, v in (e.get("fehler") or {}).items() if k != plattform}
    laeuft = {k: v for k, v in (e.get("upload_laeuft") or {}).items() if k != plattform}
    felder["fehler"] = fehler or None
    felder["upload_laeuft"] = laeuft or None
    _setzen(video_id, felder)
    return f"„{e.get('titel')}“: {PLATTFORMEN[plattform]} abgehakt, Stufe Live."


@mcp.tool(annotations=SCHREIBEN)
def upload_beginnen(video_id: str, plattform: str) -> str:
    """Direkt vor dem Hochladen aufrufen. Markiert die Plattform 45 Minuten als 'läuft', damit kein zweiter
    Lauf dasselbe Video doppelt hochlädt."""
    if plattform not in PLATTFORMEN:
        raise ValueError("plattform muss tiktok oder youtube sein")
    daten, stand = _laden(); e = _finden(daten, stand, video_id)
    if e.get(plattform):
        raise ValueError(f"„{e.get('titel')}“ ist auf {PLATTFORMEN[plattform]} schon gepostet. Nicht nochmal hochladen.")
    _setzen(video_id, {"upload_laeuft": {**(e.get("upload_laeuft") or {}), plattform: datetime.now().isoformat(timespec="seconds")}})
    return f"Upload von „{e.get('titel')}“ auf {PLATTFORMEN[plattform]} als laufend markiert."


@mcp.tool(annotations=SCHREIBEN)
def upload_fehler_melden(video_id: str, plattform: str, meldung: str) -> str:
    """Wenn ein Upload nicht klappt: Grund kurz und verständlich auf Deutsch angeben (z. B. 'TikTok nicht eingeloggt',
    'falscher Kanal im Studio', 'Datei über 10 MB'). Der Nutzer sieht die Meldung im Board; das Video wird erst wieder
    versucht, wenn er dort 'Erneut versuchen' klickt."""
    if plattform not in PLATTFORMEN:
        raise ValueError("plattform muss tiktok oder youtube sein")
    daten, stand = _laden(); e = _finden(daten, stand, video_id)
    fehler = {**(e.get("fehler") or {}), plattform: {"meldung": meldung, "zeit": datetime.now().isoformat(timespec="seconds")}}
    laeuft = {k: v for k, v in (e.get("upload_laeuft") or {}).items() if k != plattform}
    _setzen(video_id, {"fehler": fehler, "upload_laeuft": laeuft or None})
    return f"Fehler bei „{e.get('titel')}“ ({PLATTFORMEN[plattform]}) im Board vermerkt."


@mcp.tool(annotations=SCHREIBEN)
def einplanen(video_id: str, zeit: str, plattformen: list[str]) -> str:
    """Termin setzen. zeit als ISO-Zeit ohne Zone (Ortszeit), z. B. 2026-10-22T18:00.
    plattformen: Liste aus tiktok, youtube. Ein Termin gilt als Ja des Nutzers zum Hochladen – nur auf seinen Wunsch setzen."""
    datetime.fromisoformat(zeit)
    falsch = [p for p in plattformen if p not in PLATTFORMEN]
    if falsch or not plattformen:
        raise ValueError("plattformen: mindestens eine aus tiktok, youtube")
    daten, stand = _laden(); e = _finden(daten, stand, video_id)
    _setzen(video_id, {"plan": {"zeit": zeit[:16], "plattformen": plattformen, "gesetzt_am": datetime.now().isoformat(timespec="seconds")}})
    return f"„{e.get('titel')}“ eingeplant für {zeit[:16]} auf {' + '.join(PLATTFORMEN[p] for p in plattformen)}."


@mcp.tool(annotations=SCHREIBEN)
def termin_loeschen(video_id: str) -> str:
    """Termin eines Videos entfernen."""
    daten, stand = _laden(); e = _finden(daten, stand, video_id)
    _setzen(video_id, {"plan": None})
    return f"Termin von „{e.get('titel')}“ gelöscht."


@mcp.tool(annotations=SCHREIBEN)
def text_bearbeiten(video_id: str, textname: str, neuer_text: str) -> str:
    """Einen Text (z. B. 'TikTok-Caption', 'YouTube-Titel') neu fassen. Das Original in data.json bleibt erhalten;
    im Board erscheint der Text als 'bearbeitet'."""
    daten, stand = _laden(); e = _finden(daten, stand, video_id)
    namen = [t["name"] for t in (e.get("texte") or [])]
    if textname not in namen:
        raise ValueError(f"Kein Text '{textname}'. Vorhanden: {', '.join(namen)}")
    _setzen(video_id, {"texte_neu": {**(e.get("texte_neu") or {}), textname: neuer_text}})
    return f"„{textname}“ von „{e.get('titel')}“ gespeichert."


@mcp.tool(annotations=SCHREIBEN)
def text_zuruecksetzen(video_id: str, textname: str) -> str:
    """Bearbeitete Fassung verwerfen, das Original gilt wieder."""
    daten, stand = _laden(); e = _finden(daten, stand, video_id)
    neu = dict(e.get("texte_neu") or {}); neu.pop(textname, None)
    _setzen(video_id, {"texte_neu": neu})
    return f"„{textname}“ wieder im Original."


@mcp.tool(annotations=SCHREIBEN)
def idee_hinzufuegen(text: str, quelle: str = "Agent") -> str:
    """Neue Video-Idee in den Ideen-Speicher legen."""
    _, stand = _laden()
    jetzt = datetime.now()
    ideen = stand["ideen"] + [{"id": str(int(jetzt.timestamp() * 1000)), "text": text, "quelle": quelle, "zeit": jetzt.isoformat(timespec="seconds")}]
    _post("api/ideen", {"ideen": ideen})
    return "Idee gespeichert."


@mcp.tool(annotations=SCHREIBEN)
def verwerfen(video_id: str) -> str:
    """Video aus dem Board nehmen (landet unter 'Verworfen', Dateien bleiben)."""
    daten, stand = _laden(); e = _finden(daten, stand, video_id)
    _setzen(video_id, {"entfernt": True, "entfernt_am": datetime.now().isoformat(timespec="seconds")})
    return f"„{e.get('titel')}“ verworfen."


@mcp.tool(annotations=SCHREIBEN)
def zurueckholen(video_id: str) -> str:
    """Verworfenes Video zurück ins Board holen."""
    daten, stand = _laden(); e = _finden(daten, stand, video_id)
    _setzen(video_id, {"entfernt": False})
    return f"„{e.get('titel')}“ ist wieder im Board."


# ---------------------------------------------------------------- Automatischer Schnitt
# Status: wartet → in_arbeit → rohschnitt_bereit (Nutzer) → rohschnitt_ok / korrektur → in_arbeit
#         → video_bereit (Nutzer) → fertig (Stufe Bereit) / korrektur_video → in_arbeit … ; fehler → (Nutzer: erneut) → vorher
AGENT_DRAN = {"wartet": "rohschnitt", "korrektur": "rohschnitt", "rohschnitt_ok": "video", "korrektur_video": "video"}


def _auto(e, **aenderung):
    a = dict(e.get("auto") or {})
    eintrag = aenderung.pop("_verlauf", None)
    a.update(aenderung)
    a["seit"] = datetime.now().isoformat(timespec="seconds")
    if eintrag:
        a["verlauf"] = (a.get("verlauf") or []) + [{"zeit": a["seit"], "agent": eintrag}]
    return {k: v for k, v in a.items() if v is not None}


@mcp.tool(annotations=LESEN)
def schnitt_auftraege() -> list[dict]:
    """Rohaufnahmen, an denen der Schnitt-Agent jetzt arbeiten soll. 'phase' sagt was: 'rohschnitt'
    (Roh-Schnitt + Storyboard bauen bzw. Korrektur daran umsetzen) oder 'video' (fertiges Video bauen bzw.
    Korrektur am Video umsetzen). Enthält Rohdatei, Hinweis/Korrektur des Nutzers, bisherigen Verlauf und den Arbeitsordner."""
    daten, stand = _laden()
    out = []
    for it in daten["items"]:
        e = _eintrag(it, stand)
        a = e.get("auto") or {}
        st = a.get("status")
        if e.get("entfernt") or not st:
            continue
        if st == "in_arbeit":
            alt = datetime.now() - datetime.fromisoformat(a.get("seit", "2000-01-01T00:00:00"))
            if alt.total_seconds() < 3 * 3600:
                continue                      # ein anderer Lauf arbeitet daran
            st = a.get("vorher") or "wartet"  # hängengebliebener Lauf: neu aufnehmen
        if st not in AGENT_DRAN:
            continue
        out.append({
            "id": e["id"], "titel": e.get("titel"), "status": st, "phase": AGENT_DRAN[st],
            "rohdatei": _absolut(e.get("roh")), "hinweis_von_nutzer": a.get("hinweis"),
            # Mehrere Anläufe (2026-10-21): weitere Rohdateien desselben Videos, in Aufnahme-Reihenfolge
            "weitere_rohdateien": [_absolut(p) for p in (e.get("roh_weitere") or [])],
            "korrektur_von_nutzer": a.get("korrektur") if st.startswith("korrektur") else None,
            "bisherige_vorschau": {k: _absolut(v) for k, v in (a.get("vorschau") or {}).items()},
            "arbeitsordner": _arbeitsordner(a, e),
            "verlauf": a.get("verlauf") or [],
        })
    return out


@mcp.tool(annotations=SCHREIBEN)
def schnitt_beginnen(video_id: str, schritt: str = "Transkribieren und Roh-Schnitt") -> str:
    """Direkt bevor du an einem Auftrag arbeitest: sperrt ihn 3 Stunden für andere Läufe und zeigt dem Nutzer im Board,
    woran du gerade bist."""
    daten, stand = _laden(); e = _finden(daten, stand, video_id)
    a = e.get("auto") or {}
    st = a.get("status")
    if st == "in_arbeit":
        st = a.get("vorher") or "wartet"
    if st not in AGENT_DRAN:
        raise ValueError(f"„{e.get('titel')}“ wartet nicht auf den Agenten (Status {a.get('status')}).")
    ordner = _arbeitsordner(a, e)
    Path(ordner).mkdir(parents=True, exist_ok=True)
    _setzen(video_id, {"auto": _auto(e, status="in_arbeit", vorher=st, schritt=schritt, arbeitsordner=ordner, meldung=None)})
    return f"Gestartet ({AGENT_DRAN[st]}). Arbeitsordner: {ordner}"


@mcp.tool(annotations=SCHREIBEN)
def schnitt_fortschritt(video_id: str, schritt: str) -> str:
    """Kurzen Zwischenstand für den Nutzer setzen, z. B. 'Grafiken rendern (3 von 5)'. Verlängert die Sperre."""
    daten, stand = _laden(); e = _finden(daten, stand, video_id)
    _setzen(video_id, {"auto": _auto(e, schritt=schritt)})
    return "Zwischenstand gesetzt."


@mcp.tool(annotations=SCHREIBEN)
def rohschnitt_vorlegen(video_id: str, rohschnitt_video: str, storyboard_bild: str, notiz: str = "") -> str:
    """Kontrollpunkt 1: Roh-Schnitt (MP4, ohne Grafik) und Storyboard (JPG/PNG) dem Nutzer im Board zur Freigabe vorlegen.
    Pfade absolut, Dateien müssen im Arbeitsordner liegen. notiz: kurz, was geschnitten wurde und was auffiel
    (z. B. Hook-Vorschlag, verdächtige Stellen, überzogene Aussagen)."""
    daten, stand = _laden(); e = _finden(daten, stand, video_id)
    vorschau = {**((e.get("auto") or {}).get("vorschau") or {}), "rohschnitt": _web(rohschnitt_video), "storyboard": _web(storyboard_bild)}
    _setzen(video_id, {"auto": _auto(e, status="rohschnitt_bereit", vorschau=vorschau, notiz=notiz or None,
                                     schritt=None, korrektur=None, _verlauf="Roh-Schnitt + Storyboard vorgelegt")})
    return f"„{e.get('titel')}“: Roh-Schnitt und Storyboard liegen dem Nutzer zur Freigabe vor."


@mcp.tool(annotations=SCHREIBEN)
def video_vorlegen(video_id: str, video: str, notiz: str = "", thumbnail: str | None = None,
                   titel: str | None = None, texte: list[dict] | None = None) -> str:
    """Kontrollpunkt 2: fertiges Video dem Nutzer vorlegen. Das Video kommt in die Stufe Schnitt und wird im Board
    abgespielt. Optional Thumbnail, besserer Titel und Posting-Texte als Liste [{"name": "TikTok-Caption", "text": …},
    {"name": "YouTube-Titel", …}, {"name": "YouTube-Beschreibung", …}, {"name": "YouTube-Tags", …},
    {"name": "Angepinnter Kommentar", …}]."""
    daten, stand = _laden(); e = _finden(daten, stand, video_id)
    felder = {"stage": "schnitt", "video": _web(video),
              "auto": _auto(e, status="video_bereit", notiz=notiz or None, schritt=None, korrektur=None, _verlauf="Fertiges Video vorgelegt")}
    if thumbnail:
        felder["bild"] = _web(thumbnail)
    if titel:
        felder["titel"] = titel
    if texte:
        if not all(isinstance(t, dict) and t.get("name") and isinstance(t.get("text"), str) for t in texte):
            raise ValueError("texte: Liste aus {name, text}")
        felder["texte"] = [{"name": t["name"], "text": t["text"]} for t in texte]
    _setzen(video_id, felder)
    return f"„{titel or e.get('titel')}“: fertiges Video liegt dem Nutzer in Schnitt zur Freigabe vor."


@mcp.tool(annotations=SCHREIBEN)
def schnitt_fehler_melden(video_id: str, meldung: str) -> str:
    """Wenn du nicht weiterkommst (Datei defekt, kein Ton, GPU belegt …): kurzer deutscher Grund. Der Nutzer sieht ihn
    im Board und kann 'Erneut versuchen' tippen."""
    daten, stand = _laden(); e = _finden(daten, stand, video_id)
    a = e.get("auto") or {}
    _setzen(video_id, {"auto": _auto(e, status="fehler", meldung=meldung, vorher=a.get("vorher") or "wartet",
                                     schritt=None, _verlauf="Fehler: " + meldung)})
    return "Fehler im Board vermerkt."


if __name__ == "__main__":
    mcp.run()
