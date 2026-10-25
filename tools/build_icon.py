"""Generate multi-resolution Windows ICO and PNG from the editable SVG source."""
from pathlib import Path
import struct

from PySide6.QtCore import QByteArray, QBuffer, QIODevice, Qt
from PySide6.QtGui import QGuiApplication, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer


def build():
    application = QGuiApplication.instance() or QGuiApplication([])
    assets = Path(__file__).resolve().parents[1] / 'lyrics_studio/assets'
    image = QImage(512, 512, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    QSvgRenderer(str(assets / 'icon.svg')).render(painter)
    painter.end()
    if not image.save(str(assets / 'icon.png')):
        raise RuntimeError('PNG konnte nicht erzeugt werden.')
    sizes = [16, 24, 32, 48, 64, 128, 256]
    offset = 6 + 16 * len(sizes)
    directory, payloads = [], []
    for size in sizes:
        output = QByteArray()
        buffer = QBuffer(output)
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        scaled = image.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio,
                              Qt.TransformationMode.SmoothTransformation)
        if not scaled.save(buffer, 'PNG'):
            raise RuntimeError('Icon-Auflösung konnte nicht erzeugt werden.')
        payload = bytes(output)
        directory.append(struct.pack('<BBBBHHII', size % 256, size % 256, 0, 0, 1, 32, len(payload), offset))
        payloads.append(payload)
        offset += len(payload)
    (assets / 'icon.ico').write_bytes(struct.pack('<HHH', 0, 1, len(sizes)) + b''.join(directory + payloads))


if __name__ == '__main__':
    build()
