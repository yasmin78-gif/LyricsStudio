# Entwicklungsplan

## Stand 0.1.0
- Implementiert: PySide6-Desktop, Projektbibliothek, Song-Import per Dateiauswahl und Drag & Drop.
- Implementiert: Whisper über FFmpeg, Verarbeitung im Hintergrund, Fortschritt und Abbruch.
- Implementiert: bestehender Browser-Editor pro Projekt, Speichern und Wiederöffnen, portable Projektordner.
- Implementiert: SRT-Export bestätigter Passagen mit Startversatz.
- Windows-Programm mit PyInstaller gebaut; Tests mit synthetischen Daten und lokaler Whisper-Import geprüft.
- Offen: bearbeitbare DaVinci-Titel, Referenztext-Ausrichtung, Modellbereitstellung und Installationsprogramme.
- macOS und Linux noch nicht praktisch abgenommen.

Die folgenden Abschnitte enthalten den Gesamtplan einschließlich bereits begonnener Schritte.

## 1. Eigenständige Grundlage
- Bestehenden Editor mit synthetischen Beispielen und unabhängigen Tests absichern.
- Portable Audio- und Projektpfade definieren.
- Gemeinsames versioniertes Projektformat festlegen; Daten außerhalb des Codes ablegen.

## 2. Desktop-Projektverwaltung
- PySide6 als vorgesehene Oberfläche prüfen und integrieren.
- Projekte anlegen, auflisten, speichern und erneut öffnen.
- Lokalen Editor-Dienst verwalten und ausgewähltes Projekt im Browser öffnen.
- Ungespeicherte Änderungen beim Projektwechsel berücksichtigen.

## 3. Audioverarbeitung
- Song-Import und Konvertierung zum internen Audioformat.
- Whisper/FFmpeg plattformgerecht einbinden.
- Optionale vorhandene Lyrics für zeitliche Zuordnung berücksichtigen.
- Hintergrundverarbeitung mit Fortschritt, Abbruch und verständlichen Fehlern.
- Modellbereitstellung und Hardwarebeschleunigung je Plattform testen.

## 4. Exporte
- SRT: geprüfte Passagen mit Text und Anfangs-/Endzeit.
- Einstellbarer Song-Startversatz; Framerate bei Titel-Exporten berücksichtigen.
- Bearbeitbare Titel: zuerst DaVinci Resolve, danach weitere Programme nach Bedarf.
- Import und Synchronität in jedem unterstützten Zielprogramm prüfen.
- Internes Projektformat als vollständige Quelle für erneute Bearbeitung erhalten.

## 5. Auslieferung
- Installationspakete für Windows, macOS und Linux.
- Start, Audio, Speichern, Wiederöffnen und Export auf den Zielplattformen prüfen.
- Keine echten Nutzersongs, privaten Lyrics oder persönlichen Projekte im Repository.
