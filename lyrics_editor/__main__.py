import argparse
from pathlib import Path
from .server import make_server


def main():
    parser = argparse.ArgumentParser(description='Lokaler Lyrics-Editor – ohne Resolve-Verbindung oder KI-Aufrufe.')
    parser.add_argument('--data', type=Path, default=Path('lyrics_timing.json'))
    parser.add_argument('--state-dir', type=Path, default=Path('editor-state'))
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    server = make_server(args.data, args.state_dir, args.port)
    print(f'Lyrics-Editor: http://127.0.0.1:{server.server_port}', flush=True)
    print(f'Entwurf: {server.store.path}', flush=True)
    print('Nur lokale Bearbeitung. Beenden mit Strg+C.', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
