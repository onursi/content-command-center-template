# Eigene TikTok-App für öffentliches Posten

**Wozu?** Ohne eigene, von TikTok geprüfte App kann kein Programm öffentlich auf TikTok posten. Videos landen dann nur
als Entwurf im TikTok-Eingang (Weg B im README) oder bleiben privat. Mit eigener App und bestandener Prüfung postet der
Upload-Agent direkt öffentlich (Weg C).

**Ehrlich vorab:**
- Die Einrichtung dauert etwa eine Stunde. Danach prüft TikTok die App, das kann Tage bis Wochen dauern. Eine Zusage gibt es nicht.
- Bis zur Prüfung sind Uploads über die App nur **privat** („Nur ich“) sichtbar.
- Du brauchst eine eigene Website mit **Nutzungsbedingungen** und **Datenschutzerklärung**, eine Domain, bei der du DNS-Einträge
  setzen kannst, und ein kurzes **Demo-Video**, das zeigt, wie deine App TikTok nutzt.
- Das TikTok-Entwicklerportal ändert sich ab und zu. Heißt ein Knopf anders, such nach dem sinngemäßen Begriff.

## 1. Entwicklerkonto und App anlegen

1. Auf https://developers.tiktok.com mit deinem TikTok-Konto anmelden.
2. **Manage apps → Connect an app**. Als Typ „Individual“ wählen, wenn du keine Firma hast.
3. Grunddaten eintragen:
   - **App-Name** (z. B. dein Kanalname) und **App-Icon** (1024 × 1024 px, PNG)
   - **Kategorie** und eine kurze **Beschreibung**: „Lädt meine eigenen, fertig geschnittenen Videos nach meiner Freigabe
     auf mein eigenes Konto hoch.“
   - **Terms of Service URL** und **Privacy Policy URL** von deiner Website
   - **Plattform: Web**, Website-URL deiner Domain

## 2. Domain bestätigen

Bei **URL properties / Verify domain** deine Domain eintragen. TikTok zeigt einen TXT-Eintrag. Den bei deinem
Domain-Anbieter (z. B. Cloudflare) als DNS-TXT-Eintrag anlegen, ein paar Minuten warten, dann auf **Verify** klicken.

## 3. Produkte hinzufügen

Unter **Products → Add products**:

- **Login Kit:** Als **Redirect URI** die Adresse des Dienstes eintragen, der die Anmeldung abwickelt. Bei Composio steht sie in
  der Composio-Oberfläche beim TikTok-Zugang (eigene Zugangsdaten / „custom auth“).
- **Content Posting API:** einschalten und **Direct Post** aktivieren. Ohne Direct Post gibt es nur Entwürfe.

## 4. Berechtigungen (Scopes)

Unter **Scopes** diese anhaken:

| Scope | Wofür |
|---|---|
| `user.info.basic` | Name und Profilbild, um das richtige Konto zu prüfen |
| `video.upload` | Video als Entwurf hochladen |
| `video.publish` | Video direkt veröffentlichen |
| `video.list` | eigene Videos auflisten, um den Link fürs Board zu holen |

Optional: `user.info.profile`, `user.info.stats` für Statistiken. Nimm nur, was du wirklich brauchst. Jeder Scope muss in der Prüfung begründet werden.

## 5. Erst in der Sandbox testen

1. Oben auf **Sandbox** wechseln und eine Sandbox anlegen.
2. Unter **Target users** dein eigenes TikTok-Konto hinzufügen.
3. **Client key** und **Client secret** der Sandbox in Composio beim TikTok-Zugang eintragen. Nicht in `config.json`, nicht ins Repo,
   nicht in einen Chat kopieren.
4. In Claude Code testen: „Verbinde TikTok über Composio und lies mein Profil.“ Kommt dein Kontoname zurück, steht die Verbindung.
5. Testupload: ein kurzes Video mit `privacy_level: SELF_ONLY`. Es erscheint privat in deinem Profil.

## 6. Zur Prüfung einreichen

1. Auf **Production** wechseln. Dieselben Angaben, Produkte und Scopes wie in der Sandbox.
2. **Demo-Video** aufnehmen (1–3 Minuten Bildschirmaufnahme). Darin zeigen:
   - wie du dich über deine App bei TikTok anmeldest,
   - das Board mit einem fertigen Video und deinem Termin,
   - wie der Agent hochlädt und das Video danach im Profil erscheint.
3. Jeden Scope in einem Satz begründen, z. B. `video.publish`: „Veröffentlicht nur Videos, die ich im Board freigegeben und
   terminiert habe, auf meinem eigenen Konto.“
4. **Submit for review**. Antwort kommt per E-Mail. Bei Ablehnung steht der Grund dabei; nachbessern und neu einreichen.

## 7. Nach der Freigabe

1. Client key und Secret der **Production**-App in Composio eintragen (die Sandbox-Werte ersetzen) und TikTok neu verbinden.
2. Im Upload-Auftrag `geplante-aufgaben/upload.md` beim TikTok-Weg `publish: true` erlauben und die Caption mitgeben.
3. Einen Testpost mit einem unwichtigen Video machen, danach den Agenten normal laufen lassen.

## Häufige Stolpersteine

- **„Production lässt sich nicht speichern“:** meist fehlt das Demo-Video oder eine URL (Nutzungsbedingungen, Datenschutz) ist nicht erreichbar.
- **Redirect-Fehler bei der Anmeldung:** Die Redirect URI in TikTok muss exakt der Adresse in Composio entsprechen, inklusive `https://` und Schrägstrich am Ende.
- **Video bleibt privat:** Die App ist noch nicht geprüft, oder das Konto ist privat gestellt.
- **Upload bricht ab:** TikTok verlangt MP4/MOV, mindestens 3 Sekunden. Sehr große Dateien in Stücken hochladen (macht Composio selbst).
