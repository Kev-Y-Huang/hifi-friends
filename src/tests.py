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
        pass

    def shutDown(self):
        pass

    def test_upload_file(self):
        # self.setUp()
        # print(self.server.exit.is_set())
        # print("HERE")
        # self.shutDown()
        # print(self.server.exit.is_set())
        pass

    # @patch('client.socket.socket')
    # def test_upload_file_flask(self, mock_socket):
    #     mock_send = MagicMock()
    #     mock_socket.return_value.send = mock_send

    #     self.client.upload_file_flask(self.file)

    #     mock_send.assert_called()

    # @patch('client.socket.socket')
    # def test_queue_song(self, mock_socket):
    #     mock_send = MagicMock()
    #     mock_socket.return_value.send = mock_send

    #     self.client.queue_song(self.file.filename)

    #     mock_send.assert_called()

    # @patch('client.socket.socket')
    # def test_get_song_list(self, mock_socket):
    #     mock_recv = MagicMock(return_value=b'test song 1\ntest song 2')
    #     mock_socket.return_value.recv.return_value = mock_recv()

    #     self.client.get_song_list()

    #     mock_socket.return_value.send.assert_called()

    # @patch('client.socket.socket')
    # def test_get_current_queue(self, mock_socket):
    #     mock_recv = MagicMock(return_value=b'test song 1\ntest song 2')
    #     mock_socket.return_value.recv.return_value = mock_recv()

    #     self.client.get_current_queue()

    #     mock_socket.return_value.send.assert_called()

    # @patch('client.select.select')
    # @patch('client.socket.socket')
    # def test_get_audio_data(self, mock_socket, mock_select):
    #     mock_exit = MagicMock()
    #     self.client.exit = mock_exit

    #     mock_recvfrom = MagicMock(return_value=(b'\x00', 'address'))
    #     mock_decode = MagicMock(return_value='0')
    #     mock_unpack_num = MagicMock(return_value=44100)
    #     mock_song_queue_put = MagicMock()

    #     mock_socket.return_value.recvfrom = mock_recvfrom
    #     mock_socket.return_value.setsockopt = MagicMock()
    #     mock_decode.side_effect = [0, 1]
    #     mock_unpack_num.side_effect = [16, 16, 2]

    #     mock_select.return_value = ([mock_socket.return_value], [], [])
    #     self.client.song_queue.put = mock_song_queue_put

    #     self.client.get_audio_data()

    #     mock_socket.return_value.sendto.assert_called_once_with(b'Connect', (self.client.host, self.client.udp_port))
    #     mock_exit.is_set.assert_called()
    #     mock_song_queue_put.assert_called_once()

    # def tearDown(self):
    #     self.client.exit.set()


if __name__ == '__main__':
    unittest.main()
