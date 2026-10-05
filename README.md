# DaVinci RPC

Zeigt **DaVinci Resolve** als Discord Rich Presence an – inklusive Projekt, Timeline,
aktueller Page (Edit, Color, Fusion, …), Render-Fortschritt und Bearbeitungszeit.

```
Spielt DaVinci Resolve
Color Grading
Mein Kurzfilm · Timeline 1
⏱ 01:23:45 vergangen
```

## Funktionen

- Erkennt automatisch, wenn DaVinci Resolve gestartet/beendet wird
- Zeigt Projekt- und Timelinenamen (abschaltbar, z. B. für Kundenprojekte)
- Zeigt die aktive Page mit eigenem Icon
- Zeigt den Render-Fortschritt auf der Deliver-Page
- Verbindet sich automatisch neu, wenn Discord neu gestartet wird
- Basis-Modus ohne Scripting-API („DaVinci Resolve geöffnet“ + Zeit)
- Windows, macOS und Linux

## Voraussetzungen

- Python 3.10 oder neuer
- Discord-Desktop-App
- DaVinci Resolve (Free oder Studio)

## Einrichtung

### 1. Discord-Anwendung anlegen

1. Öffne das [Discord Developer Portal](https://discord.com/developers/applications) und klicke auf **New Application**.
2. Nenne sie **DaVinci Resolve** – dieser Name erscheint als „Spielt DaVinci Resolve“.
3. Kopiere die **Application ID** (unter *General Information*).
4. Unter **Rich Presence → Art Assets** folgende Bilder hochladen (Name = Asset-Key):

   | Asset-Key        | Inhalt                    |
   |------------------|---------------------------|
   | `davinci`        | DaVinci-Resolve-Logo      |
   | `page_media`     | Icon Media-Page (optional)|
   | `page_cut`       | Icon Cut-Page (optional)  |
   | `page_edit`      | Icon Edit-Page (optional) |
   | `page_fusion`    | Icon Fusion-Page (optional)|
   | `page_color`     | Icon Color-Page (optional)|
   | `page_fairlight` | Icon Fairlight-Page (optional)|
   | `page_deliver`   | Icon Deliver-Page (optional)|

   Ohne Page-Icons `use_page_icons` in der Konfiguration auf `false` setzen.
   Statt eines Asset-Keys kann `large_image` auch eine Bild-URL sein.

### 2. Konfiguration

`config.example.json` nach `config.json` kopieren und die Application ID eintragen:

```json
{
  "client_id": "123456789012345678"
}
```

| Option | Standard | Beschreibung |
|---|---|---|
| `client_id` | – | Discord Application ID (Pflicht) |
| `update_interval` | `15` | Sekunden zwischen Updates (min. 15, Discord-Limit) |
| `show_project` | `true` | Projektnamen anzeigen |
| `show_timeline` | `true` | Timelinenamen anzeigen |
| `show_page` | `true` | Aktive Page anzeigen |
| `show_elapsed_time` | `true` | Verstrichene Zeit anzeigen |
| `reset_timer_on_project_change` | `false` | Timer bei Projektwechsel zurücksetzen |
| `show_render_progress` | `true` | Render-Fortschritt anzeigen |
| `large_image` | `"davinci"` | Asset-Key oder URL des großen Bildes |
| `use_page_icons` | `true` | Kleines Page-Icon anzeigen |
| `buttons` | `[]` | Bis zu 2 Buttons: `[{"label": "Mein YouTube", "url": "https://..."}]` |

### 3. Resolve-Scripting aktivieren

Für Projekt, Timeline und Page braucht das Tool die Resolve-Scripting-API:

**DaVinci Resolve → Einstellungen → System → Allgemein → Externes Scripting verwenden: `Lokal`**

Ist die API nicht erreichbar (z. B. weil externes Scripting in deiner Resolve-Version
nicht verfügbar ist), läuft das Tool im Basis-Modus weiter.

> Hinweis: Die `fusionscript`-Bibliothek von Resolve unterstützt nicht jede
> Python-Version. Wenn die API nicht lädt, mit einer älteren Python-Version
> (z. B. 3.11/3.12) probieren und `-v` für Details verwenden.

### 4. Starten

**Windows:** Doppelklick auf `start.bat`

**Manuell:**

```bash
pip install -r requirements.txt
python -m davinci_rpc
```

Optionen: `--config PFAD`, `-v` (Debug-Ausgaben), `--version`.

## Mitmachen

Beiträge sind willkommen! Issues und Pull Requests gerne auf
[GitHub](https://github.com/Layconic/davinci-rpc).

Projektstruktur:

```
davinci_rpc/
  __main__.py   Hauptschleife & CLI
  config.py     Laden der config.json
  resolve.py    Prozesserkennung & Resolve-Scripting-API
  presence.py   Aufbau des Discord-Status & Verbindung
```

## Lizenz

[MIT](LICENSE). DaVinci Resolve ist eine Marke von Blackmagic Design.
Dieses Projekt steht in keiner Verbindung zu Blackmagic Design oder Discord.
