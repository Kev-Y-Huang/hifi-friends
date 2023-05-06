import queue
import socket
import unittest
from unittest.mock import MagicMock, mock_open, patch

from client import Client, Song
from server import Server
from utils import Operation, Update
from wire_protocol import (pack_num, pack_opcode, pack_state, unpack_num,
                           unpack_state)

HOST = 'localhost'
TCP_PORT = 1538
UDP_PORT = 1539
CLIENT_UPDATE_PORT = 1540

BUFF_SIZE = 65536
CHUNK = 10*1024


class TestSong(unittest.TestCase):
    def test_init(self):
        s = Song(width=2, sample_rate=44100, n_channels=2)
        self.assertEqual(s.width, 2)
        self.assertEqual(s.sample_rate, 44100)
        self.assertEqual(s.n_channels, 2)
        self.assertIsInstance(s.frames, queue.Queue)

    def test_update_metadata(self):
        s = Song()
        s.update_metadata(width=2, sample_rate=44100, n_channels=2)
        self.assertEqual(s.width, 2)
        self.assertEqual(s.sample_rate, 44100)
        self.assertEqual(s.n_channels, 2)

    def test_add_frame(self):
        s = Song()
        s.add_frame(b"1234")
        self.assertEqual(s.frames.get(), b"1234")


class TestClient(unittest.TestCase):
    def setUp(self):
        self.client = Client()
        self.mock_socket = MagicMock(spec=socket.socket)
        self.mock_queue = MagicMock(spec=queue.Queue)


    def tearDown(self):
        self.client = None
        self.mock_socket = None
        self.mock_queue = None


    @patch('client.socket.socket')
    def test_upload_file_flask(self, mock_socket):
        self.setUp()
        # create object self.file with attribute filename
        self.file = MagicMock()
        # Mock send oobject
        mock_send = MagicMock()
        mock_socket.return_value.send = mock_send

        self.client.upload_file_flask(self.file)
        mock_send.assert_called()
        self.tearDown()


    @patch('client.socket.socket')
    def test_queue_song(self, mock_socket):
        self.setUp()
        self.file = MagicMock()
        mock_send = MagicMock()
        mock_socket.return_value.send = mock_send

        self.client.queue_song(self.file.filename)

        mock_send.assert_called()
        self.tearDown()


    @patch('client.socket.socket')
    def test_get_song_list(self, mock_socket):
        self.setUp()
        mock_recv = MagicMock(return_value=b'test song 1\ntest song 2')
        mock_socket.return_value.recv.return_value = mock_recv()

        self.client.get_song_list()

        mock_socket.return_value.send.assert_called()
        self.tearDown()


    def test_get_current_queue(self):
        self.client.server_tcp = self.mock_socket
        self.client.server_tcp.recv.return_value = b'Test queue'
        self.assertEqual(self.client.get_current_queue(), 'Test queue')
        self.client.server_tcp.recv.assert_called_once_with(1024)
        self.client.server_tcp.send.assert_called_once_with(b'\x04')


    def test_pause_stream(self):
        self.client.stream = True
        self.client.server_tcp = self.mock_socket
        self.client.server_tcp.recv.return_value = b'Test pause'
        self.client.pause_stream()
        self.assertTrue(self.client.is_paused)
        self.client.server_tcp.recv.assert_called_once_with(1024)
        self.client.server_tcp.send.assert_called_once_with(b'\x05')


    def test_get_audio_data(self):
        self.client.audio_udp_sock = self.mock_socket
        self.mock_socket.sendto.return_value = None
        self.mock_socket.recvfrom.return_value = (b'frame_data', ('127.0.0.1', 1234))
        self.mock_queue.put.return_value = None
        self.client.get_audio_data()
        self.mock_socket.sendto.assert_called_once_with(b'Connect', (self.client.host, self.client.audio_udp_port))
    
    
    def test_process_song(self):
        self.client.stream = MagicMock()
        self.client.curr_song_frames = MagicMock()
        self.client.exit.set()

        self.assertIsNone(self.client.process_song())


    @patch('pyaudio.PyAudio')
    def test_stream_audio(self, mock_pyaudio):
        self.client.song_queue.put(MagicMock())
        self.client.exit.set()

        self.assertIsNone(self.client.stream_audio())


    def test_server_update(self):
        mock_sock = MagicMock()
        mock_sock.recvfrom.return_value = (b'state', '127.0.0.1')
        self.client.update_udp_sock = mock_sock
        self.client.exit.set()

        self.assertIsNone(self.client.server_update())

if __name__ == '__main__':
    unittest.main()
