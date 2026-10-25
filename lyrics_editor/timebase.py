"""Half-open audio intervals with outward video coverage.

Snap only representation noise within 1e-7 of an integer frame (~4.2 ns at 24
FPS). Never round arbitrary audio annotations to milliseconds or shift neighbours.
"""
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP

FRAME_EPSILON = Decimal('0.0000001')


def decimal(value):
    if isinstance(value, bool):
        raise ValueError('Eine Zahl wird erwartet.')
    try:
        result = Decimal(str(value))
    except Exception as exc:
        raise ValueError('Ungültige Zahl.') from exc
    if not result.is_finite():
        raise ValueError('Zeitwerte müssen endlich sein.')
    return result


def frame_position(seconds, fps=24):
    value, rate = decimal(seconds), decimal(fps)
    if value < 0 or rate <= 0:
        raise ValueError('Zeit muss positiv und die Bildrate größer als null sein.')
    position = value * rate
    nearest = position.to_integral_value(rounding=ROUND_HALF_UP)
    return nearest if abs(position - nearest) <= FRAME_EPSILON else position


def seconds_to_frame(seconds, fps=24, rounding='floor'):
    modes = {'floor': ROUND_FLOOR, 'ceil': ROUND_CEILING, 'nearest': ROUND_HALF_UP}
    if rounding not in modes:
        raise ValueError('Unbekannte Rundung.')
    return int(frame_position(seconds, fps).to_integral_value(rounding=modes[rounding]))


def frames_to_seconds(frame, fps=24):
    value, rate = decimal(frame), decimal(fps)
    if value < 0 or value != int(value) or rate <= 0:
        raise ValueError('Ungültige Frameposition.')
    return float(value / rate)


def frame_interval(start, end, fps=24):
    a, b = decimal(start), decimal(end)
    if a < 0 or b <= a:
        raise ValueError('Das Ende muss nach dem nichtnegativen Beginn liegen.')
    return seconds_to_frame(a, fps, 'floor'), seconds_to_frame(b, fps, 'ceil')


def validate_interval(start, end, duration, fps=24):
    a, b, limit = decimal(start), decimal(end), decimal(duration)
    frames = frame_interval(a, b, fps)
    if b > limit:
        raise ValueError('Die Endzeit liegt hinter dem Songende.')
    return float(a), float(b), frames


def timecode(seconds, fps=24):
    frame = seconds_to_frame(seconds, fps, 'nearest')
    return f'{frame // (fps*3600):02}:{frame // (fps*60) % 60:02}:{frame // fps % 60:02}:{frame % fps:02}'
