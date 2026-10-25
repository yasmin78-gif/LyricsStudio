# Entwicklungsplan

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
