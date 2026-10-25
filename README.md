# Lyrics Studio

Lokale Anwendung zum Vorbereiten, Prüfen und Exportieren zeitlich zugeordneter Lyrics.

## Vorhandener Stand

Der Browser-Editor und seine Python-Datenvalidierung wurden aus dem Musikvideo-Arbeitsverzeichnis übernommen. Er verarbeitet vorhandene Lyrics-Daten im Schema 2.0 und PCM16-WAV-Dateien. Audio, Lyrics und persönliche Bearbeitungsstände sind nicht Bestandteil dieses Repositorys.

Python 3.13 wurde im bisherigen Entwicklungsumfeld verwendet; der Editor benötigt keine zusätzlichen Python-Pakete.

Start aus diesem Repository mit eigenen, extern gespeicherten Daten:

    python -B -m lyrics_editor --data "/absoluter/pfad/lyrics_timing.json" --state-dir "/absoluter/pfad/editor-state"

Anschließend http://127.0.0.1:8765 im Browser öffnen. Der Dienst läuft nur lokal. Mit Strg+C beenden; vorher Entwurf speichern.

Der vorhandene JSON-Export ist ein interner Datenexport. Die geplanten SRT- und Titel-Exporte sind noch nicht implementiert. Desktop-Projektverwaltung und integrierte Spracherkennung fehlen ebenfalls noch.

## Geplante Anwendung

- Desktop-Oberfläche mit Projektübersicht, Anlegen, Speichern und erneutem Öffnen von Projekten.
- Song-Import und lokale Whisper-Verarbeitung mit Fortschrittsanzeige.
- Bestehender Browser-Editor zur Prüfung und Korrektur.
- Export als SRT für Untertitel.
- Export als bearbeitbare Titel für einzelne Schnittprogramme, zuerst DaVinci Resolve.
- Windows, macOS und Linux als Zielplattformen; bislang keine plattformübergreifende Abnahme.

Siehe docs/ROADMAP.md.

## Persönliche Daten

Nutzerprojekte, Songs, Lyrics, Modelle, Caches und Exporte gehören in separate Datenordner außerhalb des Repositorys. Die .gitignore dient zusätzlich als Schutz vor typischen versehentlichen Übernahmen.

## Entwicklung

Die vorhandene Testsuite aus dem ursprünglichen Arbeitsverzeichnis hängt teilweise von echten Songdaten ab und wurde deshalb noch nicht übernommen. Eine unabhängige Suite mit synthetischen Beispielen ist ein nächster Vorbereitungsschritt.
