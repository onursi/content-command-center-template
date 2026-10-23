import http.server
import socketserver
import os
import sys
import re
import posixpath
import urllib.parse
from pathlib import Path
import traceback
import time
import json
import threading
import agent_ausloeser   # startet Agenten nur bei echter Arbeit
import einstellungen as E

WEB_DIR = E.HIER
UPLOAD_DIR = E.UPLOAD_DIR      # Rohaufnahmen aus dem Board
DATA_FILE = E.DATA_FILE
STATE_FILE = E.STATE_FILE
MAX_UPLOAD = 8 * 1024 ** 3

PORT = E.PORT
HOST = E.HOST
LOG_FILE = WEB_DIR / "server.log"
# Nur diese Dateien aus dem Programmordner werden ausgeliefert (kein Zugriff auf .env, config.json, Code)
OEFFENTLICH = {"/", "/index.html", "/data.json", "/manifest.json", "/favicon.ico", "/favicon-16x16.png",
               "/favicon-32x32.png", "/icon-192.png", "/icon-512.png", "/apple-touch-icon.png", "/command-center.ico"}
STATE_LOCK = threading.Lock()

if sys.stderr is None:
    sys.stderr = open(WEB_DIR / "stderr.log", "a", encoding="utf-8")
if sys.stdout is None:
    sys.stdout = open(WEB_DIR / "stdout.log", "a", encoding="utf-8")

def log(msg):
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except Exception:
        pass

def read_state():
    try:
        s = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        s = {}
    s.setdefault("items", {}); s.setdefault("ideen", [])
    return s

def write_state(state):
    body = json.dumps(state, ensure_ascii=False, indent=1).encode("utf-8")
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_bytes(body)
    os.replace(tmp, STATE_FILE)

class MediaStreamingHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_DIR), **kwargs)

    def log_message(self, format, *args):
        log("%s - - [%s] %s" % (self.client_address[0], self.log_date_time_string(), format % args))

    def translate_path(self, path):
        clean = posixpath.normpath(urllib.parse.unquote(path.split("?")[0]))   # "/fonts/../x" -> "/x"
        for prefix, base in E.MEDIEN:
            prefix = "/" + prefix
            if clean.startswith(prefix):
                target = (base / clean[len(prefix):].lstrip("/")).resolve()
                if base.resolve() not in target.parents:
                    return str(base / "__gesperrt__")
                return str(target)
        if clean == "/data.json":
            return str(DATA_FILE)
        if clean not in OEFFENTLICH and not clean.startswith("/fonts/"):
            return str(WEB_DIR / "__gesperrt__")
        return super().translate_path(clean)

    # Gemeinsamer Stand (Pipeline-Stufen, Häkchen, Ideen) für Handy und PC
    def do_GET(self):
        if self.path.split("?")[0].endswith("/api/config"):
            body = json.dumps({"anzeigename": E.ANZEIGENAME, "agent_aktiv": E.AGENT_AKTIV}, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path.split("?")[0].endswith("/api/state"):
            body = STATE_FILE.read_bytes() if STATE_FILE.is_file() else b"{}"
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()

    def upload(self):
        """POST /api/upload?name=<dateiname>&titel=<titel> – Rohaufnahme als Rohdaten im Body (gestreamt).
        Legt die Datei in UPLOAD_DIR ab und einen neuen Eintrag (Stufe Roh, Auto-Schnitt wartet) in data.json an."""
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        name = (q.get("name") or ["aufnahme.mov"])[0]
        titel = (q.get("titel") or [""])[0].strip()[:120]
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0 or n > MAX_UPLOAD:
            self.send_error(413); return
        ext = Path(name).suffix.lower()
        if ext not in (".mov", ".mp4", ".m4v", ".webm"):
            self.send_error(415, "nur Videodateien"); return
        stamp = time.strftime("%Y-%m-%d_%H%M%S")
        stamm = re.sub(r"[^A-Za-z0-9_-]+", "_", Path(name).stem)[:40] or "aufnahme"
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        ziel = UPLOAD_DIR / f"{stamp}_{stamm}{ext}"
        tmp = ziel.with_suffix(ext + ".part")
        rest = n
        with open(tmp, "wb") as f:
            while rest > 0:
                chunk = self.rfile.read(min(rest, 1024 * 1024))
                if not chunk:
                    break
                f.write(chunk); rest -= len(chunk)
        if rest > 0:
            tmp.unlink(missing_ok=True); self.send_error(400, "Upload abgebrochen"); return
        os.replace(tmp, ziel)
        # Mehrere Anläufe (2026-10-21): ?zu=<id> hängt diese Datei als weiteren Anlauf an ein bestehendes Video an
        zu = (q.get("zu") or [""])[0].strip()
        if zu:
            with STATE_LOCK:
                daten = json.loads(DATA_FILE.read_text(encoding="utf-8"))
                item = next((i for i in daten.get("items", []) if i["id"] == zu), None)
                if item is None:
                    self.send_error(404, "Video unbekannt"); return
                item.setdefault("roh_weitere", []).append(f"media_uploads/{ziel.name}")
                t2 = DATA_FILE.with_suffix(".tmp"); t2.write_text(json.dumps(daten, ensure_ascii=False, indent=1), encoding="utf-8"); os.replace(t2, DATA_FILE)
            log(f"Upload {ziel.name} ({n} Bytes) -> weiterer Anlauf für {zu}")
            body = json.dumps({"id": zu, "datei": ziel.name}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        mehr = (q.get("mehr") or [""])[0] == "1"   # weitere Anläufe folgen: Agent wartet, bis das Board „wartet“ setzt
        iid = "upload-" + time.strftime("%Y%m%d-%H%M%S")
        eintrag = {"id": iid, "titel": titel or "Neue Rohaufnahme", "untertitel": "Wird automatisch geschnitten",
                   "take": "Upload", "stage": "aufgenommen", "datum": time.strftime("%Y-%m-%d"),
                   "roh": f"media_uploads/{ziel.name}", "texte": []}
        with STATE_LOCK:
            daten = json.loads(DATA_FILE.read_text(encoding="utf-8"))
            daten.setdefault("items", []).insert(0, eintrag)
            t2 = DATA_FILE.with_suffix(".tmp"); t2.write_text(json.dumps(daten, ensure_ascii=False, indent=1), encoding="utf-8"); os.replace(t2, DATA_FILE)
            state = read_state()
            state["items"][iid] = {"auto": {"status": "hochladen" if mehr else "wartet", "seit": time.strftime("%Y-%m-%dT%H:%M:%S")}}
            write_state(state)
        agent_ausloeser.wecken()
        log(f"Upload {ziel.name} ({n} Bytes) -> {iid}")
        body = json.dumps({"id": iid, "datei": ziel.name}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def bild_upload(self):
        """POST /api/bild?id=<video_id>&name=<datei> – neues Thumbnail (jpg/png/webp) für ein Video.
        Speichert als JPG unter UPLOAD_DIR/thumbnails, merkt sich das alte Bild in bild_vorher."""
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        iid = (q.get("id") or [""])[0]
        name = (q.get("name") or ["bild.jpg"])[0]
        n = int(self.headers.get("Content-Length") or 0)
        ext = Path(name).suffix.lower()
        if not iid or n <= 0 or n > 30 * 1024 ** 2:
            self.send_error(413); return
        if ext not in (".jpg", ".jpeg", ".png", ".webp"):
            self.send_error(415, "nur JPG, PNG oder WebP"); return
        ordner = UPLOAD_DIR / "thumbnails"; ordner.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y-%m-%d_%H%M%S")
        roh = ordner / f"{re.sub(r'[^A-Za-z0-9_-]+', '_', iid)}_{stamp}{ext}"
        roh.write_bytes(self.rfile.read(n))
        ziel = roh.with_suffix(".jpg")
        if ext != ".jpg":
            import subprocess
            r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(roh), "-q:v", "2", str(ziel)],
                               capture_output=True, creationflags=0x08000000)
            if r.returncode != 0 or not ziel.is_file():
                self.send_error(500, "Umwandlung in JPG fehlgeschlagen"); return
            roh.unlink(missing_ok=True)
        web = f"media_uploads/thumbnails/{ziel.name}"
        with STATE_LOCK:
            daten = json.loads(DATA_FILE.read_text(encoding="utf-8"))
            orig = next((i for i in daten.get("items", []) if i["id"] == iid), None)
            if orig is None:
                self.send_error(404, "Video unbekannt"); return
            state = read_state()
            e = state["items"].setdefault(iid, {})
            if "bild_vorher" not in e:
                e["bild_vorher"] = e.get("bild") or orig.get("bild") or ""
            e["bild"] = web
            write_state(state)
        log(f"Thumbnail {ziel.name} -> {iid}")
        body = json.dumps({"bild": web}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        route = self.path.split("?")[0]
        if route.endswith("/api/upload"):
            return self.upload()
        if route.endswith("/api/bild"):
            return self.bild_upload()
        if not any(route.endswith(r) for r in ("/api/state", "/api/item", "/api/ideen")):
            self.send_error(404); return
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0 or n > 2_000_000:
            self.send_error(413); return
        try:
            data = json.loads(self.rfile.read(n).decode("utf-8"))
            if not isinstance(data, dict):
                raise ValueError("kein Objekt")
        except Exception as e:
            self.send_error(400, str(e)); return
        with STATE_LOCK:
            if route.endswith("/api/state"):
                # alte Fassung: ganzer Stand (bleibt für Kompatibilität)
                state = data
            else:
                state = read_state()
                if route.endswith("/api/item"):
                    # {"id": "...", "set": {...}} – führt nur die Felder dieses Eintrags zusammen
                    iid, felder = data.get("id"), data.get("set")
                    if not isinstance(iid, str) or not isinstance(felder, dict):
                        self.send_error(400, "id und set noetig"); return
                    eintrag = state["items"].setdefault(iid, {})
                    for k, v in felder.items():
                        if v is None:
                            eintrag.pop(k, None)
                        else:
                            eintrag[k] = v
                else:
                    # {"ideen": [...]} – ersetzt nur die Ideenliste
                    if not isinstance(data.get("ideen"), list):
                        self.send_error(400, "ideen noetig"); return
                    state["ideen"] = data["ideen"]
            write_state(state)
        agent_ausloeser.wecken()
        self.send_response(204)
        self.end_headers()

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def send_head(self):
        self.remaining = None
        raw_path = self.translate_path(self.path)
        path = Path(raw_path)

        if not path.is_file():
            return super().send_head()

        ext = path.suffix.lower()
        # Handle streaming for videos and media files
        if ext in (".mp4", ".mov", ".m4v", ".webm", ".jpg", ".jpeg", ".png", ".md", ".txt", ".json"):
            if ext == ".mp4":
                ctype = "video/mp4"
            elif ext == ".mov":
                ctype = "video/quicktime"
            elif ext == ".md":
                ctype = "text/markdown; charset=utf-8"
            else:
                ctype = self.guess_type(str(path))

            size = path.stat().st_size
            start = 0
            end = size - 1
            r = self.headers.get("Range")
            
            if r:
                m = re.fullmatch(r"bytes=(\d*)-(\d*)", r)
                if not m or not any(m.groups()):
                    self.send_error(416)
                    return None
                if m[1]:
                    start = int(m[1])
                    end = min(int(m[2]) if m[2] else end, end)
                else:
                    start = max(0, size - int(m[2]))
                if start > end or start >= size:
                    self.send_response(416)
                    self.send_header("Content-Range", f"bytes */{size}")
                    self.end_headers()
                    return None

            try:
                f = open(path, "rb")
                f.seek(start)
            except OSError:
                self.send_error(404, "File not found")
                return None

            self.remaining = end - start + 1
            self.send_response(206 if r else 200)
            self.send_header("Content-Type", ctype)
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(self.remaining))
            
            if r:
                self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            
            # Check for direct download parameter
            if "download=1" in self.path:
                filename = path.name
                self.send_header("Content-Disposition", f'attachment; filename="{filename}"')

            self.end_headers()
            return f

        return super().send_head()

    def copyfile(self, source, outputfile):
        if getattr(self, "remaining", None) is not None:
            bytes_to_copy = self.remaining
            buf_size = 128 * 1024
            while bytes_to_copy > 0:
                chunk = source.read(min(bytes_to_copy, buf_size))
                if not chunk:
                    break
                try:
                    outputfile.write(chunk)
                except (BrokenPipeError, ConnectionResetError):
                    break
                bytes_to_copy -= len(chunk)
        else:
            super().copyfile(source, outputfile)

class ThreadingTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True

if __name__ == "__main__":
    try:
        os.chdir(str(WEB_DIR))
        E.erster_start()
        log(f"Starting Threading Media Server on {HOST}:{PORT}")
        agent_ausloeser.starten(log)
        with ThreadingTCPServer((HOST, PORT), MediaStreamingHandler) as httpd:
            log("Media Server listening successfully.")
            httpd.serve_forever()
    except Exception as e:
        log(f"Server exception: {e}\n{traceback.format_exc()}")
