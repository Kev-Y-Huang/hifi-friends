import os
import queue
import select
import socket
import sys
import threading
import time

import pyaudio

from utils import queue_rows
from wire_protocol import pack_opcode

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

        self.procs = []

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
        filename = os.path.basename(file_path)
        size = len(filename)
        # encode filename size as 16 bit binary, limit your filename length to 255 bytes
        size = bin(size)[2:].zfill(16)

        self.s.send(size.encode())
        self.s.send(filename.encode())

        filesize = os.path.getsize(file_path)
        # encode filesize as 32 bit binary
        filesize = bin(filesize)[2:].zfill(32)
        self.s.send(filesize.encode())

        file_to_send = open(file_path, 'rb')

        l = file_to_send.read()
        self.s.sendall(l)
        file_to_send.close()
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
        print(message)

    def get_audio_data(self):
        """
        Get audio data from the server.
        """
        inputs = [self.client_socket]
        while not self.exit.is_set():
            read_sockets, _, _ = select.select(inputs, [], [], 0.1)
            for sock in read_sockets:
                frame, _ = sock.recvfrom(BUFF_SIZE)
                self.audio_q.put(frame)

    def stream_audio(self):
        """
        Stream audio from the server.
        """
        try:
            p = pyaudio.PyAudio()
            stream = p.open(format=p.get_format_from_width(2),
                            channels=2,
                            rate=48000,
                            output=True,
                            frames_per_buffer=CHUNK)

            # TODO fix this monstrocity
            self.client_socket.sendto(b'0', (self.host, self.udp_port))
            self.audio_q = queue.Queue()

            t1 = threading.Thread(
                target=self.get_audio_data, args=())
            t1.start()
            self.procs.append(t1)

            # print('[Now Playing]... Data',DATA_SIZE,'[Audio Time]:',DURATION ,'seconds')
            while not self.exit.is_set():
                time.sleep(0.1)
                for frame in queue_rows(self.audio_q):
                    if self.exit.is_set():
                        break
                    stream.write(frame)
                    # print('[Queue size while playing]...',q.qsize(),'[Time remaining...]',round(DURATION),'seconds')

        finally:
            self.client_socket.close()
            print('Audio closed')

    def run_client(self):
        """
        Run the client.
        """
        self.s.connect((self.host, self.tcp_port))

        stream_proc = threading.Thread(target=client.stream_audio, args=())
        stream_proc.start()
        self.procs.append(stream_proc)

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
            for proc in self.procs:
                proc.join()
            self.s.close()
            print('Client closed')
            sys.exit(1)


if __name__ == "__main__":
    client = Client()
    client.run_client()
