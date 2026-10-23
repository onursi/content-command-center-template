"""Erzeugt die Demodaten neu: Cover (JPG), kurze Testclips (MP4), ein Storyboard und demo/data.json + demo/state.json.

Alle Inhalte sind ausgedacht. Braucht Pillow und ffmpeg. Aufruf:  python demo/erzeugen.py
Die fertigen Dateien liegen schon im Repo; neu erzeugen musst du sie nur, wenn du sie ändern willst.
"""
import json
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HIER = Path(__file__).resolve().parent
MEDIA = HIER / "media"
HG, AKZENT, HELL, STILL = (18, 18, 20), (233, 160, 107), (242, 242, 244), (150, 150, 158)

VIDEOS = [
    ("live-ki-morgen", "3 KI-Tools, die mir jeden Morgen 30 Minuten sparen", "DEMO · LIVE"),
    ("bereit-downloads", "Download-Ordner aufräumen mit einem Satz", "DEMO · BEREIT"),
    ("schnitt-thumbnail", "Der eine Prompt für bessere Thumbnails", "DEMO · SCHNITT"),
]


def schrift(groesse, fett=True):
    for name in (["arialbd.ttf", "DejaVuSans-Bold.ttf"] if fett else ["arial.ttf", "DejaVuSans.ttf"]):
        for basis in ("C:/Windows/Fonts", "/usr/share/fonts/truetype/dejavu", "/Library/Fonts"):
            p = Path(basis) / name
            if p.is_file():
                return ImageFont.truetype(str(p), groesse)
    return ImageFont.load_default()


def umbrechen(d, text, font, breite):
    zeilen, z = [], ""
    for w in text.split():
        t = (z + " " + w).strip()
        if d.textlength(t, font=font) > breite and z:
            zeilen.append(z); z = w
        else:
            z = t
    return zeilen + [z]


def cover(ziel, titel, marke):
    img = Image.new("RGB", (720, 1280), HG)
    d = ImageDraw.Draw(img)
    for i in range(0, 1280, 64):                       # dezentes Raster
        d.line([(0, i), (720, i)], fill=(26, 26, 29))
    d.rounded_rectangle([60, 120, 300, 176], radius=28, fill=AKZENT)
    d.text((180, 148), marke, font=schrift(26), fill=HG, anchor="mm")
    f = schrift(78)
    y = 420
    for z in umbrechen(d, titel.upper(), f, 600):
        d.text((60, y), z, font=f, fill=HELL); y += 92
    d.rectangle([60, y + 30, 260, y + 42], fill=AKZENT)
    d.text((60, 1180), "Beispielvideo – ausgedachte Demodaten", font=schrift(28, False), fill=STILL)
    img.save(ziel, quality=86)


def clip(bild, ziel, sekunden=6):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-i", str(bild),
                    "-f", "lavfi", "-i", f"sine=frequency=330:duration={sekunden}",
                    "-t", str(sekunden), "-vf", "scale=540:960,fade=in:0:12,format=yuv420p",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "30", "-r", "24",
                    "-c:a", "aac", "-b:a", "48k", "-af", "volume=0.08", "-shortest", str(ziel)], check=True)


def storyboard(ziel):
    img = Image.new("RGB", (1600, 900), HG)
    d = ImageDraw.Draw(img)
    d.text((60, 50), "Storyboard (Demo)", font=schrift(44), fill=HELL)
    szenen = [("0,0 s", "Hook: „Dein Kaffee wird kalt …“", "Titelkarte"), ("3,2 s", "„… weil du Mails sortierst.“", "Zoom 110 %"),
              ("7,8 s", "„So macht es ein Agent.“", "Glas-Karte"), ("14,5 s", "„Link im Profil.“", "Profilkarte")]
    for i, (zeit, wort, grafik) in enumerate(szenen):
        x = 60 + i * 380
        d.rounded_rectangle([x, 150, x + 340, 750], radius=24, outline=(60, 60, 66), width=3)
        d.rectangle([x + 20, 170, x + 320, 500], fill=(30, 30, 34))
        d.text((x + 170, 335), f"Szene {i + 1}", font=schrift(34), fill=STILL, anchor="mm")
        d.text((x + 20, 530), zeit, font=schrift(30), fill=AKZENT)
        for j, z in enumerate(umbrechen(d, wort, schrift(26, False), 300)):
            d.text((x + 20, 580 + j * 34), z, font=schrift(26, False), fill=HELL)
        d.text((x + 20, 700), grafik, font=schrift(24, False), fill=STILL)
    img.save(ziel, quality=86)


def main():
    MEDIA.mkdir(exist_ok=True)
    for vid, titel, marke in VIDEOS:
        cover(MEDIA / f"{vid}.jpg", titel, marke)
        clip(MEDIA / f"{vid}.jpg", MEDIA / f"{vid}.mp4")
    cover(MEDIA / "roh-kaffee.jpg", "Dein Kaffee wird kalt – Roh-Schnitt", "DEMO · ROH")
    clip(MEDIA / "roh-kaffee.jpg", MEDIA / "roh-kaffee_rohschnitt.mp4", 5)
    storyboard(MEDIA / "roh-kaffee_storyboard.jpg")

    texte = lambda thema: [
        {"name": "TikTok-Caption", "text": f"Was würdest du zuerst automatisieren? 👇\n\n#ki #produktivität #{thema}"},
        {"name": "Angepinnter Kommentar", "text": "Welches Tool fehlt hier? Schreib es in die Kommentare."},
        {"name": "YouTube-Titel", "text": ""},
        {"name": "YouTube-Beschreibung", "text": "Beispieltext aus den Demodaten des Content Command Center."},
        {"name": "YouTube-Tags", "text": f"ki, produktivität, {thema}, demo"},
    ]
    items = []
    for (vid, titel, _), stufe, take, dauer in zip(VIDEOS, ["live", "bereit", "schnitt"], ["Take 2", "Take 1", "Upload"], ["24 s", "31 s", "19 s"]):
        t = texte(vid.split("-")[1]); t[2]["text"] = titel
        items.append({"id": vid, "titel": titel, "untertitel": "Ausgedachtes Beispielvideo", "take": take,
                      "stage": stufe, "datum": "2026-10-20", "dauer": dauer,
                      "bild": f"media_packages/{vid}.jpg", "video": f"media_packages/{vid}.mp4", "texte": t})
    items.append({"id": "roh-kaffee", "titel": "Dein Kaffee wird kalt", "untertitel": "Wird automatisch geschnitten",
                  "take": "Upload", "stage": "aufgenommen", "datum": "2026-10-22",
                  "bild": "media_packages/roh-kaffee.jpg", "roh": "media_packages/roh-kaffee_rohschnitt.mp4", "texte": []})
    items.append({"id": "skript-wochenplan", "titel": "Wochenplan in 60 Sekunden", "untertitel": "Skript, noch nicht aufgenommen",
                  "take": "Skript", "stage": "skript", "datum": "2026-10-23", "dauer": "ca. 45 s",
                  "texte": [{"name": "Teleprompter-Sprechtext", "prompter": True,
                             "text": "Sonntagabend, zehn Minuten. Ich sage meinem Agenten, was diese Woche wichtig ist. "
                                     "Er baut daraus einen Plan und erinnert mich nur, wenn etwas fällig ist. "
                                     "Kein Abo-Tool, nur ein Board auf meinem Rechner."},
                            {"name": "Regie- & Aufnahme-Hinweise", "text": "Hochformat, Blick in die Kamera, ein Anlauf reicht."}]})
    (HIER / "data.json").write_text(json.dumps({"stand": "demo", "items": items}, ensure_ascii=False, indent=1), encoding="utf-8")

    stand = {"items": {
        "live-ki-morgen": {"tiktok": True, "youtube": True, "tiktok_gepostet_am": "2026-10-21T18:02:11",
                           "youtube_gepostet_am": "2026-10-21T18:05:40",
                           "links": {"youtube": "https://www.youtube.com/shorts/BEISPIEL", "tiktok": "https://www.tiktok.com/@beispiel"}},
        "bereit-downloads": {"plan": {"zeit": "2030-01-15T18:00", "plattformen": ["tiktok", "youtube"], "gesetzt_am": "2026-10-22T09:00:00"}},
        "schnitt-thumbnail": {"auto": {"status": "video_bereit", "seit": "2026-10-22T14:10:00",
                                       "notiz": "Fertig gerendert, 19 s. Hook auf den ersten Satz gezogen. Bitte Ende prüfen.",
                                       "verlauf": [{"zeit": "2026-10-22T11:00:00", "agent": "Roh-Schnitt + Storyboard vorgelegt"},
                                                   {"zeit": "2026-10-22T11:30:00", "du": "Roh-Schnitt freigegeben"},
                                                   {"zeit": "2026-10-22T14:10:00", "agent": "Fertiges Video vorgelegt"}]}},
        "roh-kaffee": {"auto": {"status": "rohschnitt_bereit", "seit": "2026-10-23T09:20:00",
                                "notiz": "Länge 48 s → 17 s. Hook-Vorschlag: „Dein Kaffee wird kalt, weil du Mails sortierst.“ Satz bei 0:12 klingt übertrieben, bitte prüfen.",
                                "vorschau": {"rohschnitt": "media_packages/roh-kaffee_rohschnitt.mp4",
                                             "storyboard": "media_packages/roh-kaffee_storyboard.jpg"},
                                "verlauf": [{"zeit": "2026-10-23T09:20:00", "agent": "Roh-Schnitt + Storyboard vorgelegt"}]}},
    }, "ideen": [
        {"id": "1", "text": "Vorher/Nachher: ein Tag ohne und mit Agent", "quelle": "Demo", "zeit": "2026-10-20T08:00:00"},
        {"id": "2", "text": "Die drei Fehler, die ich beim ersten MCP gemacht habe", "quelle": "Demo", "zeit": "2026-10-21T20:15:00"},
    ]}
    (HIER / "state.json").write_text(json.dumps(stand, ensure_ascii=False, indent=1), encoding="utf-8")
    print("Demodaten erzeugt:", ", ".join(p.name for p in sorted(MEDIA.iterdir())))


if __name__ == "__main__":
    if not shutil.which("ffmpeg"):
        raise SystemExit("ffmpeg fehlt")
    main()
