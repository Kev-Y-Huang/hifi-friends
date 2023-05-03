import math
import queue
import select
import socket
import threading
import wave
import os

import pyaudio
import argparse

from music_service import User
from utils import queue_rows, setup_logger
from wire_protocol import unpack_opcode, pack_packet, unpack_packet
from queue import Queue
from paxos import *

BUFF_SIZE = 65536
CHUNK = 10 * 1024


class Server:
    def __init__(self, server_id):
        self.server_id = server_id
        self.machines = get_other_machines(server_id)
        self.machine = MACHINES[server_id]

        # Setup client tcp socket
        self.tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.tcp_sock.bind((self.machine.ip, self.machine.client_tcp_port))
        self.tcp_sock.listen(5)

        # Setup client udp socket
        self.udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, BUFF_SIZE)
        self.udp_sock.bind((self.machine.ip, self.machine.client_udp_port))

        # Get list of files in server_files
        self.uploaded_files = os.listdir(f'server_{self.server_id}_files')

        # Paxos
        self.filename = None
        self.operation = None
        self.accept_operation = ""
        self.paxos = Paxos(server_id)
        self.paxos.servers = get_other_machines(server_id)

        # Internal Ops Queue
        self.queue = Queue()

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

    def recv_file(self, c_sock, replicate=False):
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

        file_to_write = open(f'server_{self.server_id}_files/' + filename, 'wb')
        chunksize = 4096

        self.logger.info('Receiving file: ' + filename)
        if filename in self.uploaded_files:
            self.logger.error(f'A file of the same name {filename} is already being uploaded. Upload canceled.')
            return

        while filesize > 0:
            if filesize < chunksize:
                chunksize = filesize
            data = c_sock.recv(chunksize)
            file_to_write.write(data)
            filesize -= len(data)

        file_to_write.close()

        self.logger.info('File received successfully.')
        self.uploaded_files.append(filename)

        if replicate:
            self.paxos.commit_op(filename, 'upload')

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
                        self.recv_file(sock, replicate=True)
                    # If the opcode is 2, we are queuing a file
                    elif opcode == 2:
                        self.logger.info('[2] Queuing next song.')
                        song_name = sock.recv(1024).decode()
                        if os.path.exists(f"server_{self.server_id}_files/{song_name}"):
                            song = wave.open(f"server_{self.server_id}_files/{song_name}")
                            self.song_queue.put(song)
                            message = 'Song queued.'
                        else:
                            self.logger.error(f'File {song_name}.wav not found.')
                            message = 'File not found.'
                        conn.send(message.encode())
                    # TODO implement the rest of the opcodes
                    elif opcode == 3:
                        self.logger.info('Need to finish implementation.')
                    elif opcode == 4:
                        self.logger.info('[1] Receiving audio file.')
                        self.recv_file(sock, replicate=False)
                # If there is no data, we remove the connection
                else:
                    # TODO pls fix
                    data = sock.recv(1)
                    # If there is data, we unpack the opcode
                    if data:
                        # TODO implement better opcode handling
                        opcode = unpack_opcode(data)

                        # If the opcode is 0, we are receiving a closure request
                        if opcode == 0:
                            self.logger.info('[0] Receiving client closure request.')
                            self.recv_file(sock)
                        # If the opcode is 1, we are receiving a file
                        elif opcode == 1:
                            self.logger.info('[1] Receiving audio file.')
                            self.recv_file(sock)
                        # If the opcode is 2, we are queuing a file
                        elif opcode == 2:
                            self.logger.info('[2] Queuing next song.')
                            song_name = sock.recv(1024).decode()
                            if song_name not in self.uploaded_files:
                                self.logger.error(
                                    f'File {song_name} has not been uploaded or is in the processing of uploading. Queue failed.')
                                continue
                            if os.path.exists(f"server_{self.server_id}_files/{song_name}"):
                                song = wave.open(f"server_{self.server_id}_files/{song_name}")
                            else:
                                self.logger.error(f'File {song_name} not found.')
                                continue
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
                    DATA_SIZE = math.ceil(song.getnframes() / CHUNK)
                    DATA_SIZE = str(DATA_SIZE).encode()
                    self.logger.info(
                        f'Sending data size {song.getnframes() / sample_rate}')
                    self.send_to_all_udp_addrs(DATA_SIZE)
                    cnt = 0
                    while not self.exit.is_set():
                        data = song.readframes(CHUNK)
                        self.send_to_all_udp_addrs(data)
                        # Here you can adjust it according to how fast you want to send data keep it > 0
                        time.sleep(0.001)

                        if cnt > (song.getnframes() / CHUNK):
                            break
                        cnt += 1

                    break
                stream.stop_stream()
                stream.close()
                p.terminate()
                song.close()
                # c_sock.close() was suggested by github copilot so idk if it's right

                self.logger.info('Audio streamed successfully.')

    def listen_internal(self):
        """
        Listens to the other servers to get state updates from the systems
        """
        self.internal_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.internal_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.internal_socket.bind((self.machine.ip, self.machine.internal_port))
        self.internal_socket.listen(5)

        inputs = [server.internal_socket]

        try:
            while True:
                for sock in self.poll_read_sock_no_exit(inputs):
                    # If the socket is the server socket, accept as a connection
                    if sock == self.internal_socket:
                        client, _ = sock.accept()
                        inputs.append(client)
                    # Otherwise, read the data from the socket
                    else:
                        data = sock.recv(1024)
                        if data:
                            username, gen_number, op_code, contents = unpack_packet(data)
                            print(f'gen_number to put into queue: {gen_number}')
                            curr_user = User(sock, username, gen_number)
                            self.queue.put((curr_user, int(op_code), contents))
                        # If there is no data, then the connection has been closed
                        else:
                            sock.close()
                            inputs.remove(sock)
        except Exception as e:
            print(e)
            for conn in inputs:
                conn.close()

    def handle_queue(self):
        """
        Handles the queue of messages from the clients
        """
        while True:
            if not self.queue.empty():
                user, op_code, contents = self.queue.get()
                server_id = user.get_id()
                gen_number = user.get_gen_number()
                if op_code == 8:
                    print('prepare received')
                    print(self.paxos.machines[0].conn)
                    self.paxos.send_promise(server_id, gen_number)
                if op_code == 9:
                    print('promise received')
                    self.paxos.handle_promise(server_id, gen_number, self.filename)
                if op_code == 10:
                    print('accept received')
                    print("accept this:", gen_number)
                    self.paxos.handle_accept(server_id, gen_number)
                if op_code == 11:
                    if contents == 'accept':
                        print('committing operation')
                        self.paxos.commit_op(self.filename, "upload")

    def setup_internal_connections(self):
        """
        Sets up the internal connections to the other servers
        """
        for backup in self.machines:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                sock.connect((backup.ip, backup.internal_port))
                print(f"Connected to Server {backup.id} on port {backup.internal_port}")
                self.paxos.machines[backup.id].conn = sock

            except:
                # self.logger.info(f"Setup failed for {backup.id}")
                pass
        return

    def run_server(self):
        """
        Run the server.
        """
        self.logger.info('Server started!')

        inputs = [self.tcp_sock, self.udp_sock]
        procs = list()

        # streaming thread
        procs.append(threading.Thread(target=self.stream_audio, args=()))
        # listen for incoming messages from other servers
        procs.append(threading.Thread(target=server.listen_internal))
        # handle the queue of messages from the clients
        procs.append(threading.Thread(target=server.handle_queue))

        for eachThread in procs:
            eachThread.start()

        print('\nConnecting with other servers...')
        # sleep to allow servers to start before attempting to connect
        time.sleep(1.5)
        self.setup_internal_connections()

        self.logger.info('Waiting for client incoming connections')
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
    parser = argparse.ArgumentParser(description="Replicated Music Server")

    parser.add_argument("--server_number", "-s", choices=[0, 1, 2], type=int)
    args = parser.parse_args()

    server = Server(args.server_number)
    server.run_server()
