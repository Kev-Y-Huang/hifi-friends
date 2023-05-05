import os
import queue
import select
import socket
import threading
import time
import wave

import pyaudio

from utils import ActionType, Operation, queue_rows, setup_logger
from wire_protocol import pack_num, pack_state, unpack_num, unpack_opcode, unpack_state

HOST = socket.gethostname()
TCP_PORT = 1538
UDP_PORT = 1539
CLIENT_UPDATE_PORT = 1540

BUFF_SIZE = 65536
CHUNK = 10*1024


class Server:
    def __init__(self, host=HOST, tcp_port=TCP_PORT, udp_port=UDP_PORT, client_update_port=CLIENT_UPDATE_PORT):
        self.host = host

        # TCP Setup
        self.tcp_port = tcp_port
        self.tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        # UDP Setup https://gist.github.com/ninedraft/7c47282f8b53ac015c1e326fffb664b5
        self.udp_port = udp_port
        self.udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_sock.setsockopt(
            socket.SOL_SOCKET, socket.SO_RCVBUF, BUFF_SIZE)
        self.udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

        # Client Update Setup
        self.client_update_port = client_update_port
        self.client_update_socket = socket.socket(
            socket.AF_INET, socket.SOCK_STREAM)
        self.client_update_socket.setsockopt(
            socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        # get list of files in server_files
        self.uploaded_files = os.listdir('server_files')

        self.logger = setup_logger()
        self.exit = threading.Event()

        self.song_queue = queue.Queue()

        self.udp_addrs = []

        # Server state of audio playback
        self.song_index = 0
        self.frame_index = 0

        # TODO need better implementation than just pause/play even
        self.pause_playback = threading.Event()

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

    def recv_file(self, c_sock: socket.socket):
        """
        Receive a file from the client.
        ...

        Parameters
        ----------
        c_sock : socket.socket
            The socket to receive the file from.
        """
        # TODO use specific wire protocol for file transfer
        file_name_size = unpack_num(c_sock.recv(16))
        file_name = c_sock.recv(file_name_size).decode()
        file_size = unpack_num(c_sock.recv(32))

        with open('server_files/' + file_name, 'wb') as file_to_write:
            chunk_size = 4096

            self.logger.info('Receiving file: ' + file_name)
            if file_name in self.uploaded_files:
                message = f'A file of the same name {file_name} is already being uploaded. Upload canceled.'
                self.logger.error(message)
                return message

            while file_size > 0:
                if file_size < chunk_size:
                    chunk_size = file_size
                data = c_sock.recv(chunk_size)
                file_to_write.write(data)
                file_size -= len(data)

        self.uploaded_files.append(file_name)

        message = 'File received successfully.'
        self.logger.info('File received successfully.')

        return message

    def enqueue_song(self, conn: socket.socket):
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
            self.song_queue.put(song_name)
            message = 'Song queued.'
        else:
            message = f'File {song_name} not found.'
            self.logger.error(message)
        return message

    def get_queue(self):
        """
        Get the queue of songs to be played.
        ...

        Returns
        -------
        str
            The queue of songs to be played.
        """
        song_queue_str = ','.join(str(item) for item in self.song_queue.queue)
        return f"[{song_queue_str}]"

    def handle_tcp_conn(self, conn: socket.socket):
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
                data = sock.recv(1)

                # If there is no data, the connection has been closed
                if not data:
                    break
            
                opcode = unpack_opcode(data)
                message = "No response."

                # If the opcode is 0, we are receiving a closure request
                if opcode == Operation.CLOSE:
                    self.logger.info(
                        '[0] Receiving client closure request.')
                    # TODO implement client closure request
                    message = "Close not implemented."
                # If the opcode is 1, we are receiving a file
                elif opcode == Operation.UPLOAD:
                    self.logger.info('[1] Receiving audio file.')
                    message = self.recv_file(sock)
                # If the opcode is 2, we are queueing a file
                elif opcode == Operation.QUEUE:
                    self.logger.info('[2] Queuing song.')
                    message = self.enqueue_song(sock)
                # If the opcode is 3, we are sending the list of available songs
                elif opcode == Operation.LIST:
                    self.logger.debug('[3] Requesting available songs.')
                    message = ':songs:' + str(self.uploaded_files)
                # If the opcode is 4, we are sending the current queue
                elif opcode == Operation.QUEUED:
                    self.logger.debug('[4] Requesting current queue.')
                    message = ':queue:' + self.get_queue()
                # TODO implement the rest of the opcodes
                elif opcode == 6:
                    self.logger.info('Need to finish implementation.')
                    
                # Send the message back to the client
                conn.send(message.encode())
        except Exception as e:
            self.logger.exception(e)
        finally:
            self.logger.info('Shutting down TCP handler.')
            conn.close()

    def send_to_all_udp_addrs(self, data: bytes):
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
            # self.pause_playback.wait() was suggested by github copilot so idk if it's right

            for song_name in queue_rows(self.song_queue):
                self.logger.info('Streaming audio.')
                song = wave.open(f"server_files/{song_name}")
                stream = p.open(format=p.get_format_from_width(song.getsampwidth()),
                                channels=song.getnchannels(),
                                rate=song.getframerate(),  # TODO need to adjust for different sample rates
                                input=True,
                                frames_per_buffer=CHUNK)

                # TODO just fix this :/
                width = song.getsampwidth()
                sample_rate = song.getframerate()
                n_channels = song.getnchannels()
                while not self.exit.is_set():
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

                # Send audio header information with all 0s delimiter
                self.send_to_all_udp_addrs(pack_num(0, 16))
                time.sleep(0.01)

                self.logger.info(
                    f'Sending width {width}, sample rate {sample_rate}, channels {n_channels}')

                self.send_to_all_udp_addrs(pack_num(width, 16))
                self.send_to_all_udp_addrs(pack_num(sample_rate, 16))
                self.send_to_all_udp_addrs(pack_num(n_channels, 16))

                time.sleep(0.001)

                self.logger.info('Audio streamed successfully.')

        p.terminate()

    def update_most_recent(self, song_index: int, frame_index: int):
        """
        Updates the server state to the most recent song and frame index.
        ...

        Parameters
        ----------
        song_index : int
            The passed-in song index to check.
        frame_index : int
            The passed-in frame index to check.
        """
        # Song index takes precedence over frame index
        is_song_more_recent = song_index > self.song_index
        is_frame_more_recent = song_index == self.song_index and frame_index >= self.frame_index

        if is_song_more_recent or is_frame_more_recent:
            self.song_index, self.frame_index = song_index, frame_index

    def listen_client_updates(self):
        """
        Listens for client state updates
        """
        self.client_update_socket.bind((self.host, self.client_update_port))
        self.client_update_socket.listen(5)

        inputs = [server.client_update_socket]

        try:
            for sock in self.poll_read_sock_no_exit(inputs):
                # If the socket is the server socket, accept as a connection
                if sock == self.client_update_socket:
                    client, _ = sock.accept()
                    inputs.append(client)
                # Otherwise, read the data from the socket
                else:
                    data = sock.recv(1024)
                    if data:
                        # Get  song index, frame index, and action from received data
                        song_index, frame_index, action = unpack_state(data)
                        self.update_most_recent(song_index, frame_index)

                        if action == ActionType.PLAY:
                            self.logger.info('PLAY')
                            self.pause_playback.clear()
                        elif action == ActionType.PAUSE:
                            self.logger.info('PAUSE')
                            self.pause_playback.set()

                        # TODO need a better way to handle this
                        if self.pause_playback.is_set():
                            action = ActionType.PAUSE
                        else:
                            action = ActionType.PLAY
                        sock.send(pack_state(self.song_index,
                                  self.frame_index, action))
                    # If there is no data, then the connection has been closed
                    else:
                        sock.close()
                        inputs.remove(sock)
        except Exception as e:
            self.logger.exception(e)
            for conn in inputs:
                conn.close()

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

        client_update_proc = threading.Thread(
            target=self.listen_client_updates, args=())
        client_update_proc.start()

        stream_proc = threading.Thread(target=self.stream_audio, args=())
        stream_proc.start()

        inputs = [self.tcp_sock, self.udp_sock]
        procs = [stream_proc, client_update_proc]

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
