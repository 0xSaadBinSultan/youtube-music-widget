"""Control only the installed standalone music client over local MPRIS."""
import base64
import os
from pathlib import Path
import stat
import time
import urllib.parse
import urllib.request

from gi.repository import Gio, GLib

PATH = '/org/mpris/MediaPlayer2'
PLAYER = 'org.mpris.MediaPlayer2.Player'
LIMIT = 4*1024*1024
APP_BINARY = Path.home()/'.local/opt/pear-desktop/current/opt/YouTube Music/youtube-music'
PROFILE = Path.home()/'.local/share/laptop-music/player-profile'

def process_is_music_app(pid):
    try:
        return (Path('/proc')/str(int(pid))/'exe').resolve(strict=True) == APP_BINARY.resolve(strict=True)
    except (OSError, ValueError): pass
    return False

def art_host(host):
    return any(host == domain or host.endswith('.'+domain)
               for domain in ('ytimg.com', 'googleusercontent.com', 'ggpht.com'))

class ArtworkRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parsed = urllib.parse.urlsplit(newurl)
        if parsed.scheme != 'https' or not art_host(parsed.hostname or ''):
            raise ValueError('Unsupported artwork redirect')
        return super().redirect_request(req, fp, code, msg, headers, newurl)

def read_artwork(url):
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme == 'file' and parsed.netloc in ('', 'localhost'):
        path = Path(urllib.request.url2pathname(parsed.path))
        fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
        with os.fdopen(fd, 'rb') as source:
            info = os.fstat(source.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size > LIMIT:
                raise ValueError('Artwork is not a small regular file')
            raw = source.read(LIMIT+1)
    elif parsed.scheme == 'https' and art_host(parsed.hostname or '') and not parsed.username:
        req = urllib.request.Request(url, headers={'User-Agent':'LaptopMusicWidget/1.0'})
        with urllib.request.build_opener(ArtworkRedirects()).open(req, timeout=8) as source:
            raw = source.read(LIMIT+1)
    elif url.startswith('data:image/') and ';base64,' in url and len(url) < LIMIT*2:
        raw = base64.b64decode(url.split(',',1)[1], validate=True)
    else:
        raise ValueError('Unsupported artwork address')
    if len(raw)>LIMIT: raise ValueError('Artwork too large')
    return raw

class MusicMedia:
    def __init__(self, bus=None):
        self.bus = bus or Gio.bus_get_sync(Gio.BusType.SESSION, None)
        self.service = None
        self.state = {'connected': False}

    def call(self, service, interface, method, parameters=None):
        return self.bus.call_sync(service, PATH, interface, method, parameters, None,
                                  Gio.DBusCallFlags.NONE, 1200, None)

    def is_music_player(self, service):
        try:
            pid = self.bus.call_sync('org.freedesktop.DBus','/org/freedesktop/DBus',
                'org.freedesktop.DBus','GetConnectionUnixProcessID',GLib.Variant('(s)',(service,)),
                None,Gio.DBusCallFlags.NONE,1200,None).unpack()[0]
            return process_is_music_app(pid)
        except GLib.Error: return False

    def poll(self):
        names = self.bus.call_sync('org.freedesktop.DBus','/org/freedesktop/DBus',
            'org.freedesktop.DBus','ListNames',None,None,Gio.DBusCallFlags.NONE,1200,None).unpack()[0]
        candidates = []
        for name in names:
            if not name.lower().startswith(('org.mpris.mediaplayer2.youtubemusic',
                                           'org.mpris.mediaplayer2.pear')): continue
            if not self.is_music_player(name): continue
            try:
                props = self.call(name,'org.freedesktop.DBus.Properties','GetAll',
                                  GLib.Variant('(s)',(PLAYER,))).unpack()[0]
                metadata = props.get('Metadata', {})
                score = 10*(props.get('PlaybackStatus')=='Playing') + 2*(name==self.service)
                if urllib.parse.urlsplit(metadata.get('xesam:url','')).hostname=='music.youtube.com': score+=100
                candidates.append((score, name, props, metadata))
            except GLib.Error: continue
        if not candidates:
            self.service = None; self.state = {'connected':False}; return self.state
        _, self.service, props, metadata = max(candidates, key=lambda item:(item[0],item[1]))
        artists = metadata.get('xesam:artist', [])
        if isinstance(artists,str): artists=[artists]
        self.state = {'connected':True,'service':self.service,'status':props.get('PlaybackStatus','Stopped'),
            'title':metadata.get('xesam:title') or 'YouTube Music — choose a song in the player',
            'artist':', '.join(artists) or metadata.get('xesam:album') or '',
            'ready':bool(metadata.get('xesam:title')),
            'art':metadata.get('mpris:artUrl',''),'track_id':metadata.get('mpris:trackid'),
            'position':max(0,int(props.get('Position',0))), 'length':max(0,int(metadata.get('mpris:length',0))),
            'sampled':time.monotonic(), 'rate':float(props.get('Rate',1.0)),
            'can_play':props.get('CanControl',False) and (props.get('CanPause',False) if props.get('PlaybackStatus')=='Playing' else props.get('CanPlay',False)),
            'can_next':props.get('CanControl',False) and props.get('CanGoNext',False),
            'can_previous':props.get('CanControl',False) and props.get('CanGoPrevious',False),
            'can_seek':props.get('CanControl',False) and props.get('CanSeek',False)}
        return self.state

    def command(self, method, target=None, callback=None):
        if not self.service or not self.is_music_player(self.service): return False
        if method not in {'PlayPause','Previous','Next','SetPosition'}: raise ValueError('Unsupported media action')
        key = {'PlayPause':'can_play','Previous':'can_previous','Next':'can_next','SetPosition':'can_seek'}[method]
        if not self.state.get(key): return False
        parameters = None
        if method=='SetPosition':
            track = self.state.get('track_id')
            if not track or track=='/org/mpris/MediaPlayer2/TrackList/NoTrack': return False
            target = max(0,min(int(target),self.state.get('length',0)))
            parameters = GLib.Variant('(ox)',(track,target))
        def complete(bus, result, _data):
            try: bus.call_finish(result); success=True
            except GLib.Error: success=False
            if callback: callback(success)
        self.bus.call(self.service,PATH,PLAYER,method,parameters,None,Gio.DBusCallFlags.NONE,
                      1500,None,complete,None)
        return True
