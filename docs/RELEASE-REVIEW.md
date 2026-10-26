# Technische Releaseprüfung 0.6.0

Geprüft für Windows x64, 26. Oktober 2026. Dies ist keine anwaltliche
Begutachtung, Patentfreigabe oder juristische Zertifizierung.

## Umfang

- Eigener Quellcode und eigene Assets unter MIT; bisherige Git-Autoren geprüft.
- Vollständige bisherige Git-Historie auf typische Zugangsdaten, private Medien
  und persönliche Pfade durchsucht. Zusätzlich Dateiliste und Diff geprüft.
  Mustersuche kann unbekannte Geheimnisformate nicht ausschließen.
- PySide6/shiboken6 6.12.0, Qt 6.12.0, WebEngine 6.140.0 aus den verwendeten
  Upstream-Paketen. Nutzung der LGPL-Option; unmodifizierte dynamische Bibliotheken.
- Die bisher pauschal gesammelten QML-Plugins und nicht benötigten Qt-Module
  werden nicht ausgeliefert. Das Release-Gate lehnt u.a. Charts, Graphs,
  DataVisualization, VirtualKeyboard, Quick3D, Multimedia und PDF ab.
- Quellen: neun unveränderte Qt-/PySide-Archive, passende Versionszuordnung und
  SHA-256-Manifest. Beim Release als eigenständige Assets zugänglich.
- Lizenztexte von Python, LGPL/GPL, OpenSSL, libffi und Inno Setup sowie die
  PyInstaller-Lizenz mit Ausnahme und Upstream-Notices aufbewahrt.
- 1.920 Lizenz-/Copyright-/Notice-Dateien aus dem passenden WebEngine-Quellarchiv
  als lesbare HTML-Hinweise zusammengetragen. Diese Liste enthält absichtlich
  auch Upstream-Komponenten, die im Windows-Binary nicht verwendet werden.
- Eigene MIT-Lizenz gilt nicht für die Drittanbieterbibliotheken. Deren Rechte
  und Hinweise sind in Installation und Anwendung erreichbar. Austausch/Rebuild
  sind beschrieben und werden nicht durch Aktivierung oder Signaturzwang gesperrt.
- Keine separate FFmpeg-EXE und keine Whisper-Modelle im Installer/ZIP. Externe
  Downloadlinks in Einstellungen und README. Die interne Chromium-Medienbibliothek
  ist hiervon ausdrücklich unterschieden und durch WebEngine-Quellen abgedeckt.
- Keine Telemetrie/Audio-Uploads implementiert. GitHub-Updateprüfung und externe
  Links sind im Datenschutzhinweis beschrieben.
- Per-user-Installer ohne Administratorrechte; keine Löschregel für Bibliotheken
  oder Einstellungen. Kein automatisches Nachladen externer Komponenten.

## Validierung und Grenzen

Anwendungstests mit synthetischen Daten; zusätzliche Prüfungen für Lizenzdialog
und Downloadbuttons. Buildinventar mit SHA-256 jedes ausgelieferten Files.
Gebündelten Editor und Starttest nach der Laufzeitreduktion geprüft.
Installer-Installation und Deinstallation wurden mit synthetischer Bibliothek
geprüft (jeweils Exitcode 0); eine unbekannte Testdatei blieb erhalten. Resolve-Import und drei Titelstile wurden
bereits mit synthetischen Daten in Resolve Studio 21.1.1 geprüft.

Kein Codesignaturzertifikat vorhanden; Installer und Programm sind unsigniert.
Windows kann einen Herausgeber-/SmartScreen-Hinweis zeigen. Prüfsummen und
Downloadquelle werden dokumentiert. macOS/Linux, Windows 10 und Resolve Free
sind noch keine separat praktisch abgenommenen Releaseziele.

Für neue Versionen müssen tatsächliche Bibliotheken, Quellen, Notices und Tests
erneut abgeglichen werden. Ein Link auf fremde Software ersetzt keine Pflichten
für Komponenten, die tatsächlich im eigenen Paket stecken.
