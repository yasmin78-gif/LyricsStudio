# Lyrics Studio

Lokale Desktop-Anwendung zum Vorbereiten, Prüfen und Exportieren zeitlich zugeordneter Lyrics. Der vorhandene Webeditor ist direkt in das Desktop-Fenster eingebettet; ein separater Browser ist nicht erforderlich.

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
5. „Lyrics bearbeiten“ öffnet den Editor direkt im Programm. „← Projekte“ führt zurück zur Übersicht. Texte und Zeiten prüfen, korrigieren und ausdrücklich bestätigen. Der Editor arbeitet aktuell mit 24 FPS.
6. Entwurf im Editor oder über die Desktop-Werkzeugleiste speichern. Dabei werden auch die aktuellen Text- und Zeitfelder übernommen. Beim Wechsel zwischen Projekten bleiben die geöffneten Editor-Seiten samt Eingaben erhalten; die Wiedergabe wird pausiert. Vor dem Beenden kann die Anwendung alle geöffneten Projekte einschließlich noch nicht übernommener Eingaben speichern. Ungültige Eingaben verhindern die Speicherung und bleiben zur Korrektur geöffnet.
7. Bestätigte Passagen als SRT exportieren, bei Bedarf mit einem Startversatz für ein Intro in der Schnitt-Timeline.

Beim Beenden der Desktop-Anwendung enden die zugehörigen lokalen Editor-Dienste. Der eigenständige Browser-Start bleibt für Entwicklung und besondere Einsatzzwecke verfügbar.

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
- In Vorbereitung: automatische Referenztext-Ausrichtung, komfortable Modellbereitstellung und Installationsprogramme.
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


## Version und Updateprüfung

Die Versionsnummer steht zentral in lyrics_studio/__init__.py. Desktop, Browser und Python-Paket verwenden denselben Wert. Für eine neue Veröffentlichung wird dieser Wert erhöht und ein GitHub-Release mit passendem Tag (zum Beispiel v0.2.0) angelegt.

Beim normalen Programmstart prüft ein Hintergrundthread den neuesten stabilen GitHub-Release. Ein Hinweis mit „Update öffnen“ führt zur Release-Seite. Es gibt keinen automatischen Download und keine automatische Installation. „Nach Updates suchen“ startet eine manuelle Prüfung; die automatische Prüfung kann in den Einstellungen abgeschaltet werden. Offline- oder Zugriffsfehler blockieren die Projektarbeit nicht. Der technische Starttest --check erzeugt keine Netzwerkanfrage.

Das Repository ist derzeit privat. Ohne berechtigten Zugriff kann GitHub keine Releaseinformationen liefern; derselbe HTTP-404-Status tritt auch auf, wenn noch kein Release veröffentlicht wurde. Die Anwendung zeigt dann „Updateprüfung nicht verfügbar“ statt fälschlich „aktuell“. Optional kann für private Releases LYRICS_STUDIO_UPDATE_TOKEN als Umgebungsvariable mit einem GitHub-Token mit Contents-Leseberechtigung gesetzt werden. Der Token wird ausschließlich an die feste GitHub-API-Adresse gesendet und weder eingebaut noch in den Einstellungen gespeichert. Für öffentliche Releases ist kein Token erforderlich.

Die Prüfung verwendet https://api.github.com/repos/yasmin78-gif/LyricsStudio/releases/latest. Songs, Lyrics und Projektpfade werden dabei nicht übertragen.

## Eingebetteter Editor ab 0.3.0

Der Desktop verwendet Qt WebEngine, um die bestehende Oberfläche wiederzuverwenden. Jede geöffnete Projektansicht bleibt bis zum Beenden erhalten. Navigation ist auf den jeweiligen lokalen Editor-Dienst beschränkt. Das Windows-Paket enthält die benötigte WebEngine-Laufzeit und ist deshalb größer als zuvor. Für den Starttest des gebündelten Editors kann --check-editor zusammen mit --library und einer Bibliothek mit synthetischem, vorbereitetem Testprojekt verwendet werden. Dabei wird die Updateprüfung nicht gestartet.

## Kompakte Editorleiste ab 0.3.1

Im eingebetteten Editor enthält die untere Leiste nur Speicherstatus, Rückgängig/Wiederholen und „Änderungen verwerfen“. Letzteres ist nur bei einem vorhandenen Entwurf mit neuen Änderungen aktiv und fragt vor dem Laden des gespeicherten Stands nach. Gespeichert wird über die obere Desktop-Werkzeugleiste; Strg+S funktioniert weiterhin. Der interne JSON-Export und Dateipfade sind in der eingebetteten Leiste ausgeblendet. „Projektinformationen“ zeigt die Projekt- und Entwurfspfade bei Bedarf. Der eigenständige Browser-Aufruf behält seine separaten Speicher- und JSON-Exportfunktionen.


## Bearbeitbare DaVinci-Titel ab 0.4.0

„Bearbeitbare Titel · DaVinci“ exportiert ausdrücklich bestätigte Passagen als portables Paket. Aktuelle Editor-Eingaben werden zuerst gespeichert. Wähle Zielbildrate (24, 25, 30, 50 oder 60 FPS), Full HD oder UHD und bei Bedarf einen Song-Startversatz. Der Song kann als Audiospur mitgenommen werden. Der Export läuft im Hintergrund und ist abbrechbar. Jede Ausgabe erhält einen eigenen Ordner; bestehende Ausgaben werden nicht überschrieben.

Nach dem Export zeigt die Anwendung den fertigen Importbefehl mit Kopierbutton. Öffne das gewünschte Projekt in Resolve, öffne Arbeitsbereich / Workspace → Konsole / Console und wähle Lua. Füge den dofile-Befehl ein und drücke Enter. Der Import legt eine eigene Timeline und einen eigenen Medienordner an. Jede Passage wird eine separate Fusion-Komposition mit dem Text+-Knoten Lyrics_Text. Text, Schrift, Position und Animation können in Fusion bearbeitet werden. Überlappende Passagen liegen auf getrennten Videospuren und werden vertikal versetzt. Die Clips lassen sich in andere Timelines mit gleicher Bildrate kopieren.

Die Clipzeiten werden für die gewählte Bildrate nach außen auf Frames abgebildet. Der Import prüft jede Clipgrenze und den Text nach dem Anlegen. Die neue Timeline beginnt bei 00:00:00:00; der gewählte Song-Versatz wird darauf angewendet. Bestehende Timelines werden nicht verändert. Nach dem Import das Resolve-Projekt selbst speichern.

Den gesamten Exportordner behalten: Er enthält die transparenten Titelmedien als Bildsequenz, den optionalen Song, Daten, Importscript und nach dem Import die nativen Kompositionen. Nach Verschieben des Pakets den Pfad im dofile-Befehl anpassen. Ein erfolgreicher Import erzeugt IMPORT-ERGEBNIS.txt. Bei einem Importfehler bleibt eine neue, als UNVOLLSTAENDIG gekennzeichnete Timeline zur Prüfung erhalten; Details stehen in IMPORT-FEHLER.txt. Ein bereits oder unvollständig importiertes Paket wird nicht automatisch erneut eingefügt. Die Ausgabe enthält außerdem eine .gitignore zum Schutz privater Lyrics und Medien.

Der Import wurde mit synthetischen Texten, Unicode, Zeilenumbrüchen, überlappenden Passagen, Song-Audio, 24/25 FPS, Startversatz und Full HD/UHD in DaVinci Resolve Studio 21.1.1 auf Windows geprüft. Andere Resolve-Versionen und Plattformen sind noch nicht praktisch abgenommen. 23,976/29,97-FPS-Timelines werden in dieser Version noch nicht unterstützt.
