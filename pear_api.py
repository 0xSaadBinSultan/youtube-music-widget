"""Authenticated, loopback-only client for Pear Desktop's API Server plugin.

Independent of GTK, D-Bus and Qt, so it can be tested on every desktop OS.
"""
import json
import os
from pathlib import Path
import sys
import tempfile
import urllib.error
import urllib.request
import uuid

LIMIT = 1024 * 1024
COMMANDS = {'previous', 'toggle-play', 'next'}


def config_path():
    if os.environ.get('MUSIC_WIDGET_HOME'):
        return Path(os.environ['MUSIC_WIDGET_HOME']).expanduser() / 'connection.json'
    if sys.platform == 'win32':
        root = Path(os.environ.get('APPDATA', Path.home() / 'AppData/Roaming'))
    elif sys.platform == 'darwin':
        root = Path.home() / 'Library/Application Support'
    else:
        root = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config'))
    return root / 'youtube-music-widget' / 'connection.json'


class NoRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('The local music server must not redirect requests')


class PearClient:
    def __init__(self, path=None):
        self.path = Path(path) if path else config_path()
        try:
            self.config = json.loads(self.path.read_text(encoding='utf-8'))
            if not isinstance(self.config, dict):
                self.config = {}
        except (OSError, ValueError):
            self.config = {}
        self.config.setdefault('client_id', 'desktop-widget-' + uuid.uuid4().hex)
        self.port = self.valid_port(self.config.get('port', 26538))
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirects())

    @staticmethod
    def valid_port(value):
        if isinstance(value, bool) or not isinstance(value, int) or not 1024 <= value <= 65535:
            raise ValueError('Choose a port from 1024 to 65535')
        return value

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd, name = tempfile.mkstemp(dir=self.path.parent, prefix='.music-')
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as out:
                json.dump({**self.config, 'port': self.port}, out, indent=2)
            Path(name).replace(self.path)
        finally:
            Path(name).unlink(missing_ok=True)

    def request(self, path, method='GET', pairing=False):
        if path not in {'/api/v1/song', *('/api/v1/' + cmd for cmd in COMMANDS)} and not pairing:
            raise ValueError('Unsupported player action')
        headers = {'User-Agent': 'YouTubeMusicWidget/2.0', 'Accept': 'application/json'}
        token = self.config.get('token', '')
        if token and not pairing:
            headers['Authorization'] = 'Bearer ' + token
        request = urllib.request.Request(f'http://127.0.0.1:{self.port}{path}',
                                         data=b'' if method == 'POST' else None,
                                         headers=headers, method=method)
        try:
            with self.opener.open(request, timeout=120 if pairing else 4) as response:
                raw = response.read(LIMIT + 1)
        except urllib.error.HTTPError as exc:
            code = exc.code
            exc.close()
            if code in (401, 403):
                raise RuntimeError('Pair with Pear Desktop and approve its permission dialog') from None
            raise RuntimeError(f'Player request failed (HTTP {code})') from None
        except urllib.error.URLError:
            raise RuntimeError('Open Pear Desktop and enable API Server on 127.0.0.1') from None
        if len(raw) > LIMIT:
            raise ValueError('Player response too large')
        return json.loads(raw) if raw else None

    def pair(self):
        identifier = self.config['client_id']
        if not isinstance(identifier, str) or not identifier.startswith('desktop-widget-') or not identifier[15:].isalnum():
            raise ValueError('Invalid local client identifier')
        data = self.request('/auth/' + identifier, 'POST', pairing=True)
        token = data.get('accessToken') if isinstance(data, dict) else None
        if not isinstance(token, str) or not token or any(c.isspace() for c in token):
            raise ValueError('Player did not return an access token')
        self.config['token'] = token
        self.save()

    def song(self):
        data = self.request('/api/v1/song')
        if data is None:
            return {'title': 'Choose a song in Pear Desktop', 'artist': '', 'paused': True}
        if not isinstance(data, dict) or not isinstance(data.get('title'), str):
            raise ValueError('Unexpected player response')
        return {'title': data['title'][:500], 'artist': str(data.get('artist', ''))[:500],
                'paused': bool(data.get('isPaused', False))}

    def command(self, action):
        if action not in COMMANDS:
            raise ValueError('Unsupported player action')
        self.request('/api/v1/' + action, 'POST')
