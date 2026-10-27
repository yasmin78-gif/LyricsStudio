# Third-party software

Lyrics Studio's own source code and original assets are MIT licensed. Third-party
libraries are NOT relicensed under MIT. Copyright notices and full license texts
are provided in this directory and its subdirectories.

The Windows application uses Python (PSF license), PySide6 and shiboken6 (LGPLv3),
Qt shared libraries (LGPLv3), Qt WebEngine/Chromium (LGPLv3 and numerous third-party
licenses), OpenSSL (Apache-2.0), libffi (MIT), zlib (zlib), and the PyInstaller
bootloader (GPL with its distribution exception). The setup program is built with
unmodified Inno Setup. Microsoft Windows runtime files retain Microsoft's terms.

See SOURCES.json for exact upstream source archives and versions. The release
provides access to the corresponding Qt and PySide source archives through the
release download URLs in SOURCES.json. Releases with unchanged libraries may link
to the original source assets instead of uploading identical copies again.
Qt's source archives contain third-party notices and build scripts. The exact
Chromium notices retained from its matching source are in chromium-credits.html.
Additional Qt third-party notices are retained from the matching source archives.

## LGPL rights and replacement

PySide6, shiboken6 and Qt are unmodified upstream shared libraries. We use their
LGPL licensing option. Copies of LGPLv3, GPLv3 (incorporated by LGPLv3), and LGPLv2.1
are included. You may inspect, reverse engineer for debugging modifications,
modify, replace and redistribute these libraries under their licenses. Lyrics
Studio imposes no contractual restriction on these rights and requires no vendor
signature to run with modified libraries.

The commercial-license text retained from the upstream wheels describes an
alternative Qt licensing option; this release uses the LGPL option stated above.

Close Lyrics Studio, make a copy of its installation folder, and replace compatible
DLLs/PYD files under _internal/PySide6 and _internal/shiboken6. Keep the Python ABI,
architecture, matching Qt modules, plugins and WebEngine helper/resources compatible.
Do not overwrite your only working installation. For changes to Python bindings or
an incompatible runtime, rebuild the MIT-licensed application using the instructions
in docs/RELEASE.md and the corresponding upstream source build instructions. There
is no activation, DRM or signature check blocking such a rebuild.

## External tools, not included

The separate FFmpeg executable with the Whisper filter and the Whisper model are
not included in either installer or portable application. Download buttons open
upstream/provider websites in your browser. Lyrics Studio neither hosts nor
automatically installs these dependencies. Their own licenses apply. Whisper and
whisper.cpp are separate upstream projects; no affiliation or endorsement is implied.

Qt WebEngine contains its own Chromium media implementation, including FFmpeg
code. This internal library is covered by the WebEngine notices and sources;
it is distinct from the external FFmpeg executable used for song transcription.

## Media and projects

No songs, lyrics, user projects, models or generated exports are distributed.
Users remain responsible for having the necessary rights to media they process
and publish. Third-party names and trademarks belong to their respective owners;
Lyrics Studio is not affiliated with Blackmagic Design, OpenAI, FFmpeg or Qt.
