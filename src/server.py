import math
import queue
import select
import socket
import threading
import time
import wave

import pyaudio

from utils import queue_rows, setup_logger
from wire_protocol import unpack_opcode

BUFF_SIZE = 65536
CHUNK = 10*1024


class Server:
    def __init__(self, tcp_port=1538, udp_port=1539):
        self.tcp_port = tcp_port
        self.udp_port = udp_port
        self.tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_sock.setsockopt(
            socket.SOL_SOCKET, socket.SO_RCVBUF, BUFF_SIZE)

        self.logger = setup_logger()
        self.exit = threading.Event()

        self.song_queue = queue.Queue()

        self.udp_addrs = []

    def poll_read_sock_no_exit(self, inputs, timeout=0.1):
        """
        Generator that polls the read sockets while the exit event is not set.
        ...

        Parameters
        ----------
        inputs : list
            The list of sockets to poll.
        timeout : float
            The timeout for the select call.

        Yields
        ------
        socket.socket
            A socket that is ready to be read from.
        """
        while not self.exit.is_set():
            read_sockets, _, _ = select.select(inputs, [], [], timeout)
            for sock in read_sockets:
                yield sock

    def recv_file(self, c_sock):
        """
        Receive a file from the client.
        ...

        Parameters
        ----------
        c_sock : socket.socket
            The socket to receive the file from.
        """
        # TODO use specific wire protocol for file transfer
        filename_size = c_sock.recv(16).decode()
        filename_size = int(filename_size, 2)

        filename = c_sock.recv(filename_size).decode()
        filesize = c_sock.recv(32).decode()
        filesize = int(filesize, 2)

        file_to_write = open('server_files/' + filename, 'wb')
        chunksize = 4096

        self.logger.info('Receiving file: ' + filename)

        while filesize > 0:
            if filesize < chunksize:
                chunksize = filesize
            data = c_sock.recv(chunksize)
            file_to_write.write(data)
            filesize -= len(data)

        file_to_write.close()

        self.logger.info('File received successfully.')

    def handle_tcp_conn(self, conn):
        """
        Handle a TCP client connection.
        ...

        Parameters
        ----------
        conn : socket.socket
            The TCP connection to handle.
        """
        inputs = [conn]

        self.logger.info('Waiting for incoming TCP requests.')
        try:
            for sock in self.poll_read_sock_no_exit(inputs):
                # TODO pls fix
                data = sock.recv(1)
                # If there is data, we unpack the opcode
                if data:
                    # TODO implement better opcode handling
                    opcode = unpack_opcode(data)

                    # If the opcode is 0, we are receiving a closure request
                    if opcode == 0:
                        self.logger.info(
                            '[0] Receiving client closure request.')
                        # TODO implement client closure request
                    # If the opcode is 1, we are receiving a file
                    elif opcode == 1:
                        self.logger.info('[1] Receiving audio file.')
                        self.recv_file(sock)
                    # If the opcode is 2, we are queuing a file
                    elif opcode == 2:
                        self.logger.info('[2] Queuing next song.')
                        song_name = sock.recv(1024).decode()
                        song = wave.open(f"server_files/{song_name}.wav")
                        self.song_queue.put(song)
                    # TODO implement the rest of the opcodes
                    elif opcode == 3:
                        self.logger.info('Need to finish implementation.')
                # If there is no data, we remove the connection
                else:
                    sock.close()
                    inputs.remove(sock)
        except Exception as e:
            self.logger.exception(e)
        finally:
            self.logger.info('Shutting down TCP handler.')
            self.exit.set()
            for conn in inputs:
                conn.close()

    def send_to_all_udp_addrs(self, data):
        """
        Send data to all UDP addresses.
        ...

        Parameters
        ----------
        data : bytes
            The data to send.
        """
        for addr in self.udp_addrs:
            self.udp_sock.sendto(data, addr)

    def stream_audio(self):
        """
        Stream audio to the client.
        """
        while not self.exit.is_set():
            for song in queue_rows(self.song_queue):
                self.logger.info('Streaming audio.')
                p = pyaudio.PyAudio()
                stream = p.open(format=p.get_format_from_width(song.getsampwidth()),
                                channels=song.getnchannels(),
                                rate=song.getframerate(),  # TODO need to adjust for different sample rates
                                input=True,
                                frames_per_buffer=CHUNK)

                # TODO just fix this :/
                sample_rate = song.getframerate()
                while not self.exit.is_set():
                    DATA_SIZE = math.ceil(song.getnframes()/CHUNK)
                    DATA_SIZE = str(DATA_SIZE).encode()
                    self.logger.info(
                        f'Sending data size {song.getnframes()/sample_rate}')
                    self.send_to_all_udp_addrs(DATA_SIZE)
                    cnt = 0
                    while not self.exit.is_set():
                        data = song.readframes(CHUNK)
                        self.send_to_all_udp_addrs(data)
                        # Here you can adjust it according to how fast you want to send data keep it > 0
                        time.sleep(0.001)

                        if cnt > (song.getnframes()/CHUNK):
                            break
                        cnt += 1

                    break
                stream.stop_stream()
                stream.close()
                p.terminate()
                song.close()
                # c_sock.close() was suggested by github copilot so idk if it's right

                self.logger.info('Audio streamed successfully.')

    def run_server(self):
        """
        Run the server.
        """
        self.logger.info('Server started!')

        # Bind tcp and udp sockets to ports
        self.tcp_sock.bind((socket.gethostname(), self.tcp_port))
        self.udp_sock.bind((socket.gethostname(), self.udp_port))

        # Listen for incoming connections
        self.tcp_sock.listen(5)

        stream_proc = threading.Thread(target=self.stream_audio, args=())
        stream_proc.start()

        inputs = [self.tcp_sock, self.udp_sock]
        procs = [stream_proc]

        self.logger.info('Waiting for incoming connections')
        try:
            for sock in self.poll_read_sock_no_exit(inputs):
                if sock == self.tcp_sock:
                    conn, addr = sock.accept()

                    self.logger.info(
                        f'[+] TCP connected to {addr[0]} ({addr[1]})')

                    t = threading.Thread(
                        target=self.handle_tcp_conn, args=(conn,))
                    t.start()
                    procs.append(t)
                # If the socket is the server socket, accept as a connection
                elif sock == self.udp_sock:
                    _, addr = sock.recvfrom(BUFF_SIZE)

                    self.logger.info(
                        f'[+] UDP connected to {addr[0]} ({addr[1]})')

                    self.udp_addrs.append(addr)
                # Otherwise, read the data from the socket
                else:
                    # TODO pls fix
                    data = sock.recv(1024)
                    if data:
                        self.logger.info(f'Received data: {data}')
                    else:
                        sock.close()
                        inputs.remove(sock)
        except KeyboardInterrupt:
            self.logger.info('Shutting down server.')
            self.exit.set()

            for proc in procs:
                proc.join()
            for conn in inputs:
                conn.close()


if __name__ == "__main__":
    server = Server()
    server.run_server()
