# YouTube Music desktop bar

A compact Android-style GTK3 bar for Kali/Debian XFCE X11, paired with [Pear Desktop](https://github.com/pear-devs/pear-desktop) (the standalone YouTube Music desktop client). Artwork sits on the left, with a single title/artist line and a flat control row. The background follows the artwork's colors. Right-click the artwork or title for its menu.

![Sample widget layout](docs/preview.png)

## Start listening

1. Click the widget's play arrow, or open **YouTube Music (widget player)** from Applications.
2. Sign in to the standalone player if you want your library, then choose a song.
3. Close its window with X. The player hides to the tray and continues playing; the desktop widget remains connected. Brave can be fully closed.
4. To stop the application entirely, use **Quit** in its own tray menu. Clicking play in an idle widget opens it again.

The music application must still run in the background, like a phone music app. The widget itself is a remote, not an audio streaming engine. The old shared-Brave and dedicated-Brave-profile backends are no longer used: ordinary YouTube tabs are never selected as a fallback.

The installation enables Pear's close-to-tray setting, Shortcuts/MPRIS plugin, and built-in blocking plugin. Blocking effectiveness depends on the upstream client and service behavior; no subscription features or ad-free guarantee are supplied by the widget. The local HTTP control server remains disabled. No YouTube API key, extra OAuth app, password copy or browser extension is needed.

The installer also enables the client's performance option and adds a reduced-motion theme for menus and navigation. Hardware acceleration stays enabled. The laptop's battery/power profile is not changed; power-saving mode and network latency can still affect responsiveness.

## Controls and placement

- Previous, play/pause and next use the standalone client's local [MPRIS interface](https://specifications.freedesktop.org/mpris/latest/Player_Interface.html).
- Like/dislike icons match the reference layout but remain disabled: MPRIS does not expose rating actions. Rate songs in the music player itself.
- Drag the artwork or title to move the bar.
- Right-click → **Set position** saves a preferred location. **Reset position** returns to those exact coordinates, including near screen edges. Temporary moves do not overwrite the preferred location.
- The bar sits below normal application windows and starts after login. Neither it nor the player needs Codex to remain open.

The widget verifies the actual executable owning a media service and accepts only the locally installed Pear executable. The check is repeated immediately before sending commands. Missing or unverified processes are rejected.

Artwork is decoded in memory. Song details and artwork are not saved, uploaded or logged by the widget. The player stores its own ordinary website/session data privately in `~/.local/share/laptop-music/player-profile`. Placement is stored in `~/.config/laptop-music/position.json`. Do not publish either directory. Any older `brave-profile` directory is preserved but unused.

## Install

Needs systemd user services, Python3, dpkg-deb, GTK3/PyGObject and Cairo (`python3-gi`, `python3-gi-cairo`, `gir1.2-gtk-3.0` on Debian/Kali). Run as your desktop user:

```bash
git clone https://github.com/0xSaadBinSultan/youtube-music-widget.git
cd youtube-music-widget
python3 install-player.py
python3 install.py
laptop-music
```

The player installer downloads the official **3.12.0 amd64 Linux release**, verifies its published SHA-256 digest, and extracts it under `~/.local/opt/pear-desktop`. It does not use sudo or alter Kali's installed packages. Other CPU architectures need the appropriate upstream release and checksum.

The launcher uses an existing root-owned Chromium sandbox helper, when available, through `CHROME_DEVEL_SANDBOX`; it does not add `--no-sandbox`. The current laptop has this helper installed with Brave; Brave itself does not need to run. A fresh machine must provide working Electron sandbox support and the normal desktop/audio runtime libraries.

The widget assumes X11 display `:0` and `~/.Xauthority`; adjust its user service for another desktop session. The player runs in an independent user service, so restarting or closing the widget does not terminate music.

```bash
systemctl --user restart laptop-music-widget.service
systemctl --user stop laptop-music-widget.service
```

To stop the widget appearing after login, add `Hidden=true` to `~/.config/autostart/laptop-music-widget.desktop`. Its **Quit widget** menu closes only the widget for the current session.
