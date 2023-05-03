import math
import queue
import select
import socket
import threading
import time
import wave
import os

import pyaudio

from utils import queue_rows, setup_logger
from wire_protocol import unpack_opcode, unpack_size

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
        # get list of files in server_files
        self.uploaded_files = os.listdir('server_files')

        self.logger = setup_logger()
        self.exit = threading.Event()

        self.song_queue = queue.Queue()
        self.now_playing = queue.Queue()

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
        file_name_size = unpack_size(c_sock.recv(16))
        file_name = c_sock.recv(file_name_size).decode()
        file_size = unpack_size(c_sock.recv(32))

        with open('server_files/' + file_name, 'wb') as file_to_write:
            chunk_size = 4096

            self.logger.info('Receiving file: ' + file_name)
            if file_name in self.uploaded_files:
                self.logger.error(
                    f'A file of the same name {file_name} is already being uploaded. Upload canceled.')
                return

            while file_size > 0:
                if file_size < chunk_size:
                    chunk_size = file_size
                data = c_sock.recv(chunk_size)
                file_to_write.write(data)
                file_size -= len(data)

        self.logger.info('File received successfully.')
        self.uploaded_files.append(file_name)

    def enqueue_song(self, conn):
        """
        Enqueue a song to be played.
        ...

        Parameters
        ----------
        conn : socket.socket
            The socket to receive the song name from.
        
        Returns
        -------
        str
            A message to send back to the client.
        """
        song_name = conn.recv(1024).decode()
        if song_name not in self.uploaded_files:
            message = f'File {song_name} has not been uploaded or is in the processing of uploading. Queue failed.'
            self.logger.error(message)
        elif os.path.exists(f"server_files/{song_name}"):
            self.song_queue.put(f"server_files/{song_name}")
            message = 'Song queued.'
        else:
            message = f'File {song_name} not found.'
            self.logger.error(message)
        return message

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
                    # If the opcode is 2, we are queueing a file
                    elif opcode == 2:
                        self.logger.info('[2] Queuing song.')
                        message = self.enqueue_song(sock)
                        conn.send(message.encode())
                    # If the opcode is 3, we are sending the list of available songs
                    elif opcode == 3:
                        message = str(self.uploaded_files)
                        conn.send(message.encode())
                    elif opcode == 4:
                        self.logger.debug('[4] Playing the next song.')
                        if self.song_queue.empty():
                            self.logger.debug('No songs in queue.')
                        else:
                            song_path = self.song_queue.get()
                            song = wave.open(song_path)
                            self.now_playing.put(song)
                            self.logger.info('Playing next song.')
                    # TODO implement the rest of the opcodes
                    elif opcode == 5:
                        self.logger.info('Need to finish implementation.')
                # If there is no data, we remove the connection
                else:
                    break
        except Exception as e:
            self.logger.exception(e)
        finally:
            self.logger.info('Shutting down TCP handler.')
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
        p = pyaudio.PyAudio()

        while not self.exit.is_set():
            for song in queue_rows(self.now_playing):
                self.logger.info('Streaming audio.')
                stream = p.open(format=p.get_format_from_width(song.getsampwidth()),
                                channels=song.getnchannels(),
                                rate=song.getframerate(),  # TODO need to adjust for different sample rates
                                input=True,
                                frames_per_buffer=CHUNK)

                # TODO just fix this :/
                sample_rate = song.getframerate()
                while not self.exit.is_set():
                    self.logger.info(f'Sending sample rate {sample_rate}')
                    sample_rate = str(sample_rate).encode()
                    self.send_to_all_udp_addrs(sample_rate)
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
                song.close()
                # c_sock.close() was suggested by github copilot so idk if it's right

                self.logger.info('Audio streamed successfully.')

        p.terminate()

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
