import os
import queue
import socket
import threading
import time
import wave

import pyaudio

from utils import (ActionType, Operation, poll_read_sock_no_exit, queue_rows,
                   send_to_all_addrs, setup_logger)
from wire_protocol import pack_state, unpack_num, unpack_opcode, pack_audio_meta

HOST = socket.gethostname()
TCP_PORT = 1538
AUDIO_UDP_PORT = 1539
UPDATE_UDP_PORT = 1540

BUFF_SIZE = 65536
CHUNK = 10*1024


class Server:
    def __init__(self, host=HOST, tcp_port=TCP_PORT, audio_udp_port=AUDIO_UDP_PORT, update_udp_port=UPDATE_UDP_PORT):
        self.host = host

        # TCP Setup
        self.tcp_port = tcp_port
        self.tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        # UDP Setup https://gist.github.com/ninedraft/7c47282f8b53ac015c1e326fffb664b5
        self.audio_udp_port = audio_udp_port
        self.udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_sock.setsockopt(
            socket.SOL_SOCKET, socket.SO_RCVBUF, BUFF_SIZE)

        # Client Update Setup
        self.update_udp_port = update_udp_port
        self.update_udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.update_udp_sock.setsockopt(
            socket.SOL_SOCKET, socket.SO_RCVBUF, BUFF_SIZE)

        # get list of files in server_files
        self.uploaded_files = os.listdir('server_files')

        self.logger = setup_logger()
        self.exit = threading.Event()

        self.song_queue = queue.Queue()

        self.audio_udp_addrs = []
        self.update_udp_addrs = []

        # Server state of audio playback
        self.song_index = 0
        self.frame_index = 0
        self.action_mutex = threading.Lock()
        self.action = ActionType.PING

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

        if file_name in self.uploaded_files:
            message = f'A file of the same name {file_name} is already being uploaded. Upload canceled.'
            self.logger.error(message)
            return message

        with open('server_files/' + file_name, 'wb') as file_to_write:
            chunk_size = 4096

            self.logger.info('Receiving file: ' + file_name)

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
            for sock in poll_read_sock_no_exit(inputs, self.exit):
                data = sock.recv(1)

                # If there is no data, the connection has been closed
                if not data:
                    break

                opcode = unpack_opcode(data)
                message = "No response."

                if opcode == Operation.CLOSE:
                    self.logger.info(
                        '[0] Receiving client closure request.')
                    # TODO implement client closure request
                    message = "Close not implemented."
                elif opcode == Operation.UPLOAD:
                    self.logger.info('[1] Receiving audio file.')
                    message = self.recv_file(sock)
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
                    self.action = ActionType.PAUSE
                    self.action_mutex.release()
                    message = 'Audio paused.'
                elif opcode == Operation.PLAY:
                    self.logger.info('[6] Playing audio.')
                    self.action_mutex.acquire()
                    self.action = ActionType.PLAY
                    self.action_mutex.release()
                    message = 'Audio playing.'
                elif opcode == Operation.SKIP:
                    self.logger.info('[7] Skipping audio.')
                    self.action_mutex.acquire()
                    self.action = ActionType.SKIP
                    self.action_mutex.release()
                    message = 'Song skipped.'
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

    def stream_audio(self):
        """
        Stream audio to the client.
        """
        p = pyaudio.PyAudio()

        while not self.exit.is_set():
            for song_name in queue_rows(self.song_queue):
                self.logger.info('Streaming audio.')
                song = wave.open(f"server_files/{song_name}")
                stream = p.open(format=p.get_format_from_width(song.getsampwidth()),
                                channels=song.getnchannels(),
                                rate=song.getframerate(),
                                input=True,
                                frames_per_buffer=CHUNK)

                width = song.getsampwidth()
                sample_rate = song.getframerate()
                n_channels = song.getnchannels()
                
                self.logger.info(
                    f'Sending width {width}, sample rate {sample_rate}, channels {n_channels}')
                data = pack_audio_meta(width, sample_rate, n_channels)
                send_to_all_addrs(self.udp_sock, self.audio_udp_addrs, data)
                
                while not self.exit.is_set():
                    cnt = 0
                    while not self.exit.is_set():
                        data = song.readframes(CHUNK)
                        send_to_all_addrs(
                            self.udp_sock, self.audio_udp_addrs, data)
                        # Here you can adjust it according to how fast you want to send data keep it > 0
                        time.sleep(0.001)

                        if cnt > (song.getnframes()/CHUNK):
                            break
                        cnt += 1

                    break
                stream.stop_stream()
                stream.close()
                song.close()

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

    def send_client_updates(self):
        """
        Sends client state updates
        """
        try:
            while not self.exit.is_set():
                self.action_mutex.acquire()
                send_to_all_addrs(self.update_udp_sock, self.update_udp_addrs, pack_state(
                    self.song_index, self.frame_index, self.action))
                self.action = ActionType.PING
                self.action_mutex.release()

                time.sleep(0.01)
        except Exception as e:
            self.logger.exception(e)
            self.update_udp_sock.close()

    def run_server(self):
        """
        Run the server.
        """
        self.logger.info('Server started!')

        # Bind tcp and udp sockets to ports
        self.tcp_sock.bind((socket.gethostname(), self.tcp_port))
        self.udp_sock.bind((socket.gethostname(), self.audio_udp_port))
        self.update_udp_sock.bind((socket.gethostname(), self.update_udp_port))

        # Listen for incoming connections
        self.tcp_sock.listen(5)

        client_update_proc = threading.Thread(
            target=self.send_client_updates, args=())
        client_update_proc.start()

        stream_proc = threading.Thread(target=self.stream_audio, args=())
        stream_proc.start()

        inputs = [self.tcp_sock, self.udp_sock, self.update_udp_sock]
        procs = [stream_proc, client_update_proc]

        self.logger.info('Waiting for incoming connections')
        try:
            for sock in poll_read_sock_no_exit(inputs, self.exit):
                if sock == self.tcp_sock:
                    conn, addr = sock.accept()

                    self.logger.info(
                        f'[+] TCP connected to {addr[0]} ({addr[1]})')

                    t = threading.Thread(
                        target=self.handle_tcp_conn, args=(conn,))
                    t.start()
                    procs.append(t)
                elif sock == self.udp_sock:
                    _, addr = sock.recvfrom(BUFF_SIZE)

                    self.logger.info(
                        f'[+] Audio UDP connected to {addr[0]} ({addr[1]})')

                    self.audio_udp_addrs.append(addr)
                elif sock == self.update_udp_sock:
                    _, addr = sock.recvfrom(BUFF_SIZE)

                    self.logger.info(
                        f'[+] Update UDP connected to {addr[0]} ({addr[1]})')

                    self.update_udp_addrs.append(addr)
                # Otherwise, read the data from the socket
                else:
                    sock.close()
                    inputs.remove(sock)
        except Exception as e:
            self.logger.exception(e)
        except KeyboardInterrupt:
            self.logger.info('Shutting down server.')
        finally:
            self.exit.set()

            for proc in procs:
                proc.join()
            for conn in inputs:
                conn.close()


if __name__ == "__main__":
    server = Server()
    server.run_server()
