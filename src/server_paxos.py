import queue
import socket
import threading
import wave

import os
import time

import pyaudio
import argparse

from utils import (Operation, Update, Message, ServerOperation, poll_read_sock_no_exit,
                   queue_rows, send_to_all_addrs, setup_logger)
from wire_protocol import (pack_audio_meta, pack_state, unpack_num,
                           pack_msgcode, unpack_opcode, unpack_packet, unpack_server_opcode, unpack_state)

from machines import MACHINES, get_other_machines
from paxos import Paxos


HOST = socket.gethostname()

BUFF_SIZE = 65536
CHUNK = 10*1024


class Server:
    def __init__(self, server_id):
        self.server_id = server_id
        self.machine = MACHINES[server_id]

        # TCP Setup
        self.upload_tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.upload_tcp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        # TCP Stream Setup
        self.stream_tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.stream_tcp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        # State TCP Setup
        self.state_tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.state_tcp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        # Audio UDP Setup
        self.audio_udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.audio_udp_sock.setsockopt(
            socket.SOL_SOCKET, socket.SO_RCVBUF, BUFF_SIZE)

        # Update UDP Setup
        self.update_udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.update_udp_sock.setsockopt(
            socket.SOL_SOCKET, socket.SO_RCVBUF, BUFF_SIZE)

        # Internal
        self.internal_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.internal_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        # List of uploaded files and queue of songs to be played
        self.uploaded_files = [f for f in os.listdir(f'server_{self.server_id}_files') if f.endswith('.wav')]
        self.song_queue = queue.Queue()

        # UDP addresses to send audio and update packets to
        self.audio_udp_addrs = []
        self.update_udp_addrs = []

        # Server state of audio playback
        self.song_index = 0
        self.frame_index = 0
        self.action_mutex = threading.Lock()
        self.action = Update.PING

        # Logging and cleanup
        self.logger = setup_logger()
        self.exit = threading.Event()

        # Paxos
        self.filename = None
        self.operation = None
        self.accept_operation = ""
        self.paxos = Paxos(server_id)
        self.paxos.machines = get_other_machines(server_id)

    def recv_file(self, c_sock: socket.socket, replicate=True):
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

        chunk_size = 4096

        self.filename = file_name

        if file_name in self.uploaded_files:
            message = f'A file of the same name {file_name} has already been uploaded. Upload canceled.'
            self.logger.error(message)

            # Send message to client
            if replicate:
                c_sock.send(message.encode())

            # Receive the file so that next recv is accurate
            # TODO: any way to make this better?
            while file_size > 0:
                if file_size < chunk_size:
                    chunk_size = file_size
                data = c_sock.recv(chunk_size)
                file_size -= len(data)
                
            return message
        
        # Begin receiving the file and writing it to the server files directory
        with open(f'server_{self.server_id}_files/' + file_name, 'wb') as file_to_write:
            self.logger.info(f'Receiving file: {file_name}')

            while file_size > 0:
                if file_size < chunk_size:
                    chunk_size = file_size
                data = c_sock.recv(chunk_size)
                file_to_write.write(data)
                file_size -= len(data)

        self.uploaded_files.append(file_name)

        message = 'File received successfully.'
        self.logger.info('File received successfully.')

        if replicate:
            # Tell client file finished uploading
            c_sock.send(message.encode())
            
            self.paxos.send_prepare()

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
        elif os.path.exists(f'server_{self.server_id}_files/{song_name}'):
            self.song_queue.put(song_name)
            conn.send(pack_msgcode(Message.QUEUE))
            conn.send(song_name.encode())
            time.sleep(0.01)
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
        return f'[{song_queue_str}]'
    
    def handle_upload_tcp_conn(self, conn: socket.socket):
        """
        Handle a TCP client connection for uploading
        ...

        Parameters
        ----------
        conn : socket.socket
            The TCP connection to handle.
        """
        inputs = [conn]

        self.logger.info('Waiting for incoming Upload TCP requests.')
        try:
            for sock in poll_read_sock_no_exit(inputs, self.exit):
                data = sock.recv(1)

                # If there is no data, the connection has been closed
                if not data:
                    break

                opcode = unpack_opcode(data)
                
                if opcode == Operation.UPLOAD:
                    self.logger.info('[1] Receiving audio file.')
                    self.recv_file(sock)
                elif opcode == Operation.PING:
                    self.logger.info('[8] Receving ping.')

        except Exception as e:
            self.logger.exception(e)
        finally:
            self.logger.info('Shutting down Upload TCP handler.')
            conn.close()

    def handle_stream_tcp_conn(self, conn: socket.socket):
        """
        Handle a TCP client connection for streaming
        ...

        Parameters
        ----------
        conn : socket.socket
            The TCP connection to handle.
        """
        inputs = [conn]

        self.logger.info('Waiting for incoming Stream TCP requests.')
        try:
            for sock in poll_read_sock_no_exit(inputs, self.exit):
                data = sock.recv(1)

                # If there is no data, the connection has been closed
                if not data:
                    break

                opcode = unpack_opcode(data)
                message = None

                if opcode == Operation.CLOSE:
                    self.logger.info(
                        '[0] Receiving client closure request.')
                    # TODO implement client closure request
                    message = 'Close not implemented.'
                elif opcode == Operation.UPLOAD:
                    self.logger.info('[1] Receiving audio file.')
                    self.recv_file(sock)
                elif opcode == Operation.QUEUE:
                    self.logger.info('[2] Queuing song.')
                    message = self.enqueue_song(sock)
                elif opcode == Operation.LIST:
                    self.logger.info('[3] Requesting available songs.')
                    message = ':songs:' + str(self.uploaded_files)
                elif opcode == Operation.QUEUED:
                    self.logger.info('[4] Requesting current queue.')
                    message = ':queue:' + self.get_queue()
                elif opcode == Operation.PAUSE:
                    self.logger.info('[5] Pausing audio.')
                    self.action_mutex.acquire()
                    self.action = Update.PAUSE
                    self.action_mutex.release()
                    message = 'Audio paused.'
                elif opcode == Operation.PLAY:
                    self.logger.info('[6] Playing audio.')
                    self.action_mutex.acquire()
                    self.action = Update.PLAY
                    self.action_mutex.release()
                    message = 'Audio playing.'
                elif opcode == Operation.SKIP:
                    self.logger.info('[7] Skipping audio.')
                    self.action_mutex.acquire()
                    self.action = Update.SKIP
                    self.action_mutex.release()
                    message = 'Song skipped.'

                # Send the message back to the client
                if message:
                    sock.send(pack_msgcode(Message.PRINT))
                    sock.send(message.encode())
        except Exception as e:
            self.logger.exception(e)
        finally:
            self.logger.info('Shutting down Stream TCP handler.')
            conn.close()

    def handle_state_tcp_conn(self, conn: socket.socket):
        """
        Handle a TCP client connection for receiving state from clients.
        ...

        Parameters
        ----------
        conn : socket.socket
            The TCP connection to handle.
        """
        inputs = [conn]

        self.logger.info('Waiting for incoming state TCP requests.')
        try:
            for sock in poll_read_sock_no_exit(inputs, self.exit):
                data = sock.recv(12)

                # If there is no data, the connection has been closed
                if not data:
                    break

                song_index, frame_index, _ = unpack_state(data)
                self.update_most_recent(song_index, frame_index)
        except Exception as e:
            self.logger.exception(e)
        finally:
            self.logger.info('Shutting down state TCP handler.')
            conn.close()

    def stream_audio(self):
        """
        Stream audio to the client.
        """
        p = pyaudio.PyAudio()

        while not self.exit.is_set():
            for song_name in queue_rows(self.song_queue):
                self.logger.info('Streaming audio.')
                song = wave.open(f'server_{self.server_id}_files/{song_name}')

                width = song.getsampwidth()
                sample_rate = song.getframerate()
                channels = song.getnchannels()

                # Send audio metadata for correct playback
                self.logger.info(
                    f'Sending width {width}, sample rate {sample_rate}, channels {channels}')
                data = pack_audio_meta(width, sample_rate, channels)
                send_to_all_addrs(self.audio_udp_sock,
                                  self.audio_udp_addrs, data)

                # Send audio data in chunks of frames
                for _ in range(0, song.getnframes(), CHUNK):
                    if self.exit.is_set():
                        break

                    data = song.readframes(CHUNK)
                    send_to_all_addrs(
                        self.audio_udp_sock, self.audio_udp_addrs, data)
                    # Here you can adjust it according to how fast you want to send data keep it > 0
                    time.sleep(0.001)

                # Close the song file
                song.close()

                self.logger.info('Audio frames sent successfully.')

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

    def send_client_updates(self):
        """
        Sends client state updates
        """
        try:
            while not self.exit.is_set():
                self.action_mutex.acquire()
                send_to_all_addrs(self.update_udp_sock, self.update_udp_addrs, pack_state(
                    self.song_index, self.frame_index, self.action))
                self.action = Update.PING
                self.action_mutex.release()

                time.sleep(0.01)
        except Exception as e:
            self.logger.exception(e)
            self.update_udp_sock.close()

    def listen_internal(self, conn):
        """
        Listens to the other servers to get paxos state updates from the systems
        """
        inputs = [conn]

        try:
            for sock in poll_read_sock_no_exit(inputs, self.exit):
                # If the socket is the server socket, accept as a connection
                if sock == self.internal_socket:
                    client, _ = sock.accept()
                    inputs.append(client)
                # Otherwise, read the data from the socket
                else:
                    data = sock.recv(1)
                    # If there is no data, then the connection has been closed
                    if not data:
                        break
                    opcode = unpack_server_opcode(data)

                    if opcode == ServerOperation.UPLOAD:
                        self.logger.info('[0] Receiving audio file from another server.')
                        self.recv_file(sock, False)

                    else:
                        paxos_msg = sock.recv(1024)
                        server_id, gen_number, msg = unpack_packet(paxos_msg)

                        if opcode == ServerOperation.PREPARE:
                            self.logger.info('[1] Prepare received')
                            self.paxos.send_promise(server_id, gen_number)

                        if opcode == ServerOperation.PROMISE:
                            self.logger.info('[2] Promise received')
                            self.paxos.handle_promise(server_id, gen_number, self.filename)

                        if opcode == ServerOperation.ACCEPT:
                            self.logger.info('[3] Accept received')
                            self.logger.info(f'Accept this: {gen_number}')
                            self.paxos.handle_accept(server_id, gen_number)

                        if opcode == ServerOperation.ACCEPT_RESPONSE:
                            self.logger.info('[4] Committing operation')
                            self.logger.info(f'File name: {self.filename}')
                            self.paxos.commit_op(server_id, self.filename, "upload")

        except Exception as e:
            self.logger.exception(e)
            conn.close()
            self.logger.info('Shutting down internal server connection handler.')

    def setup_internal_connections(self):
        """
        Sets up the internal connections to the other servers
        """
        for server_id in self.paxos.machines:
            backup = self.paxos.machines[server_id]
            while True:
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.connect((backup.ip, backup.internal_port))
                    self.logger.info(f"Connected to Server {backup.id} on port {backup.internal_port}")
                    self.paxos.machines[backup.id].conn = sock
                    self.paxos.machines[backup.id].ip = backup.ip
                    self.paxos.machines[backup.id].port = backup.upload_tcp_port
                    self.paxos.machines[backup.id].connected = True
                    break
                except:
                    self.logger.info(f"Setup failed for {backup.id}")
                    time.sleep(0.5)
        return


    def run_server(self):
        """
        Run the server.
        """
        self.logger.info('Server started!')
        # Bind tcp, udp, internal sockets to ports
        self.upload_tcp_sock.bind((socket.gethostname(), self.machine.upload_tcp_port))
        self.stream_tcp_sock.bind((socket.gethostname(), self.machine.stream_tcp_port))
        self.state_tcp_sock.bind((socket.gethostname(), self.machine.state_tcp_port))

        self.audio_udp_sock.bind((socket.gethostname(), self.machine.audio_udp_port))
        self.update_udp_sock.bind((socket.gethostname(), self.machine.update_udp_port))
        self.internal_socket.bind((socket.gethostname(), self.machine.internal_port))

        # Listen for incoming connections
        self.upload_tcp_sock.listen(5)
        self.stream_tcp_sock.listen(5)
        self.state_tcp_sock.listen(5)
        self.internal_socket.listen(5)

        procs = list()

        # Start the client update thread
        client_update_proc = threading.Thread(
            target=self.send_client_updates, args=())
        client_update_proc.start()

        # Start the audio streaming thread
        stream_proc = threading.Thread(target=self.stream_audio, args=())
        stream_proc.start()

        inputs = [self.upload_tcp_sock, self.stream_tcp_sock, self.state_tcp_sock, self.audio_udp_sock, self.update_udp_sock, self.internal_socket]
        procs = [stream_proc, client_update_proc]
        
        self.logger.info('Connecting to Server Replicas')
        self.setup_internal_connections()

        self.logger.info('Waiting for incoming connections')
        try:
            for sock in poll_read_sock_no_exit(inputs, self.exit):
                # If the socket is the upload TCP socket, accept the connection
                if sock == self.upload_tcp_sock:
                    conn, addr = sock.accept()

                    self.logger.info(
                        f'[+] Upload TCP connected to {addr[0]} ({addr[1]})')

                    t = threading.Thread(
                        target=self.handle_upload_tcp_conn, args=(conn,))
                    t.start()
                    procs.append(t)
                # If the socket is the stream TCP socket, accept the connection
                elif sock == self.stream_tcp_sock:
                    conn, addr = sock.accept()

                    self.logger.info(
                        f'[+] Stream TCP connected to {addr[0]} ({addr[1]})')

                    t = threading.Thread(
                        target=self.handle_stream_tcp_conn, args=(conn,))
                    t.start()
                    procs.append(t)
                # If the socket is the state TCP socket, accept the connection
                elif sock == self.state_tcp_sock:
                    conn, addr = sock.accept()

                    self.logger.info(
                        f'[+] State TCP connected to {addr[0]} ({addr[1]})')

                    t = threading.Thread(
                        target=self.handle_state_tcp_conn, args=(conn,))
                    t.start()
                    procs.append(t)
                 # If the socket is the audio UDP socket, add the address to the list
                elif sock == self.audio_udp_sock:
                    _, addr = sock.recvfrom(BUFF_SIZE)

                    self.logger.info(
                        f'[+] Audio UDP connected to {addr[0]} ({addr[1]})')

                    self.audio_udp_addrs.append(addr)
                # If the socket is the update UDP socket, add the address to the list
                elif sock == self.update_udp_sock:
                    _, addr = sock.recvfrom(BUFF_SIZE)

                    self.logger.info(
                        f'[+] Update UDP connected to {addr[0]} ({addr[1]})')

                    self.update_udp_addrs.append(addr)
                # If the socket is the server socket, accept as a connection
                elif sock == self.internal_socket:
                    conn, addr = sock.accept()
                    self.logger.info(
                        f'[+] Internal Server connected to {addr[0]} ({addr[1]})')
                    t = threading.Thread(
                        target=self.listen_internal, args=(conn,))
                    t.start()
                    procs.append(t)

                    # self.internal_addrs.append(addr)
                # Otherwise, close the socket
                else:
                    sock.close()
                    inputs.remove(sock)
        except Exception as e:
            self.logger.exception(e)
        except KeyboardInterrupt:
            self.logger.info('Shutting down server.')
        finally:
            # uncomment below to empty directory: for upload debugging
            os.system(f'rm -rf server_{self.server_id}_files/*')

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
