# OpenClaw Home Assistant Conversation Agent — Detaillierte Spezifikation

## Projektübersicht

**Ziel:** Eine HACS-kompatible Home Assistant Custom Integration, die OpenClaw (James) als nativen Konversations-Agenten in Home Assistant einbindet.

**Kurzname:** `openclaw_conversation`
**Verzeichnis:** `custom_components/openclaw_conversation/`
**HACS-Kategorie:** Integration

---

## 1. Funktionale Anforderungen

### 1.1 Konversations-Agent
- OpenClaw erscheint in HA unter **Einstellungen → Sprachassistenten** als auswählbarer Konversations-Agent (gleichwertig zu Google Assistant, ChatGPT etc.)
- Der Agent nimmt Texteingaben und Spracheingaben entgegen und liefert Textantworten zurück
- HA verarbeitet die Sprachausgabe (TTS) eigenständig — die Integration liefert nur Text

### 1.2 Sprachsteuerung
- Funktioniert mit dem HA-Mikrofon-Button im Dashboard
- Kompatibel mit **HA Voice** (Wyoming-Pipeline)
- Nutzer kann sagen: „Frag James, mach das Licht im Wohnzimmer an" und James antwortet und steuert optional Geräte

### 1.3 Gerätesteuerung (optional, Phase 2)
- James kann HA-Service-Calls auslösen (z.B. `light.turn_on`, `switch.toggle`)
- James erhält Kontext über den aktuellen HA-Zustand (Gerätestatus, Entitäten) via HA-API
- Antwort enthält sowohl Aktionsergebnis als auch natürlichsprachliche Bestätigung

### 1.4 Konfiguration
- Konfiguration ausschließlich über die HA-UI (Config Flow), keine manuelle YAML-Bearbeitung nötig
- Konfigurierbare Felder:
  - **API-URL** der OpenClaw-Instanz (z.B. `http://192.168.1.100:8080`)
  - **API-Key** (optional, für Authentifizierung)
  - **Agent-Name** (Anzeigename, Standard: „James")
  - **Timeout** in Sekunden (Standard: 30)
  - **Kontext senden** (Bool): Ob HA-Gerätestatus mitgeschickt wird

---

## 2. Technische Architektur

### 2.1 Verzeichnisstruktur

```
custom_components/openclaw_conversation/
├── __init__.py              # Integration-Setup, Config-Entry-Handling
├── manifest.json            # HACS-Manifest (version, requirements, dependencies)
├── config_flow.py           # UI-Konfigurationsflow (ConfigFlow + OptionsFlow)
├── const.py                 # Konstanten (Domain, Default-Werte)
├── conversation.py          # ConversationEntity — Kern der Integration
├── api.py                   # HTTP-Client für OpenClaw-API
├── strings.json             # UI-Texte (Englisch)
└── translations/
    ├── en.json              # Englische Übersetzungen
    └── de.json              # Deutsche Übersetzungen

hacs.json                    # HACS-Repository-Metadaten
```

### 2.2 HA-Integration-Schnittstelle

Die Integration implementiert `homeassistant.components.conversation.ConversationEntity` (HA Core ab 2023.x):

```python
class OpenClawConversationEntity(ConversationEntity):
    async def async_process(
        self, user_input: ConversationInput
    ) -> ConversationResult:
        ...
```

**Eingabe (`ConversationInput`):**
- `text`: Transkribierter Text der Nutzereingabe
- `conversation_id`: ID für Mehrschritt-Konversationen (Session-Tracking)
- `language`: Sprachcode (z.B. `de`, `en`)
- `agent_id`: ID dieses Agenten

**Ausgabe (`ConversationResult`):**
- `response.speech.plain.speech`: Antworttext für TTS
- `response.response_type`: `ACTION_DONE` | `QUERY_ANSWER` | `ERROR`

### 2.3 OpenClaw API-Anbindung

**Endpunkt (Phase 1 — Basis):**
```
POST {API_URL}/conversation
Content-Type: application/json
Authorization: Bearer {API_KEY}

{
  "message": "Mach das Licht an",
  "conversation_id": "ha-session-abc123",
  "language": "de",
  "context": {                          // optional (wenn aktiviert)
    "ha_entities": [
      {"entity_id": "light.wohnzimmer", "state": "off", "name": "Wohnzimmer Licht"}
    ]
  }
}
```

**Erwartete Antwort:**
```json
{
  "response": "Das Licht im Wohnzimmer ist jetzt an.",
  "actions": [                          // optional (Phase 2)
    {"service": "light.turn_on", "entity_id": "light.wohnzimmer"}
  ]
}
```

**Fehlerbehandlung:**
- Timeout → Fehlermeldung auf Deutsch/Englisch je nach HA-Sprache
- HTTP 4xx/5xx → Fehlermeldung mit Status-Code
- Netzwerkfehler → Fallback-Text + Logging

### 2.4 Manifest (`manifest.json`)

```json
{
  "domain": "openclaw_conversation",
  "name": "OpenClaw Conversation Agent",
  "version": "1.0.0",
  "documentation": "https://github.com/andreasschiffmann86-prog/openclaw-ha-conversation",
  "issue_tracker": "https://github.com/andreasschiffmann86-prog/openclaw-ha-conversation/issues",
  "requirements": ["aiohttp>=3.9.0"],
  "dependencies": ["conversation"],
  "codeowners": ["@andreasschiffmann86-prog"],
  "iot_class": "cloud_polling",
  "config_flow": true
}
```

### 2.5 HACS-Metadaten (`hacs.json`)

```json
{
  "name": "OpenClaw Conversation Agent",
  "render_readme": true
}
```

---

## 3. Implementierungsphasen

### Phase 1 — MVP (Minimal Viable Product)
**Ziel:** James antwortet auf Texteingaben in HA

| Aufgabe | Datei | Priorität |
|---|---|---|
| Manifest + hacs.json erstellen | `manifest.json`, `hacs.json` | Hoch |
| Konstanten definieren | `const.py` | Hoch |
| Config Flow (UI-Setup) | `config_flow.py` | Hoch |
| API-Client (async HTTP) | `api.py` | Hoch |
| ConversationEntity implementieren | `conversation.py` | Hoch |
| Integration registrieren | `__init__.py` | Hoch |
| Übersetzungen (DE + EN) | `translations/` | Mittel |
| README mit Installationsanleitung | `README.md` | Mittel |

**Akzeptanzkriterium:** James erscheint in HA als Konversations-Agent, nimmt Text entgegen, sendet ihn an OpenClaw-API und gibt die Antwort zurück.

### Phase 2 — Gerätesteuerung
**Ziel:** James kann HA-Geräte steuern

| Aufgabe | Details |
|---|---|
| HA-Entitäten-Kontext aufbauen | Zustand relevanter Entitäten an API mitschicken |
| Actions aus API-Antwort ausführen | `hass.services.async_call()` für empfangene Actions |
| Sicherheits-Whitelist | Nur erlaubte Domains/Services ausführbar (konfigurierbar) |

### Phase 3 — Erweiterungen
- Konversations-Verlauf / Session-Management
- HA-Notifications als Antwortkanal
- Dashboard-Karte (Lovelace) für Direktzugriff
- Diagnose-Endpoint für HACS

---

## 4. Sicherheitsanforderungen

- API-Key wird verschlüsselt im HA-Credential-Store gespeichert (nicht in `config_entries`)
- Alle HTTP-Requests gehen über `async with aiohttp.ClientSession()` (kein blocking I/O)
- Bei Gerätesteuerung (Phase 2): Whitelist für erlaubte HA-Domains (Standard: `light`, `switch`, `climate`, `cover`)
- Kein direktes Ausführen von beliebigem Code aus API-Antworten

---

## 5. Kompatibilität

| Anforderung | Version |
|---|---|
| Home Assistant | >= 2023.8 (ConversationEntity stabil) |
| Python | >= 3.11 |
| HACS | >= 1.33.0 |
| HA Voice / Wyoming | kompatibel (kein Zusatzaufwand) |

---

## 6. Testplan

### 6.1 Manuelle Tests
- [ ] Integration über HACS installierbar
- [ ] Config Flow zeigt alle Felder korrekt
- [ ] Agent erscheint unter Einstellungen → Sprachassistenten
- [ ] Texteingabe im HA-Chat → Antwort von James erscheint
- [ ] Spracheingabe via Mikrofon-Button → Antwort wird vorgelesen
- [ ] Fehlerfall: Falsche API-URL → verständliche Fehlermeldung
- [ ] Fehlerfall: Timeout → Fehlermeldung ohne HA-Absturz

### 6.2 Automatisierte Tests (Phase 2)
- Unit-Tests für `api.py` mit Mock-HTTP-Responses
- Integration-Tests mit HA-Test-Framework (`pytest-homeassistant-custom-component`)

---

## 7. Installationsablauf (Endnutzer)

1. HACS öffnen → Integrationen → Benutzerdefiniertes Repository hinzufügen
2. URL: `https://github.com/andreasschiffmann86-prog/openclaw-ha-conversation`
3. Kategorie: Integration
4. „OpenClaw Conversation Agent" installieren → HA neu starten
5. Einstellungen → Geräte & Dienste → Integration hinzufügen → „OpenClaw"
6. API-URL und optionalen API-Key eingeben → Speichern
7. Einstellungen → Sprachassistenten → Neuen Assistenten erstellen → Konversations-Agent: „James" wählen

---

## 8. Offene Fragen

- [ ] Welches API-Format verwendet die OpenClaw-Instanz (REST/JSON, WebSocket, anderes)?
- [ ] Soll Konversations-History serverseitig (OpenClaw) oder clientseitig (HA) verwaltet werden?
- [ ] Authentifizierungsmethode: Bearer Token, Basic Auth, oder kein Auth?
- [ ] Soll Phase 2 (Gerätesteuerung) von OpenClaw koordiniert werden oder direkt in der HA-Integration?
