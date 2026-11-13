#!/usr/bin/env python3
"""Install a checksum-verified official Pear release without changing Kali packages."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import urllib.request

VERSION='3.12.0'
NAME=f'youtube-music_{VERSION}_amd64.deb'
SHA256='cbf8996f565cbe01cd3a37cc9df0e52da3dcc3b889541117b512be7e4f2afde3'
URL=f'https://github.com/pear-devs/pear-desktop/releases/download/v{VERSION}/{NAME}'

def write_private(path,data):
    path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    fd,name=tempfile.mkstemp(dir=path.parent,prefix='.config-')
    with os.fdopen(fd,'w') as out:json.dump(data,out,indent=2)
    Path(name).replace(path)

def main():
    if os.geteuid()==0:raise SystemExit('Run as your desktop user, without sudo.')
    if subprocess.check_output(['dpkg','--print-architecture'],text=True).strip()!='amd64':
        raise SystemExit('This pinned release package is for amd64 only.')
    home=Path.home();cache=home/'.cache/laptop-music-install';cache.mkdir(parents=True,exist_ok=True)
    package=cache/NAME
    if not package.exists() or hashlib.sha256(package.read_bytes()).hexdigest()!=SHA256:
        partial=package.with_suffix('.partial')
        with urllib.request.urlopen(URL,timeout=45) as response,partial.open('wb') as out:
            shutil.copyfileobj(response,out)
        if hashlib.sha256(partial.read_bytes()).hexdigest()!=SHA256:raise RuntimeError('Release checksum mismatch')
        partial.replace(package)
    root=home/'.local/opt/pear-desktop';root.mkdir(parents=True,exist_ok=True)
    version=root/VERSION
    if not version.exists():
        stage=Path(tempfile.mkdtemp(prefix='.install-',dir=root))
        subprocess.run(['dpkg-deb','-x',str(package),str(stage)],check=True)
        if not (stage/'opt/YouTube Music/youtube-music').is_file():raise RuntimeError('Unexpected release layout')
        stage.replace(version)
    temporary=root/'.current-new';temporary.unlink(missing_ok=True)
    temporary.symlink_to(VERSION,target_is_directory=True);temporary.replace(root/'current')
    profile=home/'.local/share/laptop-music/player-profile';profile.mkdir(parents=True,exist_ok=True,mode=0o700)
    config=profile/'config.json'
    data=json.loads(config.read_text()) if config.exists() else {}
    data.setdefault('window-size',{'width':1100,'height':650})
    data.setdefault('window-position',{'x':-1,'y':-1})
    options=data.setdefault('options',{})
    defaults={'autoUpdates':True,'alwaysOnTop':False,'hideMenu':False,'hideMenuWarned':False,
        'startAtLogin':False,'disableHardwareAcceleration':False,'removeUpgradeButton':False,
        'restartOnConfigChanges':False,'trayClickPlayPause':False,'autoResetAppCache':False,
        'likeButtons':'','swapLikeButtonsOrder':False,'proxy':'','startingPage':'',
        'overrideUserAgent':False,'usePodcastParticipantAsArtist':False}
    for key,value in defaults.items():options.setdefault(key,value)
    options.update(tray=True,appVisible=True)
    options.setdefault('resumeOnStart',True)
    themes=options.setdefault('themes',[])
    theme=home/'.local/share/laptop-music/player-fast.css'
    theme.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(Path(__file__).resolve().parent/'player-fast.css',theme)
    if str(theme) not in themes:themes.append(str(theme))
    plugins=data.setdefault('plugins',{})
    plugins.setdefault('performance-improvement',{}).update(enabled=True)
    shortcuts=plugins.setdefault('shortcuts',{})
    shortcuts.update(enabled=True,overrideMediaKeys=False)
    shortcuts.setdefault('global',{'previous':'','playPause':'','next':''})
    shortcuts.setdefault('local',{'previous':'','playPause':'','next':''})
    # No network control server or third-party account integrations are needed.
    plugins.setdefault('api-server',{}).update(enabled=False)
    plugins.setdefault('do-not-track',{}).update(enabled=True,cache=True,blocker='In player',
        additionalBlockLists=[],disableDefaultLists=False)
    write_private(config,data)
    print('Pear Desktop '+VERSION+' installed locally. Close-to-tray and MPRIS are enabled.')
    print('Official release SHA-256 verified; Kali packages were not modified.')

if __name__=='__main__':main()
