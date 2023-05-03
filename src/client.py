import os
import queue
import select
import socket
import sys
import threading
import time

import pyaudio

from utils import queue_rows
from wire_protocol import pack_opcode, pack_file_name_size, pack_file_size

HOST = socket.gethostname()
TCP_PORT = 1538
UDP_PORT = 1539

BUFF_SIZE = 65536
CHUNK = 10*1024


class Client:
    def __init__(self, host=HOST, tcp_port=TCP_PORT, udp_port=UDP_PORT):
        self.s = socket.socket()
        self.host = host
        self.tcp_port = tcp_port
        self.udp_port = udp_port

        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.client_socket.setsockopt(
            socket.SOL_SOCKET, socket.SO_RCVBUF, BUFF_SIZE)

        self.exit = threading.Event()

        self.audio_q = queue.Queue()

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
        self.s.send(pack_file_name_size(file_name))
        self.s.send(file_name.encode())
        self.s.send(pack_file_size(os.path.getsize(file_path)))

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
        return message

    def get_audio_data(self):
        """
        Get audio data from the server.
        """
        inputs = [self.client_socket]
        self.client_socket.sendto(b'0', (self.host, self.udp_port))

        while not self.exit.is_set():
            read_sockets, _, _ = select.select(inputs, [], [], 0.1)
            for sock in read_sockets:
                frame, _ = sock.recvfrom(BUFF_SIZE)
                self.audio_q.put(frame)

    def stream_audio(self):
        """
        Stream audio from the server.
        """
        p = pyaudio.PyAudio()
        format = p.get_format_from_width(2)
        try:
            while not self.exit.is_set():
                if self.audio_q.empty():
                    # TODO implement sending next song request
                    self.s.send(pack_opcode(4))
                    time.sleep(1)
                    continue

                print("Playing")
                stream = p.open(format=format,
                                channels=2,
                                rate=48000,
                                output=True,
                                frames_per_buffer=CHUNK)

                # TODO fix this monstrocity
                for frame in queue_rows(self.audio_q):
                    if self.exit.is_set():
                        break
                    stream.write(frame)
                
                stream.stop_stream()
                stream.close()

        finally:
            self.client_socket.close()
            p.terminate()
            print('Audio closed')

    def run_client(self):
        """
        Run the client.
        """
        self.s.connect((self.host, self.tcp_port))

        stream_proc = threading.Thread(target=self.stream_audio, args=())
        stream_proc.start()

        get_audio_data_proc = threading.Thread(
            target=self.get_audio_data, args=())
        get_audio_data_proc.start()

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
        except Exception as e:
            print(e)
        finally:
            self.exit.set()
            print(self.exit.is_set())

            stream_proc.join()
            get_audio_data_proc.join()

            self.s.close()
            print('Client closed')
            sys.exit(1)


if __name__ == "__main__":
    client = Client()
    client.run_client()
