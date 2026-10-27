# Lyrics Studio

Lokale Desktop-Anwendung für Songtexte und ihr Timing: Songs importieren, Whisper-Vorschläge prüfen und korrigieren, Projekte speichern und bestätigte Passagen exportieren. Der Editor ist direkt eingebettet; ein zusätzlicher Browser ist nicht nötig.

## Windows herunterladen

**Aktuelle Version: 0.6.1 · Windows x64**

- [Installer herunterladen](https://github.com/yasmin78-gif/LyricsStudio/releases/download/v0.6.1/LyricsStudio-0.6.1-Windows-x64-Setup.exe)
- [Alle Downloads, portable ZIP, Prüfsummen und Quellen](https://github.com/yasmin78-gif/LyricsStudio/releases/tag/v0.6.1)

Der Installer installiert nur für den aktuellen Benutzer, ohne Administratorrechte. Python und der eingebettete Editor sind enthalten. Für die portable Ausgabe das vollständige ZIP entpacken und `LyricsStudio.exe` starten. Bei der Deinstallation bleiben persönliche Projekte und Einstellungen erhalten.

Windows 11 x64 wurde praktisch getestet. Windows 10 x64 ab Version 2004 ist als Installationsziel vorgesehen, aber noch nicht separat abgenommen. Für macOS und Linux gibt es derzeit keine geprüften Installationspakete.

Das Paket ist nicht digital codesigniert; Windows kann deshalb einen unbekannten Herausgeber melden. Download und SHA-256-Prüfsummen ausschließlich über dieses Repository beziehen. Sicherheitsfunktionen nicht pauschal abschalten.

## Einmalig FFmpeg und ein Whisper-Modell einrichten

Diese beiden Komponenten sind **nicht im Download enthalten**. Die Buttons unter Einstellungen öffnen die externen Anbieter-Webseiten; Lyrics Studio lädt oder installiert sie nicht automatisch.

1. [FFmpeg für Windows von gyan.dev](https://www.gyan.dev/ffmpeg/builds/) herunterladen: einen **Full Build mit Whisper-Filter** auswählen und entpacken. Nicht jede FFmpeg-Version unterstützt Whisper. Die [FFmpeg-Downloadseite](https://ffmpeg.org/download.html) nennt weitere Anbieter.
2. Ein [GGML-Whisper-Modell](https://huggingface.co/ggerganov/whisper.cpp/tree/main) herunterladen. Als Einstieg eignet sich `ggml-small.bin` (mehrsprachig, ungefähr 466 MiB). Die Dateiendung muss `.bin` sein; keine CoreML-ZIP oder PyTorch-Datei auswählen. Größere Modelle benötigen mehr Speicher und Rechenzeit.
3. Unter Einstellungen „Erneut nach verfügbaren Einträgen suchen“ wählen. Falls nötig unter „Weitere Installation hinzufügen“ einmalig `bin/ffmpeg.exe` und die Modelldatei hinzufügen. Dann beide Einträge auswählen und speichern.
4. Bei Problemen mit der Grafikkarte die GPU-Option ausschalten.

Bei Bedarf die Unterstützung mit `ffmpeg -hide_banner -h filter=whisper` prüfen. Die Anwendung prüft sie ebenfalls vor der Song-Verarbeitung. Die externe FFmpeg-Version und Modelle unterliegen den jeweiligen Anbieter- und Open-Source-Lizenzen.

## Mit einem Song arbeiten

1. Einen Song per Drag & Drop ins Fenster ziehen oder „Neues Projekt“ wählen. WAV, MP3, FLAC, M4A und OGG werden angeboten; die tatsächliche Dekodierung übernimmt das separat installierte FFmpeg.
2. Projektnamen und Sprache wählen. Optional vorhandene Lyrics als Referenz einfügen. Die automatische Zuordnung dieses Referenztextes zum Gesang ist noch nicht implementiert.
3. Song vorbereiten lassen. Eine WAV-Arbeitskopie und unverbindliche Whisper-Vorschläge entstehen lokal. Die Vorbereitung ist abbrechbar.
4. „Lyrics bearbeiten“ öffnen. Text und Zeiten prüfen, korrigieren und ausdrücklich bestätigen. Whisper-Erkennung kann bei Gesang fehlerhaft sein. Der Editor arbeitet intern derzeit mit 24 FPS.
5. Über die obere Werkzeugleiste oder Strg+S speichern. Auch aktuelle Eingaben werden übernommen. Projektansichten bleiben beim Wechsel geöffnet; die Wiedergabe pausiert.
6. Bestätigte Passagen als SRT oder als bearbeitbare DaVinci-Titel exportieren.

„Projekt löschen …“ verschiebt nach Bestätigung den verwalteten Projektordner in den Papierkorb. Der ursprüngliche Song bleibt erhalten. Ungespeicherte Eingaben der geschlossenen Editorsitzung gehen verloren. Während einer Vorbereitung ist Löschen gesperrt.

## Exporte

**SRT:** bestätigte Passagen mit Text und Timing; optional mit Startversatz. Gestaltung und Animation hängen vom Untertitelwerkzeug des Schnittprogramms ab.

**Bearbeitbare Titel · DaVinci:** portable Exportpakete mit Importskript, transparenten Titelmedien, bestätigten Lyrics und optionalem Song. Einstellbar sind 24/25/30/50/60 FPS, Full HD/UHD und Song-Startversatz. Den angezeigten Importbefehl in Resolve unter Arbeitsbereich / Workspace → Konsole / Console → Lua ausführen. Er legt eine neue Timeline und einen eigenen Medienordner an. Bestehende Timelines werden nicht überschrieben. Überlappungen liegen auf getrennten Videospuren. Anschließend das Resolve-Projekt speichern und den gesamten Exportordner behalten.

**Animationen nach dem Import:** Lyrics-Clips in Resolves Edit-Timeline markieren, „Befehl zur Stilwahl kopieren“ im Exportdialog verwenden und den Befehl in der Lua-Konsole ausführen. Zur Auswahl stehen Standard Text+, sanftes Ein-/Ausblenden und Ghostly Mist Dissolve. Unterschiedliche Passagen können unterschiedliche Stile erhalten. Text und Clipzeiten bleiben erhalten; Schrift, Farbe, Größe und Position werden übernommen. Eigene Keyframe-Animationen werden nicht übertragen. Jeder Wechsel behält die vorherige Fusion-Komposition; als Quelle dient die zuletzt angelegte Lyrics-Komposition.

Text+ wird in Fusion über `Lyrics_Text` bearbeitet, beim Nebelstil über `GhostlyMistDissolve`. Die Stilwahl benötigt `Timeline:GetSelectedClips()`. Der Resolve-Import und Stilwechsel wurden mit **DaVinci Resolve Studio 21.1.1 auf Windows** geprüft. Andere Resolve-Versionen, die Free-Version und andere Plattformen sind noch nicht abgenommen. 23,976/29,97 FPS werden noch nicht angeboten.

## Daten und Datenschutz

Songs und Texte werden lokal verarbeitet. Es gibt keine Benutzerkonten und keine Telemetrie. Die standardmäßig aktive Updateprüfung kontaktiert die GitHub-API; sie lässt sich unter Einstellungen deaktivieren. Download- und Hilfelinks öffnen externe Webseiten. Details: [Datenschutzhinweise](legal/PRIVACY.md).

Die Bibliothek liegt standardmäßig außerhalb des Quellcodes:

- Windows: `%LOCALAPPDATA%/LyricsStudio/projects`
- macOS: `~/Library/Application Support/LyricsStudio/projects`
- Linux: `$XDG_DATA_HOME/LyricsStudio/projects` bzw. `~/.local/share/LyricsStudio/projects`

„Projektordner“ wählt eine andere Bibliothek; `--library PATH` gilt für einen Start. Für Backups vollständige Projektordner bei geschlossener Anwendung kopieren. Originaldateien bleiben unverändert. Songs, Lyrics, Modelle, Projekte und Exporte gehören nicht in Git; typische Dateien sind zusätzlich ausgeschlossen. Benutzer benötigen die Rechte an den von ihnen verwendeten und veröffentlichten Medien.

## Über Lyrics Studio

Die Schaltfläche „Über Lyrics Studio“ öffnet die Programminformationen mit Symbol, Versionsnummer, Copyright, MIT-Lizenz sowie Python-/Qt-Version, Betriebssystem, Architektur und Prozessinformationen. Dort sind auch das GitHub-Projekt und die vollständigen Lizenz- und Datenschutzhinweise erreichbar.

## Lizenz

Eigener Quellcode und eigene Grafiken: **MIT**, siehe [LICENSE](LICENSE). Mitgelieferte Bibliotheken behalten ihre eigenen Lizenzen, insbesondere PySide6/Qt unter LGPLv3 und die weiteren Lizenzen von Qt WebEngine/Chromium. Die Hinweise sind im Programm unter „Über Lyrics Studio → Lizenzen und Datenschutz“ und unter [legal/THIRD_PARTY.md](legal/THIRD_PARTY.md) erreichbar. Die unveränderten Qt-/PySide-Quellarchive sind weiterhin bei [v0.6.0](https://github.com/yasmin78-gif/LyricsStudio/releases/tag/v0.6.0) verfügbar; genaue Downloadlinks und Prüfsummen stehen in [legal/SOURCES.json](legal/SOURCES.json). Austausch und Änderung der Bibliotheken gemäß ihren Lizenzen bleiben erlaubt.

Keine Verbindung oder offizielle Unterstützung durch Blackmagic Design, OpenAI, FFmpeg oder Qt wird behauptet. Es gibt keine Zusicherung fehlerfreier Transkription oder einer juristisch zertifizierten Nutzung.

## Entwicklung

Python 3.11 oder neuer, Windows-Build getestet mit Python 3.13.15:

```powershell
python -m venv .venv
.venv/Scripts/python -m pip install -e .
.venv/Scripts/python -m lyrics_studio
.venv/Scripts/python -B -m unittest discover -s tests -q
```

Unter macOS/Linux `.venv/bin/python` verwenden. Alternativ startet unter Windows `Start-LyricsStudio.cmd` ohne Konsolenfenster. Der eigenständige Browser-Editor bleibt für Entwicklung verfügbar: `python -m lyrics_editor --data PATH --state-dir PATH`.

Build, Lizenzquellen, Installer und Prüfungen: [Release-Anleitung](docs/RELEASE.md). Geplante Erweiterungen: [Roadmap](docs/ROADMAP.md). Fehler bitte mit Programmversion und reproduzierbaren Schritten unter [Issues](https://github.com/yasmin78-gif/LyricsStudio/issues) melden; keine privaten Songs oder Zugangsdaten anhängen.
