import os
import queue
import select
import socket
import struct
import sys
import threading
import time

import pyaudio

from utils import queue_rows
from wire_protocol import pack_opcode, pack_num, unpack_num

HOST = socket.gethostname()
TCP_PORT = 1538
UDP_PORT = 1539
CLIENT_UPDATE_PORT = 1540

BUFF_SIZE = 65536
CHUNK = 10*1024


class Client:
    def __init__(self, host=HOST, tcp_port=TCP_PORT, udp_port=UDP_PORT, client_update_port=CLIENT_UPDATE_PORT):
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.host = host
        self.tcp_port = tcp_port
        self.udp_port = udp_port

        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.client_socket.setsockopt(
            socket.SOL_SOCKET, socket.SO_RCVBUF, BUFF_SIZE)

        self.exit = threading.Event()

        self.audio_q = queue.Queue()

        self.stream = None

        self.client_update_port = client_update_port
        self.client_update_socket = socket.socket(
            socket.AF_INET, socket.SOCK_STREAM)
        self.client_update_socket.connect((self.host, self.client_update_port))
        self.next_update = b'ping'

        self.width = 2
        self.sample_rate = 22050
        self.n_channels = 2
        

    def upload_file(self, file_path):
        """
        Upload a file to the server.
        ...

        Parameters
        ----------
        file_path : str
            The path to the file to upload.
        """
        self.s.send(pack_opcode(1))

        file_name = os.path.basename(file_path)
        self.s.send(pack_num(len(file_name), 16))
        self.s.send(file_name.encode())
        self.s.send(pack_num(os.path.getsize(file_path), 32))

        with open(file_path, 'rb') as file_to_send:
            self.s.sendall(file_to_send.read())

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
        self.s.send(pack_opcode(2))
        self.s.send(filename.encode())

        # Wait for server to respond
        message = self.s.recv(1024).decode()
        print(message)

    def get_song_list(self):
        """
        Gets the available songs for queueing from the server and prints them.
        """
        self.s.send(pack_opcode(3))

        # Wait for server to respond
        message = self.s.recv(1024).decode()
        # print(message)
        return message

    def get_current_queue(self):
        """
        Gets the current queue from the server and prints it.
        """
        self.s.send(pack_opcode(4))

        # Wait for server to respond
        message = self.s.recv(1024).decode()
        # print(message)
        return message

    def get_audio_data(self):
        """
        Get audio data from the server.
        """
        inputs = [self.client_socket]
        self.client_socket.sendto(b'0', (self.host, self.udp_port))

        song_q = queue.Queue()
        while not self.exit.is_set():
            read_sockets, _, _ = select.select(inputs, [], [], 0.1)
            for sock in read_sockets:
                frame, _ = sock.recvfrom(BUFF_SIZE)

                try:
                    # Received audio header
                    if int(frame.decode(), 2) == 0:
                        self.width = unpack_num(sock.recvfrom(16)[0])
                        self.sample_rate = unpack_num(sock.recvfrom(16)[0])
                        self.n_channels = unpack_num(sock.recvfrom(16)[0])

                        self.audio_q.put(song_q)
                        song_q = queue.Queue()
                except:
                    song_q.put(frame)
                

        print("closed")

    def stream_audio(self):
        """
        Stream audio from the server.
        """
        p = pyaudio.PyAudio()

        try:
            while not self.exit.is_set():
                if self.audio_q.empty():
                    # TODO implement sending next song request
                    self.next_update = b"NEXT"
                    time.sleep(0.1)
                    continue

                song_q = self.audio_q.get()

                print("Playing")
                self.stream = p.open(format=p.get_format_from_width(self.width),
                                channels=self.n_channels,
                                rate=self.sample_rate,
                                output=True,
                                frames_per_buffer=CHUNK)

                # TODO fix this monstrocity
                for frame in queue_rows(song_q):
                    if self.exit.is_set():
                        break
                    # TODO definitely can do this better
                    while self.stream.is_stopped():
                        if self.exit.is_set():
                            raise Exception("Exiting")
                        time.sleep(0.1)
                    self.stream.write(frame)

                self.stream.stop_stream()
                self.stream.close()
                self.stream = None

        finally:
            self.client_socket.close()
            p.terminate()
            print('Audio closed')

    def server_update(self):
        """
        Update the server with the client's ip address and port.
        """
        try:
            while not self.exit.is_set():
                time.sleep(0.1)
                self.client_update_socket.send(self.next_update)
                self.next_update = b'ping'
                data = self.client_update_socket.recv(1024)
                state = struct.unpack("?", data)[0]  # TODO can do this better

                if self.stream and state == self.stream.is_active():
                    if state:
                        self.stream.stop_stream()
                    else:
                        self.stream.start_stream()
        except Exception as e:
            print(e)
        finally:
            self.client_update_socket.close()
            print('Server update closed')

    def run_client(self):
        """
        Run the client.
        """
        self.s.connect((self.host, self.tcp_port))

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
                        self.stream.stop_stream()
                        self.next_update = b'PAUSE'
                elif op_code == '8':
                    if self.stream:
                        self.stream.start_stream()
                        self.next_update = b'PLAY'
                elif op_code == '9':
                    if self.stream:
                        with self.audio_q.mutex:
                            self.audio_q.queue.clear()
                        self.next_update = b'PLAY'
        except Exception as e:
            print(e)
        finally:
            self.exit.set()
            print(self.exit.is_set())

            stream_proc.join()
            get_audio_data_proc.join()
            server_update_proc.join()

            self.s.close()
            print('Client closed')
            sys.exit(1)


if __name__ == "__main__":
    client = Client()
    client.run_client()
