"""Keep one local editor session per open project, preserving unsaved work on switching."""
import threading

from lyrics_editor.server import make_server


class Sessions:
    def __init__(self):
        self.servers = {}

    def open(self, project):
        key = str(project.directory)
        if key not in self.servers:
            server = make_server(project.data, project.state_dir, port=0, title=project.info['name'])
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            self.servers[key] = (server, thread)
        server = self.servers[key][0]
        with server.store.lock:
            server.store.title = project.info['name']
        return server

    def dirty(self):
        result = []
        for server, _ in self.servers.values():
            with server.store.lock:
                if server.store.state()['dirty']:
                    result.append(server.store)
        return result

    def save_all(self):
        for server, _ in self.servers.values():
            with server.store.lock:
                server.store.save(server.store.revision)

    def close_project(self, project):
        entry = self.servers.pop(str(project.directory), None)
        if entry:
            server, thread = entry
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def close(self):
        for server, thread in self.servers.values():
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
        self.servers.clear()
