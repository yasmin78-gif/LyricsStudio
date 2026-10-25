"""Interoperable subtitle export from explicitly reviewed editor content."""
from decimal import Decimal, ROUND_HALF_UP
import math


def srt_timestamp(seconds):
    millis = int((Decimal(str(seconds)) * 1000).to_integral_value(rounding=ROUND_HALF_UP))
    return f'{millis // 3600000:02}:{millis // 60000 % 60:02}:{millis // 1000 % 60:02},{millis % 1000:03}'


def srt_document(document, offset=0):
    if not math.isfinite(offset) or offset < 0:
        raise ValueError('Der Startversatz muss eine nichtnegative Zahl sein.')
    rows = document['confirmed_occurrences']
    if not rows:
        raise ValueError('Noch keine bestätigten Textpassagen vorhanden. Bitte zuerst im Editor prüfen und bestätigen.')
    blocks = []
    for index, row in enumerate(sorted(rows, key=lambda r: r['timing']['start_time']), 1):
        timing = row['timing']
        if not row['manual_text_confirmation'] or not timing['manual_confirmation']:
            raise ValueError('Der Export enthält eine unbestätigte Passage.')
        start = srt_timestamp(timing['start_time'] + offset)
        end = srt_timestamp(timing['end_time'] + offset)
        if start == end:
            raise ValueError('Eine Passage ist für das SRT-Millisekundenraster zu kurz.')
        blocks.append(f'{index}\n{start} --> {end}\n{row["text"].strip()}\n')
    return '\n'.join(blocks)
