# Windows-Release bauen

Version 0.6.1 wurde unter Windows 11 x64 mit Python 3.13.15 gebaut. macOS/Linux
sind bisher keine abgenommenen Releaseziele. Der Installer ist mit Inno Setup
7.1.0 gebaut. Der Quellcode des Programms ist MIT-lizenziert.

## Abhängigkeiten und Quellen

`requirements-build.txt` fixiert die für diesen Build verwendeten Versionen.
In einer frischen virtuellen Umgebung installieren:

```powershell
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements-build.txt
.venv/Scripts/python -m pip install --no-deps -e .
.venv/Scripts/python tools/prepare_legal.py
.venv/Scripts/python tools/export_chromium_credits.py
```

`prepare_legal.py` bezieht unveränderte Quellen von download.qt.io und Lizenztexte
aus den angegebenen Upstream-Projekten. `legal/SOURCES.json` dokumentiert die
Versionen, Quell-URLs und SHA-256-Prüfsummen. Die Archivnamen und Prüfsummen gegen
die bereits geprüfte Manifestversion vergleichen; bei Abweichungen vor dem
Veröffentlichen die Ursache klären. Die Bibliotheken sind nicht von uns geändert.

Bei unveränderten Bibliotheken wie in 0.6.1 können die passenden Quellen des Releases [v0.6.0](https://github.com/yasmin78-gif/LyricsStudio/releases/tag/v0.6.0) weiterverwendet werden. Dann im neuen Release ausdrücklich auf diese Quellen und `legal/SOURCES.json` verweisen.

Bei neuen Bibliotheksversionen die vollständigen Qt-/PySide-Quellarchive unter `dist/upstream-sources` zusammen
mit dem Installer und der portablen ZIP beim Release veröffentlichen. Die Quellen
enthalten auch deren Buildskripte und Anleitungen. Qt: https://doc.qt.io/qt-6/build-sources.html
PySide: https://doc.qt.io/qtforpython-6/building_from_source/index.html
Für kompatible Ersatzbibliotheken Architektur, Python-ABI, Qt-Versionen und
WebEngine-Ressourcen angleichen. Das öffentliche Anwendungsrepository und diese
Builddateien erlauben den vollständigen Neubau ohne Signatur-/Aktivierungszwang.

## Bauen und prüfen

```powershell
.venv/Scripts/python -B -m unittest discover -s tests -q
.venv/Scripts/python -m PyInstaller --noconfirm --distpath dist/v0.6.1 LyricsStudio.spec
.venv/Scripts/python tools/audit_bundle.py dist/v0.6.1/LyricsStudio dist/release-v0.6.1/runtime-manifest.json
```

`LyricsStudio.spec` bindet Lizenztexte und die README ein. `bundle_policy.py`
verwendet die PE-Abhängigkeiten der benötigten Widgets-/WebEngine-Laufzeit und
eine beschränkte Plugin-Auswahl; unbenutzte QML-Plugins und GPL-only-Qt-Module
werden nicht pauschal mitgeliefert. UPX ist deaktiviert. Normale Qt-DLLs und
PySide-PYD-Dateien bleiben im `_internal`-Verzeichnis austauschbar.

Mit installiertem Inno Setup kompilieren:

```powershell
ISCC.exe installer/LyricsStudio.iss
```

Danach Installer in einen separaten Testordner installieren, `LyricsStudio.exe
--check` und `--check-editor --library PATH` mit einer synthetischen Bibliothek
ausführen. Auch die Deinstallation und das Beibehalten von Projektdateien prüfen.
Keine echten Songs für Pakettests verwenden. Das gesamte Programmverzeichnis
als `LyricsStudio-0.6.1-Windows-x64-Portable.zip` packen. Für alle Releaseassets
SHA-256-Prüfsummen erzeugen. Das Paket ist derzeit nicht codesigniert.

## Veröffentlichung

1. `tools/release_audit.py` auf der vollständigen Git-Historie ausführen; das
   ist eine ergänzende Mustersuche, keine Garantie auf Geheimnisfreiheit.
2. Arbeitsbaum/Diff und vollständiges Runtime-Manifest prüfen. Keine Modelle,
   Audiodateien, Nutzerdaten, Einstellungen oder Zugangsdaten veröffentlichen.
3. Quellcode committen und Tag `v0.6.1` exakt auf den getesteten Stand setzen.
4. Zunächst einen GitHub-Releaseentwurf anlegen. Installer, portable ZIP,
   Runtime-Manifest, Lizenz-/Quellenhinweise, Prüfsummen und alle Quellarchive
   hochladen. Erst nach erfolgreicher Vollständigkeitsprüfung veröffentlichen.
5. Bei der ersten Veröffentlichung die Repository-Sichtbarkeit erst ändern,
   wenn Historie, Lizenz und Releaseassets geprüft sind.

FFmpeg und Whisper-Modelle sind separate Downloads. Das gilt nicht für die
interne Chromium-Medienimplementierung von Qt WebEngine: deren enthaltene
FFmpeg-Quellen und Lizenzen sind in den WebEngine-Quellen und Hinweisen enthalten.

## Grenzen der Prüfung

Dies ist eine technische Lizenz-/Paketprüfung, keine anwaltliche Begutachtung,
keine Patentfreigabe und keine Gewähr für jede Rechtsordnung. Mitgelieferte
Komponenten behalten ihre jeweiligen Lizenzen. Die MIT-Lizenz des eigenen Codes
ersetzt deren Bedingungen nicht. Für spätere Abhängigkeitsupdates müssen Quellen,
Hinweise und Paketprüfung erneut auf die tatsächlichen Versionen abgestimmt werden.
