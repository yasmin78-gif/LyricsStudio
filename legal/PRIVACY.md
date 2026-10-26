# Datenschutz und Netzwerkzugriffe

Songs, Texte, Whisper-Ausgaben und Projektentwürfe werden lokal verarbeitet und
gespeichert. Es gibt kein Benutzerkonto, keine Telemetrie und keinen Upload der
Songs durch Lyrics Studio. Der eingebettete Editor verwendet einen lokalen Dienst
auf 127.0.0.1. Der Editor und seine Audiodateien werden nicht im Internet gehostet.

Beim Programmstart ist die Updateprüfung standardmäßig aktiviert. Sie fragt die
GitHub-API nach dem neuesten stabilen Release ab. Dabei erhält GitHub die bei
einer HTTPS-Verbindung üblichen Verbindungsdaten, insbesondere die IP-Adresse,
sowie einen User-Agent mit der Programmversion. Songs, Texte und Projektpfade
werden nicht gesendet. Die Prüfung kann unter Einstellungen ausgeschaltet werden.
Updates werden nicht automatisch installiert.

Die Downloadbuttons öffnen die externen Webseiten von gyan.dev (FFmpeg) und
Hugging Face (Whisper-Modelle) im normalen Browser. GitHub-, Quellen- und
Lizenzlinks öffnen ebenfalls externe Webseiten. Ab diesem Aufruf gelten deren
Datenschutzbedingungen. Lyrics Studio lädt FFmpeg oder Modelle nicht automatisch.

Projektdateien bleiben bei der Deinstallation erhalten. Zum Entfernen der eigenen
Daten die gewählte Projektbibliothek und bei Bedarf die Lyrics-Studio-Einstellungen
selbst löschen. Backups und exportierte Dateien separat berücksichtigen.

Dieses Dokument beschreibt das Verhalten der unveränderten Anwendung. Vom Nutzer
separat installierte Tools, Betriebssystemdienste und Änderungen am Quellcode
können eigene Netzwerkzugriffe ausführen.
