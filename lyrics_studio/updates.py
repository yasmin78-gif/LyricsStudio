"""Read release metadata only. Updates are opened in the browser, never installed silently."""
from dataclasses import dataclass
import json
import os
import re
import urllib.error
import urllib.request

from . import __version__

REPOSITORY = 'yasmin78-gif/LyricsStudio'
RELEASES_URL = f'https://github.com/{REPOSITORY}/releases'
API_URL = f'https://api.github.com/repos/{REPOSITORY}/releases/latest'


def version_tuple(value):
    match = re.fullmatch(r'v?(\d+)\.(\d+)\.(\d+)', value)
    if not match:
        raise ValueError('Ungültige Versionsnummer.')
    return tuple(map(int, match.groups()))


@dataclass(frozen=True)
class UpdateResult:
    status: str
    message: str
    version: str = ''
    url: str = ''


def check_for_updates(current=__version__):
    headers = {'Accept': 'application/vnd.github+json',
               'User-Agent': f'LyricsStudio/{current}', 'X-GitHub-Api-Version': '2022-11-28'}
    # Optional private-repository access. Never embedded in the application or saved to settings.
    token = os.environ.get('LYRICS_STUDIO_UPDATE_TOKEN', '').strip()
    if token:
        headers['Authorization'] = 'Bearer ' + token
    try:
        request = urllib.request.Request(API_URL, headers=headers)
        with urllib.request.urlopen(request, timeout=6) as response:
            payload = response.read(1_000_001)
        if len(payload) > 1_000_000:
            raise ValueError('Release-Antwort ist zu groß.')
        release = json.loads(payload)
        if not isinstance(release, dict) or release.get('draft') or release.get('prerelease'):
            raise ValueError('Keine stabile Veröffentlichung.')
        tag = release.get('tag_name', '')
        newer = version_tuple(tag) > version_tuple(current)
        if newer:
            # Construct our own trusted repository URL; do not open arbitrary API-provided links.
            return UpdateResult('available', f'Update verfügbar: Lyrics Studio {tag.lstrip("v")}',
                                tag.lstrip('v'), RELEASES_URL + '/tag/' + tag)
        return UpdateResult('current', f'Lyrics Studio {current} ist aktuell.')
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return UpdateResult('unavailable', 'Updateprüfung nicht verfügbar: Repository privat oder noch kein Release veröffentlicht.')
        if exc.code in (401, 403):
            return UpdateResult('unavailable', 'Updateprüfung derzeit nicht möglich: Zugriff verweigert oder GitHub-Anfragelimit erreicht.')
        return UpdateResult('unavailable', 'Updateprüfung derzeit nicht möglich. Bitte später erneut versuchen.')
    except (OSError, ValueError, TypeError, KeyError):
        return UpdateResult('unavailable', 'Updateprüfung derzeit nicht möglich. Bitte Internetverbindung und Releasequelle prüfen.')
