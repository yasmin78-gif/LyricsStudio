# Lyrics Studio

Lokale Desktop-Anwendung zum Vorbereiten, Prüfen und Exportieren zeitlich zugeordneter Lyrics. Der vorhandene Editor läuft weiterhin im Browser.

## Desktop starten

Python 3.11 oder neuer installieren (hier mit Python 3.13 getestet), dann aus dem Repository:

    python -m venv .venv
    .venv\Scripts\python -m pip install -e .
    .venv\Scripts\python -m lyrics_studio

Unter Windows startet anschließend auch ein Doppelklick auf Start-LyricsStudio.cmd die Oberfläche ohne Konsolenfenster.

Unter macOS/Linux stattdessen .venv/bin/python verwenden. Diese Plattformen sind vorbereitet, aber noch nicht praktisch abgenommen.

## Mit einem Song arbeiten

1. Unter Einstellungen aus den Listen gefundener FFmpeg-Installationen und Whisper-Modelle auswählen. Vorhandene Einträge werden automatisch vorausgewählt. Bei Problemen mit der Grafikkarte die GPU-Option deaktivieren. Die Anwendung lädt keine Modelle automatisch herunter.
2. Einen Song per Drag & Drop ins Fenster ziehen oder „Neues Projekt“ wählen. Pro Import eine Audiodatei; weitere Songs als weitere Projekte anlegen.
3. Namen und Sprache wählen, optional den vorhandenen Liedtext einfügen oder als UTF-8-TXT laden. Der Liedtext dient als Referenz; automatische Zuordnung des Referenztextes zum Gesang ist noch nicht implementiert.
4. Die Vorbereitung erstellt eine PCM16-WAV-Arbeitskopie und erkennt Textpassagen mit Whisper. Sie läuft im Hintergrund und kann abgebrochen werden. Fehlgeschlagene oder abgebrochene Vorbereitungen können erneut gestartet werden.
5. „Im Browser bearbeiten“ öffnet den vorhandenen Editor. Texte und Zeiten prüfen, korrigieren und ausdrücklich bestätigen. Der Editor arbeitet aktuell mit 24 FPS.
6. Entwurf im Browser oder in der Desktop-Anwendung speichern. Projekte können später erneut geöffnet werden. Beim Wechsel bleiben laufende Editor-Sitzungen erhalten. Vor dem Beenden alle Eingaben im Browser übernehmen; die Desktop-Anwendung kann nur an den Dienst übergebene Änderungen speichern.
7. Bestätigte Passagen als SRT exportieren, bei Bedarf mit einem Startversatz für ein Intro in der Schnitt-Timeline.

Beim Beenden der Desktop-Anwendung enden die zugehörigen lokalen Editor-Dienste. Alte Browser-Tabs danach schließen und Projekte über die Desktop-Anwendung neu öffnen.

## Einstellungen

FFmpeg und Whisper-Modelle werden als direkt auswählbare Listen mit Namen und Versions- beziehungsweise Größenangaben angezeigt. Die Suche berücksichtigt gespeicherte Einträge, den Programmsuchpfad, bekannte Installations- und Modellordner sowie unter Windows WinGet-Installationen. Ein bereits ausgewählter Eintrag bleibt beim erneuten Suchen erhalten, sofern er noch vorhanden ist. Nicht jede FFmpeg-Installation enthält Whisper; die benötigte Unterstützung wird beim Start der Song-Verarbeitung geprüft.

Unter „Weitere Installation hinzufügen“ lassen sich zusätzliche lokale Programme oder Modelle einmalig ergänzen. Diese Orte werden gespeichert und bei späteren Suchen berücksichtigt. Technische Dateipfade sind als Tooltips verfügbar. Wenn eine erforderliche Komponente fehlt, zeigt die Liste das ausdrücklich an; eine unvollständige Auswahl lässt sich nicht speichern. Modelle werden nicht automatisch heruntergeladen.


## Projektdateien

Die persönliche Bibliothek liegt standardmäßig außerhalb des Quellcodes:

- Windows: %LOCALAPPDATA%/LyricsStudio/projects
- macOS: ~/Library/Application Support/LyricsStudio/projects
- Linux: $XDG_DATA_HOME/LyricsStudio/projects bzw. ~/.local/share/LyricsStudio/projects

„Projektordner“ wählt eine andere Bibliothek; --library PATH setzt sie für einen Start. Ein Projekt ist ein eigener Ordner mit project.json, Audio-Arbeitskopie, optionalem Referenztext, Whisper-Ausgabe und Editor-Entwürfen samt Revisionen. Nach erfolgreichem Import kann der ganze Projektordner verschoben oder gesichert werden. Vor dem Verschieben die Anwendung schließen. Zur Aufnahme in eine andere Bibliothek den gesamten Projektordner in deren Verzeichnis kopieren.

Original-Songs bleiben unverändert. Vor erfolgreicher Vorbereitung muss die ursprüngliche Audiodatei verfügbar bleiben. Nutzerdaten, Songs, Modelle und Exporte gehören nicht in dieses Repository. Die .gitignore schließt typische Datenordner und Medienformate zusätzlich aus.

## Stand und Grenzen

- Implementiert: Projektverwaltung, Drag & Drop, lokale Whisper-Verarbeitung mit FFmpeg, Fortschritt, Abbruch, erneutes Öffnen, Editor-Anbindung, Speichern und SRT-Export.
- In Vorbereitung: Export bearbeitbarer Titel für DaVinci Resolve, automatische Referenztext-Ausrichtung, komfortable Modellbereitstellung und Installationsprogramme.
- Whisper-Ergebnisse sind Vorschläge. Der SRT-Export verwendet ausschließlich ausdrücklich bestätigte Passagen.
- Für Whisper benötigt FFmpeg einen Build mit aktiviertem Whisper-Filter. Ein gewöhnlicher FFmpeg-Build genügt eventuell nicht. Siehe https://ffmpeg.org/ffmpeg-filters.html#whisper.

## Entwicklung und Tests

    .venv\Scripts\python -B -m unittest discover -s tests -v

Die Tests erzeugen synthetisches Audio und eigene Textbeispiele. Echte Songs und persönliche Lyrics sind nicht enthalten. GUI-Tests verwenden Qt offscreen; ein echter Whisper-Import wird separat mit vorhandenen lokalen Werkzeugen geprüft.

Ein Windows-Programm ohne separat installierte Python-Laufzeit lässt sich so bauen:

    .venv\Scripts\python -m pip install -e .[build]
    .venv\Scripts\python -m PyInstaller --noconfirm LyricsStudio.spec

Das Ergebnis liegt unter dist/LyricsStudio/LyricsStudio.exe. Für die Weitergabe den gesamten Ordner verwenden. FFmpeg mit Whisper und das Modell werden separat benötigt. Build-Ausgaben und persönliche Einstellungen werden nicht in Git aufgenommen.

Der Browser-Editor kann weiterhin unabhängig gestartet werden:

    python -B -m lyrics_editor --data "/absoluter/pfad/lyrics_timing.json" --state-dir "/absoluter/pfad/editor-state"

Anschließend http://127.0.0.1:8765 öffnen. Mehr zur weiteren Planung in docs/ROADMAP.md.
