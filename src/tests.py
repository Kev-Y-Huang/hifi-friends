import queue
import socket
import unittest
from unittest.mock import MagicMock, mock_open, patch, Mock

from client_paxos import Client, Song
from server_paxos import Server
from utils import Operation, Update, ServerOperation
from wire_protocol import (
    pack_packet, 
    unpack_packet, 
    pack_opcode, 
    unpack_opcode, 
    pack_num, 
    unpack_num, 
    pack_state, 
    unpack_state, 
    pack_audio_meta, 
    unpack_audio_meta
)
from paxos import Paxos
from machines import Machine, MACHINE_ZERO, MACHINE_ONE, MACHINE_TWO, get_other_machines

HOST = 'localhost'
TCP_PORT = 1538
UDP_PORT = 1539
CLIENT_UPDATE_PORT = 1540

BUFF_SIZE = 65536
CHUNK = 10*1024

class TestMachines(unittest.TestCase):
    def test_get_other_machines(self):
        other_machines = get_other_machines(0)
        self.assertEqual(other_machines[1].id, 1)
        
        other_machines = get_other_machines(1)
        self.assertEqual(other_machines[0].id, 0)

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
        self.mock_socket = MagicMock()
        self.mock_queue = MagicMock()


    def tearDown(self):
        self.client = None
        self.mock_socket = None
        self.mock_queue = None


    @patch('client_paxos.socket.socket')
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


    @patch('client_paxos.socket.socket')
    def test_queue_song(self, mock_socket):
        self.setUp()
        self.file = MagicMock()
        mock_send = MagicMock()
        mock_socket.return_value.send = mock_send

        self.client.queue_song(self.file.filename)

        mock_send.assert_called()
        self.tearDown()


    @patch('client_paxos.socket.socket')
    def test_get_song_list(self, mock_socket):
        self.setUp()
        mock_recv = MagicMock(return_value=b'test song 1\ntest song 2')
        mock_socket.return_value.recv.return_value = mock_recv()

        self.client.get_song_list()

        mock_socket.return_value.send.assert_called()
        self.tearDown()


    def test_pause_stream(self):
        self.client.stream_tcp_sock = self.mock_socket
        self.client.stream = True
        self.client.server_tcp = self.mock_socket
        self.client.server_tcp.recv.return_value = b'Test pause'
        self.client.pause_stream()
        self.assertTrue(self.client.is_paused)


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


class TestPaxos(unittest.TestCase):

    def setUp(self):
        self.paxos = Paxos(1)

    def test_send_prepare(self):
        conn = Mock()
        self.paxos.machines = {2: Mock(conn=conn), 3: Mock(conn=conn)}
        self.paxos.send_prepare()
        conn.send.assert_any_call(pack_opcode(ServerOperation.PREPARE))
        conn.send.assert_any_call(pack_packet(self.paxos.server_id, self.paxos.gen_number, ""))

    def test_send_promise(self):
        conn = Mock()
        proposer = Mock(conn=conn)
        proposer_id = 2
        self.paxos.machines = {proposer_id: proposer}
        self.paxos.promise_value = 0
        self.paxos.send_promise(proposer_id, "100")
        conn.send.assert_any_call(pack_opcode(ServerOperation.PROMISE))
        conn.send.assert_any_call(pack_packet(self.paxos.server_id, 100, ""))

    def test_handle_promise_no_accept(self):
        server_id = 1
        self.paxos.machines = {1: Mock()}
        self.paxos.gen_number = 100
        self.paxos.accept_operation = ""
        self.paxos.promise_value = 0
        self.paxos.handle_promise(server_id, 100, "file.wav")
        self.assertEqual(self.paxos.promise_value, 0)
        self.assertEqual(self.paxos.accept_operation, "")
        self.assertTrue(self.paxos.machines[server_id].accepted)


class TestWireProtocol(unittest.TestCase):
    def test_pack_packet(self):
        expected_output = b'1|2|hello world'
        self.assertEqual(pack_packet(1, 2, 'hello world'), expected_output)

    def test_unpack_packet(self):
        packet = b'1|2|3|hello world'
        expected_output = (1, 2, '3')
        self.assertEqual(unpack_packet(packet), expected_output)

    def test_pack_opcode(self):
        expected_output = b'\x01'
        self.assertEqual(pack_opcode(Operation.UPLOAD), expected_output)

    def test_unpack_opcode(self):
        opcode = b'\x02'
        expected_output = Operation.QUEUE
        self.assertEqual(unpack_opcode(opcode), expected_output)

    def test_pack_num(self):
        expected_output = b'00001010'
        self.assertEqual(pack_num(10, 8), expected_output)

    def test_unpack_num(self):
        num = b'00001010'
        expected_output = 10
        self.assertEqual(unpack_num(num), expected_output)

    def test_pack_state(self):
        expected_output = b'\x00\x00\x00\x01\x00\x00\x00\x02\x00\x00\x00\x02'
        self.assertEqual(pack_state(1, 2, Update.PLAY), expected_output)

    def test_unpack_state(self):
        state = b'\x00\x00\x00\x01\x00\x00\x00\x02\x00\x00\x00\x02'
        expected_output = (1, 2, Update.PLAY)
        self.assertEqual(unpack_state(state), expected_output)

    def test_pack_audio_meta(self):
        expected_output = b'\x00\x00\x00\x00\x04\x00\x00\x00\x80\x00\x00\x01\x02'
        self.assertEqual(pack_audio_meta(4, 128, 258), expected_output)

    def test_unpack_audio_meta(self):
        audio_meta = b'\x00\x00\x00\x00\x04\x00\x00\x00\x80\x00\x00\x01\x02'
        expected_output = (0, 4, 128, 258)
        self.assertEqual(unpack_audio_meta(audio_meta), expected_output)


if __name__ == '__main__':
    unittest.main()
