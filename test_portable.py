"""Exercise the real loopback HTTP client and offline Qt frontend."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from PySide6.QtWidgets import QApplication
from pear_api import PearClient
from desktop import MusicWindow


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        self.do_GET()

    def do_GET(self):
        self.server.requests.append((self.command, self.path, self.headers.get('Authorization')))
        if self.path.startswith('/auth/'):
            self.send_response(200)
            data = {'accessToken': 'local-test-token'}
        elif self.server.redirect:
            self.send_response(302)
            self.send_header('Location', 'http://example.com/never-contact')
            self.end_headers()
            return
        elif self.headers.get('Authorization') != 'Bearer local-test-token':
            self.send_response(401)
            data = {}
        else:
            self.send_response(200)
            data = {'title': 'গান', 'artist': 'Demo artist', 'isPaused': True}
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())


class PortableTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.client = PearClient(Path(self.folder.name) / 'connection.json')
        self.client.port = self.server.server_port
        self.server.requests = []
        self.server.redirect = False

    def test_pair_persists_token_and_commands_use_authorization(self):
        self.client.pair()
        self.assertEqual(self.client.song(), {'title': 'গান', 'artist': 'Demo artist', 'paused': True})
        self.client.command('next')
        self.assertEqual(self.server.requests[-1], ('POST', '/api/v1/next', 'Bearer local-test-token'))
        restored = PearClient(self.client.path)
        self.assertEqual(restored.port, self.server.server_port)
        self.assertEqual(restored.config['token'], 'local-test-token')
        if os.name == 'posix':
            self.assertEqual(self.client.path.stat().st_mode & 0o777, 0o600)

    def test_unauthorized_requests_explain_pairing_without_leaking_token(self):
        with self.assertRaisesRegex(RuntimeError, 'Pair with Pear'):
            self.client.song()

    def test_redirect_cannot_send_bearer_token_to_another_host(self):
        self.client.pair()
        self.server.redirect = True
        with self.assertRaisesRegex(ValueError, 'must not redirect'):
            self.client.song()
        self.assertEqual(len(self.server.requests), 2)

    def test_invalid_actions_and_ports_never_send_requests(self):
        with self.assertRaises(ValueError):
            self.client.command('../../auth/unexpected')
        for port in [0, 65536, True, '26538']:
            with self.assertRaises(ValueError):
                self.client.valid_port(port)
        self.assertEqual(self.server.requests, [])

    def test_demo_never_contacts_a_player_and_closes(self):
        with patch('desktop.PearClient', side_effect=AssertionError('No player in demo')):
            window = MusicWindow(demo=True)
            window.show()
            self.app.processEvents()
            self.assertIn('Synthetic', window.artist.text())
            self.assertGreater(window.grab().width(), 300)
            self.assertTrue(all(not b.isEnabled() for b in window.buttons))
            window.close()
            self.app.processEvents()
            self.assertFalse(window.isVisible())


if __name__ == '__main__':
    unittest.main()
