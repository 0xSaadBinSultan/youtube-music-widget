"""Launch the standalone music client independently of the widget."""
import os
from pathlib import Path
import stat
import subprocess
import uuid
from mpris import APP_BINARY, PROFILE

def sandbox_helper():
    for name in ['/opt/brave.com/brave/chrome-sandbox','/usr/lib/chromium/chrome-sandbox',
                 '/opt/google/chrome/chrome-sandbox','/usr/share/code/chrome-sandbox']:
        try:
            info=Path(name).stat()
            if info.st_uid==0 and info.st_mode & stat.S_ISUID and not info.st_mode & 0o022:
                return name
        except OSError:pass
    return None

def open_player():
    if not APP_BINARY.is_file():raise RuntimeError('Install the standalone music client first')
    PROFILE.mkdir(parents=True,exist_ok=True,mode=0o700)
    # Closing the widget must not terminate the standalone music client.
    command=['systemd-run','--user','--collect','--no-block','--quiet',
        '--unit=laptop-music-player-'+uuid.uuid4().hex[:10],
        '--property=Type=exec','--property=PartOf=graphical-session.target','--property=UMask=0077',
        '--setenv=DISPLAY='+os.environ.get('DISPLAY',':0'),
        '--setenv=XAUTHORITY='+os.environ.get('XAUTHORITY',str(Path.home()/'.Xauthority')),
        '--setenv=GIO_USE_VFS=local','--setenv=NO_AT_BRIDGE=1']
    helper=sandbox_helper()
    if helper:command.append('--setenv=CHROME_DEVEL_SANDBOX='+helper)
    command.extend([str(APP_BINARY),'--user-data-dir='+str(PROFILE)])
    subprocess.run(command,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=5)

if __name__=='__main__':open_player()
