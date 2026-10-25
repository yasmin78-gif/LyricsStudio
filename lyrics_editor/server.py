"""Loopback-only HTTP server: allowlisted assets, read-only audio, review actions."""
from array import array
import io
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import re
import secrets
import sys
from urllib.parse import parse_qs, urlparse
import wave

from .store import Store, Conflict, atomic_write, encoded
from .timebase import validate_interval

ASSETS = Path(__file__).parent / 'static'


def peaks(store):
    path = store.directory / ('waveform-' + store.base['audio']['sha256'][:16] + '.json')
    if path.exists():
        result = json.loads(path.read_text(encoding='utf-8'))
        if result.get('audio_sha256') == store.base['audio']['sha256']:
            return result
        raise ValueError('Wellenform-Cache passt nicht zur Quelle.')
    bins = []
    with wave.open(str(store.audio), 'rb') as audio:
        channels, rate = audio.getnchannels(), audio.getframerate()
        if audio.getsampwidth() != 2 or audio.getcomptype() != 'NONE':
            raise ValueError('Phase 1 unterstützt PCM-WAV mit 16 Bit.')
        bucket = max(1, round(rate * .01))
        while block := audio.readframes(bucket):
            values = array('h', block)
            if sys.byteorder != 'little':
                values.byteswap()
            entries = []
            for channel in range(channels):
                samples = values[channel::channels]
                entries.extend((min(samples), max(samples)))
            bins.append(entries)
    result = dict(audio_sha256=store.base['audio']['sha256'], channels=channels,
                  bucket_seconds=bucket / rate, duration=store.duration, peaks=bins)
    atomic_write(path, encoded(result))
    return result


def make_server(data, state_dir, port=8765, title=None):
    directory = Path(state_dir).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    lease = (directory / '.session.lock').open('a+b')
    try:
        if lease.tell() == 0:
            lease.write(b'0')
            lease.flush()
        lease.seek(0)
        if sys.platform == 'win32':
            import msvcrt
            msvcrt.locking(lease.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(lease.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        store = Store(data, state_dir, title=title)
        waveform = peaks(store)
    except Exception:
        lease.close()
        raise
    token = secrets.token_urlsafe(32)

    class Handler(BaseHTTPRequestHandler):
        protocol_version = 'HTTP/1.1'

        def log_message(self, format, *args):
            if sys.stderr is not None and (not args or '/api/audio' not in str(args[0])):
                super().log_message(format, *args)

        def response(self, status, payload, content_type='application/json; charset=utf-8', extra=None):
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(payload)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; media-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'")
            for key, value in (extra or {}).items():
                self.send_header(key, value)
            self.end_headers()
            if self.command != 'HEAD':
                self.wfile.write(payload)

        def json_response(self, data, status=200):
            self.response(status, encoded(data))

        def host_allowed(self):
            return self.headers.get('Host') == f'127.0.0.1:{self.server.server_port}'

        def do_HEAD(self):
            self.do_GET()

        def do_GET(self):
            if not self.host_allowed():
                return self.json_response({'error': 'Nur lokaler Zugriff über 127.0.0.1 erlaubt.'}, 403)
            path = urlparse(self.path).path
            try:
                if path in ('/', '/app.js', '/style.css'):
                    name = {'/': 'index.html', '/app.js': 'app.js', '/style.css': 'style.css'}[path]
                    kind = {'index.html': 'text/html; charset=utf-8', 'app.js': 'text/javascript; charset=utf-8',
                            'style.css': 'text/css; charset=utf-8'}[name]
                    return self.response(200, (ASSETS / name).read_bytes(), kind)
                if path == '/api/state':
                    with store.lock:
                        return self.json_response({**store.state(), 'token': token})
                if path == '/api/peaks':
                    return self.json_response(waveform)
                if path == '/api/audio':
                    return self.audio()
                if path == '/api/segment':
                    query = parse_qs(urlparse(self.path).query)
                    start, end, _ = validate_interval(query['start'][0], query['end'][0], store.duration, store.fps)
                    if end - start > 60:
                        raise ValueError('Bereichsvorschau auf 60 Sekunden begrenzt. Bitte kürzeren Bereich wählen.')
                    with wave.open(str(store.audio), 'rb') as source:
                        rate = source.getframerate()
                        source.setpos(round(start * rate))
                        block = source.readframes(round(end * rate) - round(start * rate))
                        result = io.BytesIO()
                        with wave.open(result, 'wb') as target:
                            target.setnchannels(source.getnchannels())
                            target.setsampwidth(source.getsampwidth())
                            target.setframerate(rate)
                            target.writeframes(block)
                    return self.response(200, result.getvalue(), 'audio/wav')
                if path == '/favicon.ico':
                    return self.response(204, b'', 'image/x-icon')
                return self.json_response({'error': 'Nicht gefunden.'}, 404)
            except (ValueError, KeyError) as exc:
                return self.json_response({'error': str(exc)}, 400)
            except (BrokenPipeError, ConnectionResetError):
                return

        def audio(self):
            size = store.audio.stat().st_size
            start, end, status = 0, size - 1, 200
            requested = self.headers.get('Range')
            if requested:
                match = re.fullmatch(r'bytes=(\d*)-(\d*)', requested)
                if not match or not any(match.groups()):
                    return self.response(416, b'', extra={'Content-Range': f'bytes */{size}'})
                a, b = match.groups()
                if a:
                    start = int(a)
                    end = min(int(b), end) if b else end
                else:
                    start = max(0, size - int(b))
                if start >= size or start > end:
                    return self.response(416, b'', extra={'Content-Range': f'bytes */{size}'})
                status = 206
            self.send_response(status)
            self.send_header('Content-Type', 'audio/wav')
            self.send_header('Accept-Ranges', 'bytes')
            self.send_header('Content-Length', str(end - start + 1))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            if status == 206:
                self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
            self.end_headers()
            if self.command == 'HEAD':
                return
            with store.audio.open('rb') as source:
                source.seek(start)
                remaining = end - start + 1
                while remaining:
                    block = source.read(min(65536, remaining))
                    if not block:
                        break
                    self.wfile.write(block)
                    remaining -= len(block)

        def do_POST(self):
            origin = self.headers.get('Origin')
            expected_origin = f'http://127.0.0.1:{self.server.server_port}'
            if not self.host_allowed() or (origin and origin != expected_origin) or self.headers.get('X-Editor-Token') != token:
                self.close_connection = True
                return self.json_response({'error': 'Ungültige lokale Sitzung.'}, 403)
            try:
                size = int(self.headers.get('Content-Length', 0))
                if not 0 < size <= 100_000:
                    raise ValueError('Ungültige Nachrichtengröße.')
                payload = json.loads(self.rfile.read(size))
                path = urlparse(self.path).path
                if path == '/api/action':
                    result = store.act(payload)
                elif path == '/api/save':
                    result = store.save(payload['revision'])
                elif path == '/api/reload':
                    result = store.reload(payload['revision'])
                elif path == '/api/export':
                    result = store.export(payload['revision'])
                else:
                    return self.json_response({'error': 'Nicht gefunden.'}, 404)
                return self.json_response(result)
            except Conflict as exc:
                return self.json_response({'error': str(exc)}, 409)
            except (ValueError, KeyError, TypeError) as exc:
                return self.json_response({'error': str(exc)}, 400)
            except OSError as exc:
                return self.json_response({'error': 'Speichern fehlgeschlagen. Vorheriger Stand bleibt erhalten: ' + str(exc)}, 500)

    class LocalServer(ThreadingHTTPServer):
        def server_close(self):
            super().server_close()
            lease.close()

    try:
        server = LocalServer(('127.0.0.1', port), Handler)
    except Exception:
        lease.close()
        raise
    server.store = store
    server.daemon_threads = True
    return server
