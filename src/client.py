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
        self.s.send(pack_opcode(2))
        self.s.send(filename.encode())
        print('Song Queued')

    def getAudioData(self):
        inputs = [self.client_socket]
        while not self.exit.is_set():
            read_sockets, _, _ = select.select(inputs, [], [], 0.1)
            for sock in read_sockets:
                frame, _ = sock.recvfrom(BUFF_SIZE)
                self.audio_q.put(frame)

    def stream_audio(self):
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
                target=self.getAudioData, args=())
            t1.start()
            self.procs.append(t1)

            # print('[Now Playing]... Data',DATA_SIZE,'[Audio Time]:',DURATION ,'seconds')
            while not self.exit.is_set():
                time.sleep(0.1)
                for frame in queue_rows(self.audio_q):
                    stream.write(frame)
                    # print('[Queue size while playing]...',q.qsize(),'[Time remaining...]',round(DURATION),'seconds')

        except:
            self.client_socket.close()
            print('Audio closed')
            sys.exit(1)

    def run_client(self):
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
                    self.upload_file(file_path)
                elif op_code == '2':
                    filename = input("Enter Song Title: ")
                    self.queue_song(filename)
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
