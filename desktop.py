#!/usr/bin/env python3
"""Portable desktop remote for an independently installed Pear Desktop player."""
import argparse
import sys
import threading
from pathlib import Path

from PySide6.QtCore import QObject, QSettings, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QApplication, QHBoxLayout, QInputDialog,
                               QLabel, QPushButton, QSlider, QVBoxLayout, QWidget)
from PySide6.QtCore import Qt
from pear_api import PearClient


class Results(QObject):
    done = Signal(str, object, str)


class MusicWindow(QWidget):
    def __init__(self, demo=False):
        super().__init__()
        self.demo = demo
        self.client = None if demo else PearClient()
        self.busy = False
        self.bridge = Results(self)
        self.bridge.done.connect(self.finished)
        self.settings = QSettings('0xSaadBinSultan', 'YouTubeMusicWidget')
        self.setWindowTitle('YouTube Music Remote' + (' — Demo' if demo else ''))
        self.resize(520, 230)
        self.setMinimumSize(360, 210)
        if not demo and self.settings.value('geometry'):
            self.restoreGeometry(self.settings.value('geometry'))
            if not any(self.frameGeometry().intersects(s.availableGeometry()) for s in QApplication.screens()):
                self.move(QApplication.primaryScreen().availableGeometry().topLeft())
        layout = QVBoxLayout(self)
        self.title = QLabel('Open Pear Desktop to start listening')
        self.title.setWordWrap(True)
        self.title.setStyleSheet('font-size:20px;font-weight:600')
        self.artist = QLabel('Authenticated local remote · Windows / macOS / Linux')
        self.artist.setWordWrap(True)
        layout.addWidget(self.title)
        layout.addWidget(self.artist)
        controls = QHBoxLayout()
        self.buttons = []
        for text, action in [('Previous', 'previous'), ('Play / Pause', 'toggle-play'), ('Next', 'next')]:
            button = QPushButton(text)
            button.clicked.connect(lambda checked=False, cmd=action: self.run_job('command', lambda: self.client.command(cmd)))
            controls.addWidget(button)
            self.buttons.append(button)
        layout.addLayout(controls)
        options = QHBoxLayout()
        self.pair_button = QPushButton('Pair with Pear')
        self.pair_button.clicked.connect(lambda: self.run_job('pair', self.client.pair))
        port = QPushButton('Port')
        port.clicked.connect(self.choose_port)
        downloads = QPushButton('Get Pear Desktop')
        downloads.clicked.connect(lambda: QDesktopServices.openUrl(QUrl('https://github.com/pear-devs/pear-desktop/releases/latest')))
        for button in (self.pair_button, port, downloads):
            options.addWidget(button)
        self.port_button = port
        layout.addLayout(options)
        opacity = QSlider(Qt.Orientation.Horizontal)
        opacity.setRange(40, 100)
        opacity.setValue(95)
        opacity.valueChanged.connect(lambda value: self.setWindowOpacity(value / 100))
        layout.addWidget(opacity)
        self.status = QLabel('Enable Pear’s API Server on 127.0.0.1 with authentication, then Pair.')
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.poll)
        self.timer.start(2000)
        self.setWindowOpacity(.95)
        if demo:
            self.title.setText('A quiet evening')
            self.artist.setText('Synthetic preview · no music account connected')
            self.status.setText('Demo mode · controls disabled · no network requests')
            for button in self.buttons + [self.pair_button, port]:
                button.setEnabled(False)
        else:
            for button in self.buttons:
                button.setEnabled(bool(self.client.config.get('token')))
            self.poll()

    def choose_port(self):
        if self.demo or self.busy:
            return
        port, ok = QInputDialog.getInt(self, 'Pear API port', 'Loopback port (127.0.0.1)', self.client.port, 1024, 65535)
        if ok:
            self.client.port = port
            self.client.config.pop('token', None)
            self.client.save()
            self.status.setText('Port changed. Pair with the player again.')

    def poll(self):
        if self.client and self.client.config.get('token'):
            self.run_job('poll', self.client.song)

    def run_job(self, kind, operation):
        if self.demo or self.busy:
            return
        self.busy = True
        self.pair_button.setEnabled(False)
        self.port_button.setEnabled(False)
        for button in self.buttons:
            button.setEnabled(False)
        if kind == 'pair':
            self.status.setText('Approve the connection in Pear Desktop (up to two minutes)…')
        bridge = self.bridge
        def work():
            data, error = None, ''
            try:
                data = operation()
            except RuntimeError as exc:
                error = str(exc)
            except Exception as exc:
                error = 'Player connection unavailable (' + type(exc).__name__ + ')'
            try:
                bridge.done.emit(kind, data, error)
            except RuntimeError:
                pass
        threading.Thread(target=work, daemon=True).start()

    def finished(self, kind, data, error):
        self.busy = False
        self.pair_button.setEnabled(True)
        self.port_button.setEnabled(True)
        for button in self.buttons:
            button.setEnabled(not error and bool(self.client.config.get('token')))
        if error:
            self.status.setText(error)
        elif kind == 'poll':
            self.title.setText(data['title'])
            self.artist.setText(data['artist'])
            self.status.setText('Paused' if data['paused'] else 'Playing')
        else:
            self.status.setText('Connected to the local player')
            self.poll()

    def closeEvent(self, event):
        if not self.demo:
            self.settings.setValue('geometry', self.saveGeometry())
        event.accept()


def main():
    parser = argparse.ArgumentParser(description='Portable local remote for Pear Desktop')
    parser.add_argument('--demo', action='store_true', help='Synthetic preview, no player or network')
    parser.add_argument('--export-preview', type=Path, help='Save a synthetic preview and exit; requires --demo')
    args = parser.parse_args()
    if args.export_preview and not args.demo:
        parser.error('--export-preview requires --demo')
    app = QApplication(sys.argv[:1])
    app.setStyle('Fusion')
    app.setStyleSheet('''QWidget { background:#221d2d; color:#f4efff; font-size:12px; }
        QPushButton { background:#493652; border:0; border-radius:7px; padding:9px; }
        QPushButton:hover { background:#655076; } QPushButton:disabled { color:#918099; }
        QSlider::groove:horizontal { background:#493652; height:5px; }
        QSlider::handle:horizontal { background:#dcc1ef; width:12px; margin:-4px 0; border-radius:6px; }''')
    window = MusicWindow(args.demo)
    window.show()
    if args.export_preview:
        def export():
            args.export_preview.parent.mkdir(parents=True, exist_ok=True)
            success = window.grab().save(str(args.export_preview))
            app.exit(0 if success else 1)
        QTimer.singleShot(150, export)
    return app.exec()


if __name__ == '__main__':
    raise SystemExit(main())
