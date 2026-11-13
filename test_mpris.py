"""Regression checks for selecting only the standalone music application."""
import unittest
from unittest.mock import patch
from mpris import MusicMedia

NATIVE='org.mpris.MediaPlayer2.YoutubeMusic'
BRAVE='org.mpris.MediaPlayer2.brave.instance111'

class Reply:
    def __init__(self,value):self.value=value
    def unpack(self):return (self.value,)

class Bus:
    def __init__(self):
        self.owners={BRAVE:111,NATIVE:222};self.actions=[]
        self.metadata={'xesam:title':'Music track','xesam:artist':['Artist'],
                       'mpris:trackid':'/track/1','mpris:length':180_000_000}
    def call_sync(self,service,path,interface,method,parameters,*args):
        if method=='ListNames':return Reply(list(self.owners))
        if method=='GetConnectionUnixProcessID':return Reply(self.owners[parameters.unpack()[0]])
        if method=='GetAll':return Reply({'PlaybackStatus':'Paused' if service==NATIVE else 'Playing',
            'Metadata':self.metadata,'CanControl':True,'CanPlay':True,'CanPause':True,
            'CanGoNext':True,'CanGoPrevious':True,'CanSeek':True})
        raise AssertionError('Unexpected D-Bus method')
    def call(self,service,path,interface,method,*args):self.actions.append((service,method))

class RoutingTests(unittest.TestCase):
    def setUp(self):
        self.bus=Bus();self.media=MusicMedia(self.bus)
        self.check=patch('mpris.process_is_music_app',side_effect=lambda pid:pid==222)
        self.check.start();self.addCleanup(self.check.stop)

    def test_playing_youtube_does_not_override_paused_music(self):
        state=self.media.poll()
        self.assertEqual(state['service'],NATIVE)
        self.assertTrue(self.media.command('PlayPause'))
        self.assertEqual(self.bus.actions,[(NATIVE,'PlayPause')])

    def test_quitting_music_never_falls_back_to_youtube(self):
        self.media.poll();del self.bus.owners[NATIVE]
        self.assertFalse(self.media.poll()['connected'])
        self.assertFalse(self.media.command('PlayPause'))
        self.assertEqual(self.bus.actions,[])

    def test_changed_process_owner_is_rejected_before_next_poll(self):
        self.media.poll();self.bus.owners[NATIVE]=111
        self.assertFalse(self.media.command('Next'))
        self.assertEqual(self.bus.actions,[])

    def test_player_can_connect_before_a_song_is_selected(self):
        self.bus.metadata={}
        state=self.media.poll()
        self.assertTrue(state['connected']);self.assertFalse(state['ready'])

if __name__=='__main__':unittest.main()
