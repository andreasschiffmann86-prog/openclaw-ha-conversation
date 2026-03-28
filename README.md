# OpenClaw Conversation Agent

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub release](https://img.shields.io/github/v/release/andreasschiffmann86-prog/openclaw-ha-conversation)](https://github.com/andreasschiffmann86-prog/openclaw-ha-conversation/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Bindet **OpenClaw (James)** als nativen Konversations-Agenten in Home Assistant ein.

- James erscheint als auswählbarer Agent neben Google Assistant, ChatGPT etc.
- Funktioniert mit Texteingabe **und** mit dem HA-Mikrofon-Button / HA Voice
- Optionaler Gerätezustand-Kontext: James weiß, was gerade an ist
- Vollständig über die HA-UI konfigurierbar — kein YAML nötig

---

## Voraussetzungen

| Anforderung | Version |
|---|---|
| Home Assistant | ≥ 2024.1 |
| HACS | ≥ 1.33.0 |
| OpenClaw-Instanz | erreichbar im lokalen Netzwerk |

---

## Installation via HACS

1. **HACS** → **Integrationen** → drei Punkte oben rechts → **Benutzerdefiniertes Repository hinzufügen**
2. URL: `https://github.com/andreasschiffmann86-prog/openclaw-ha-conversation`
3. Kategorie: **Integration**
4. **OpenClaw Conversation Agent** suchen und **Herunterladen** klicken
5. Home Assistant neu starten

## Manuelle Installation

```bash
# Im HA config-Verzeichnis ausführen
mkdir -p custom_components/openclaw_conversation
# Inhalt von custom_components/openclaw_conversation/ dorthin kopieren
```

Danach HA neu starten.

---

## Einrichtung

1. **Einstellungen** → **Geräte & Dienste** → **Integration hinzufügen** → **OpenClaw**
2. Felder ausfüllen:

| Feld | Beschreibung | Standard |
|---|---|---|
| API-URL | URL der OpenClaw-Instanz | `http://localhost:8080` |
| API-Schlüssel | Bearer-Token (optional) | — |
| Anzeigename | Name in HA | `James` |
| Timeout | Max. Wartezeit in Sekunden | `30` |
| Gerätezustand senden | Sendet HA-Entitäten als Kontext | aus |

3. **Speichern** — James erscheint jetzt unter
   **Einstellungen** → **Sprachassistenten** → Agenten-Auswahl

---

## Verwendung

### Texteingabe
Im HA-Dashboard oben rechts auf das Chat-Symbol klicken, Agent auf **James** wechseln, Nachricht tippen.

### Spracheingabe
Mikrofon-Button im Dashboard → sprechen → James antwortet (TTS übernimmt HA).

### HA Voice / Wyoming
James kann direkt als Konversations-Agent in einer Voice-Pipeline ausgewählt werden:
**Einstellungen** → **Sprachassistenten** → Pipeline bearbeiten → Konversations-Agent: **James**

---

## Erwartetes API-Format (OpenClaw-Seite)

### Request

```
POST /conversation
Content-Type: application/json
Authorization: Bearer <token>   (optional)

{
  "message": "Mach das Licht im Wohnzimmer an",
  "conversation_id": "ha-abc123",            // optional, für Session-Tracking
  "language": "de",
  "context": {                               // optional, wenn aktiviert
    "ha_entities": [
      {"entity_id": "light.wohnzimmer", "state": "off", "name": "Wohnzimmer Licht"}
    ]
  }
}
```

### Response

```json
{
  "response": "Das Licht im Wohnzimmer ist jetzt an.",
  "conversation_id": "ha-abc123"
}
```

---

## Versionierung & Releases

Dieses Projekt folgt [Semantic Versioning](https://semver.org/).

Für ein neues Release:
1. `version` in `custom_components/openclaw_conversation/manifest.json` erhöhen
2. Neuen Abschnitt in `CHANGELOG.md` hinzufügen
3. Git-Tag erstellen und pushen:
   ```bash
   git tag 1.1.0
   git push origin 1.1.0
   ```
4. GitHub Actions erstellt automatisch das Release — HACS erkennt es sofort.

---

## Roadmap

- **v1.0** — MVP: James antwortet auf Text & Sprache ✅
- **v1.1** — Gerätesteuerung: Actions aus API-Antwort ausführen
- **v1.2** — Diagnose-Endpunkt, erweiterte Fehlerdiagnose in HA

---

## Lizenz

MIT — siehe [LICENSE](LICENSE)
