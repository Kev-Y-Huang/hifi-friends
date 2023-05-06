import os
import queue
import select
import socket
import sys
import threading
import time

import pyaudio

from utils import queue_rows, Operation, ActionType
from wire_protocol import pack_num, pack_opcode, pack_state, unpack_num, unpack_state

HOST = socket.gethostname()
TCP_PORT = 1538
UDP_PORT = 1539
CLIENT_UPDATE_PORT = 1540

BUFF_SIZE = 65536
CHUNK = 10*1024


class Song:
    def __init__(self, width=None, sample_rate=None, n_channels=None):
        self.width = width
        self.sample_rate = sample_rate
        self.n_channels = n_channels

        self.frames = queue.Queue()

    def update_metadata(self, width, sample_rate, n_channels):
        self.width = width
        self.sample_rate = sample_rate
        self.n_channels = n_channels

    def add_frame(self, frame):
        self.frames.put(frame)


class Client:
    def __init__(self, host=HOST, tcp_port=TCP_PORT, udp_port=UDP_PORT, client_update_port=CLIENT_UPDATE_PORT):
        self.host = host

        # TCP connection to server
        self.tcp_port = tcp_port
        self.server_tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        # UDP connection to server
        self.udp_port = udp_port
        self.server_udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.server_udp.setsockopt(
            socket.SOL_SOCKET, socket.SO_RCVBUF, BUFF_SIZE)

        self.exit = threading.Event()

        self.song_queue = queue.Queue()

        self.stream = None

        self.client_update_port = client_update_port
        self.client_update_socket = socket.socket(
            socket.AF_INET, socket.SOCK_STREAM)
        self.client_update_socket.connect((self.host, self.client_update_port))
        self.next_action = ActionType.PING

        # Keeping track of song and frame index
        self.song_index = 0
        self.frame_index = 0
        self.server_song_index = 0
        self.server_frame_index = 0

        # Keeps track of whether audio is paused or not for everybody
        self.is_paused = False

    def upload_file(self, file_path):
        """
        Upload a file to the server.
        ...

        Parameters
        ----------
        file_path : str
            The path to the file to upload.
        """
        self.server_tcp.send(pack_opcode(Operation.UPLOAD))

        file_name = os.path.basename(file_path)
        self.server_tcp.send(pack_num(len(file_name), 16))
        self.server_tcp.send(file_name.encode())
        self.server_tcp.send(pack_num(os.path.getsize(file_path), 32))

        with open(file_path, 'rb') as file_to_send:
            self.server_tcp.sendall(file_to_send.read())

        print('File Sent')

    def upload_file_flask(self, file):
        """
        Upload a file to the server (for Flask application).
        ...

        Parameters
        ----------
        file_path : FileStorage object
            The file to upload.
        """
        self.server_tcp.send(pack_opcode(Operation.UPLOAD))

        file_name = file.filename
        self.server_tcp.send(pack_num(len(file_name), 16))
        self.server_tcp.send(file_name.encode())

        data = file.read()

        self.server_tcp.send(pack_num(len(data), 32))
        self.server_tcp.sendall(data)

        print('File Sent')

    def queue_song(self, filename):
        """
        Queue a song to be played by the server.
        ...

        Parameters
        ----------
        filename : str
            The name of the file to queue.
        """
        self.server_tcp.send(pack_opcode(Operation.QUEUE))
        self.server_tcp.send(filename.encode())

        # Wait for server to respond
        message = self.server_tcp.recv(1024).decode()
        print(message)

    def get_song_list(self):
        """
        Gets the available songs for queueing from the server and prints them.
        """
        self.server_tcp.send(pack_opcode(Operation.LIST))

        # Wait for server to respond
        message = self.server_tcp.recv(1024).decode()

        print(message)

        return message

    def get_current_queue(self):
        """
        Gets the current queue from the server and prints it.
        """
        self.server_tcp.send(pack_opcode(Operation.QUEUED))

        # Wait for server to respond
        message = self.server_tcp.recv(1024).decode()
        print(message)
        return message

    def get_audio_data(self):
        """
        Get audio data from the server.
        """
        inputs = [self.server_udp]
        self.server_udp.sendto(b'Connect', (self.host, self.udp_port))

        song = Song()
        while not self.exit.is_set():
            read_sockets, _, _ = select.select(inputs, [], [], 0.1)
            for sock in read_sockets:
                frame, _ = sock.recvfrom(BUFF_SIZE)

                try:
                    # Received audio header
                    if int(frame.decode(), 2) == 0:
                        width = unpack_num(sock.recvfrom(16)[0])
                        sample_rate = unpack_num(sock.recvfrom(16)[0])
                        n_channels = unpack_num(sock.recvfrom(16)[0])

                        song.update_metadata(width, sample_rate, n_channels)

                        self.song_queue.put(song)
                        song = Song()
                except:
                    song.add_frame(frame)

        print("closed")

    def process_song(self, frames):
        """
        Process the song queue.
        ...

        Parameters
        ----------
        song_q : queue.Queue
            The queue of song frames to process.
        """
        for frame in queue_rows(frames):
            if self.exit.is_set():
                return
            # TODO definitely can do this better
            while self.stream.is_stopped():
                # TODO figure out better place to move frame index update
                if self.frame_index < self.server_frame_index:
                    self.frame_index += 1
                    # skip frame
                    frames.get()
                if self.exit.is_set():
                    return
                # Start the steam again if someone hit play
                if not self.is_paused and self.stream:
                    self.stream.start_stream()
                time.sleep(0.1)
            self.frame_index += 1

            # Stop the stream if someone paused
            if self.is_paused and not self.stream.is_stopped():
                self.stream.stop_stream()
            # Write frame to the stream otherwise
            else:
                self.stream.write(frame)

    def stream_audio(self):
        """
        Stream audio from the server.
        """
        p = pyaudio.PyAudio()

        try:
            while not self.exit.is_set():
                if self.song_queue.empty():
                    time.sleep(0.1)
                    continue

                song = self.song_queue.get()
                self.song_index += 1

                self.stream = p.open(format=p.get_format_from_width(song.width),
                                     channels=song.n_channels,
                                     rate=song.sample_rate,
                                     output=True,
                                     frames_per_buffer=CHUNK)

                self.process_song(song.frames)

                self.stream.stop_stream()
                self.stream.close()
                self.stream = None
        except Exception as e:
            print(e)
        finally:
            self.server_udp.close()
            p.terminate()
            print('Audio closed')

    def server_update(self):
        """
        Update the server with the current state of the audio stream for the client.
        """
        try:
            while not self.exit.is_set():
                time.sleep(0.1)
                self.client_update_socket.send(pack_state(
                    self.song_index, self.frame_index, self.next_action))
                self.next_action = ActionType.PING

                data = self.client_update_socket.recv(12)
                self.server_song_index, self.server_frame_index, action = unpack_state(
                    data)
                if self.stream:
                    if action == ActionType.PAUSE and self.stream.is_active():
                        self.is_paused = True
                    elif action == ActionType.PLAY and not self.stream.is_active():
                        self.is_paused = False
        except Exception as e:
            print(e)
        finally:
            self.client_update_socket.close()
            print('Server update closed')

    def run_client(self):
        """
        Run the client.
        """
        self.server_tcp.connect((self.host, self.tcp_port))

        get_audio_data_proc = threading.Thread(
            target=self.get_audio_data, args=())
        get_audio_data_proc.start()

        stream_proc = threading.Thread(target=self.stream_audio, args=())
        stream_proc.start()

        server_update_proc = threading.Thread(
            target=self.server_update, args=())
        server_update_proc.start()

        try:
            while not self.exit.is_set():
                op_code = input("Enter Operation Code: ")
                if op_code == '0':
                    break
                elif op_code == '1':
                    file_path = input("Enter File Path: ")
                    # check if file path exists
                    if os.path.exists(file_path):
                        self.upload_file(file_path)
                    else:
                        print("File path does not exist. Unable to upload file")
                        continue
                elif op_code == '2':
                    filename = input("Enter Song Title: ")
                    self.queue_song(filename)
                elif op_code == '3':
                    self.get_song_list()
                elif op_code == '7':
                    if self.stream:
                        self.is_paused = True
                        self.next_action = ActionType.PAUSE
                elif op_code == '8':
                    if self.stream:
                        self.is_paused = False
                        self.next_action = ActionType.PLAY
                elif op_code == '9':
                    # TODO need to implement skip
                    if self.stream:
                        with self.song_queue.mutex:
                            self.song_queue.queue.clear()
                        self.next_action = ActionType.PLAY
                else:
                    print("Invalid Operation Code. Please try again.")
        except Exception as e:
            print(e)
        finally:
            self.exit.set()

            stream_proc.join()
            get_audio_data_proc.join()
            server_update_proc.join()

            self.server_tcp.close()
            print('Client closed')
            sys.exit(1)


if __name__ == "__main__":
    client = Client()
    client.run_client()
