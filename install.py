#!/usr/bin/env python3
"""Install the standalone music client's desktop widget for the current user."""
import os
from pathlib import Path
import shutil
import subprocess

if os.geteuid()==0:raise SystemExit('Run as your desktop user, without sudo.')
home=Path.home();source=Path(__file__).resolve().parent;target=home/'.local/share/laptop-music'
target.mkdir(parents=True,exist_ok=True)
for name in ['widget.py','mpris.py','player.py','player-fast.css']:shutil.copy2(source/name,target/name)
units=home/'.config/systemd/user';units.mkdir(parents=True,exist_ok=True)
(units/'laptop-music-widget.service').write_text(f'''[Unit]
Description=YouTube Music desktop widget for the standalone player
PartOf=graphical-session.target

[Service]
Type=simple
Environment=DISPLAY=:0
Environment=XAUTHORITY={home}/.Xauthority
Environment=NO_AT_BRIDGE=1
Environment=GIO_USE_VFS=local
ExecStart=/usr/bin/python3 {target}/widget.py
Restart=on-failure
RestartSec=10
Nice=10
UMask=0077
''')
autostart=home/'.config/autostart';autostart.mkdir(parents=True,exist_ok=True)
(autostart/'laptop-music-widget.desktop').write_text('''[Desktop Entry]
Type=Application
Name=YouTube Music Widget
Exec=systemctl --user start laptop-music-widget.service
OnlyShowIn=XFCE;
Terminal=false
''')
commands=home/'.local/bin';commands.mkdir(parents=True,exist_ok=True)
launcher=commands/'laptop-music'
launcher.write_text('''#!/bin/sh
exec systemctl --user start laptop-music-widget.service
''');launcher.chmod(0o755)
apps=home/'.local/share/applications';apps.mkdir(parents=True,exist_ok=True)
(apps/'laptop-music-player.desktop').write_text(f'''[Desktop Entry]
Type=Application
Name=YouTube Music (widget player)
Comment=Standalone music player with close-to-tray playback
Exec=/usr/bin/python3 {target}/player.py
Icon=multimedia-player
Categories=AudioVideo;Audio;
Terminal=false
''')
(apps/'laptop-music.desktop').write_text(f'''[Desktop Entry]
Type=Application
Name=YouTube Music Widget
Comment=Desktop controls for the standalone YouTube Music player
Exec={launcher}
Icon=multimedia-player
Categories=AudioVideo;Audio;
Terminal=false
''')
subprocess.run(['systemctl','--user','daemon-reload'],check=True)
print('YouTube Music Widget installed for the current desktop user.')
