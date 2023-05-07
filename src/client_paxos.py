import os
import queue
import select
import socket
import sys
import threading
import time
import traceback

import pyaudio

from utils import Operation, Update, Message, poll_read_sock_no_exit, queue_rows
from wire_protocol import (pack_num, pack_opcode, unpack_audio_meta,
                           unpack_state, unpack_msgcode)
from machines import MACHINES

HOST = socket.gethostname()

server_number = 0
TCP_PORT = MACHINES[server_number].tcp_port
AUDIO_UDP_PORT = MACHINES[server_number].audio_udp_port
UPDATE_UDP_PORT = MACHINES[server_number].update_udp_port

BUFF_SIZE = 65536
CHUNK = 10 * 1024


class Song:
    def __init__(self, width=None, sample_rate=None, n_channels=None):
        self.width = width
        self.sample_rate = sample_rate
        self.n_channels = n_channels

        self.frames = queue.Queue()

    def update_metadata(self, width, sample_rate, n_channels):
        self.width = width
        self.sample_rate = sample_rate
        self.n_channels = n_channels

    def add_frame(self, frame):
        self.frames.put(frame)


class Client:
    def __init__(self, host=HOST, tcp_port=TCP_PORT, audio_udp_port=AUDIO_UDP_PORT, update_udp_port=UPDATE_UDP_PORT):
        self.host = host

        # TCP connection to server
        self.tcp_port = tcp_port
        self.server_tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_number = server_number

        # UDP connection for audio
        self.audio_udp_port = audio_udp_port
        self.audio_udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.audio_udp_sock.setsockopt(
            socket.SOL_SOCKET, socket.SO_RCVBUF, BUFF_SIZE)
        
       # UDP connection for server updates
        self.update_udp_port = update_udp_port
        self.update_udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.update_udp_sock.setsockopt(
            socket.SOL_SOCKET, socket.SO_RCVBUF, BUFF_SIZE)

        self.exit = threading.Event()

        self.can_input = threading.Event()
        self.can_input.set()

        self.song_queue = queue.Queue()
        self.curr_song_frames = None

        self.song_name_queue = queue.Queue()

        self.stream = None

        # Keeping track of song and frame index
        self.song_index = 0
        self.frame_index = 0
        self.server_song_index = 0
        self.server_frame_index = 0

        # Keeps track of whether audio is paused or not for everybody
        self.is_paused = False

    def upload_file(self, file_path):
        """
        Upload a file to the server.
        ...

        Parameters
        ----------
        file_path : str
            The path to the file to upload.
        """
        for _ in range(len(MACHINES)):
            try:
                # Pause user input until finished uploading
                self.can_input.clear()

                self.server_tcp.send(pack_opcode(Operation.UPLOAD))

                file_name = os.path.basename(file_path)
                self.server_tcp.send(pack_num(len(file_name), 16))
                self.server_tcp.send(file_name.encode())
                self.server_tcp.send(pack_num(os.path.getsize(file_path), 32))

                with open(file_path, 'rb') as file_to_send:
                    self.server_tcp.sendall(file_to_send.read())

                print('File Sent')
                # break if file is sent
                break
            except (ConnectionRefusedError, BrokenPipeError):
                self.server_number += 1
                self.server_number %= len(MACHINES)
                self.server_tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.server_tcp.connect((self.host, MACHINES[self.server_number].tcp_port))

            # self.server_tcp.close()
            # for _ in range(3):
            #     # Leader election find the lowest index server that is available
            #     self.server_number += 1
            #     self.server_number %= len(MACHINES)
            #     self.server_tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            #     self.server_tcp.connect((self.host, MACHINES[self.server_number].tcp_port))

    def upload_file_flask(self, file):
        """
        Upload a file to the server (for Flask application).
        ...

        Parameters
        ----------
        file_path : FileStorage object
            The file to upload.
        """
        self.server_tcp.send(pack_opcode(Operation.UPLOAD))

        file_name = file.filename
        self.server_tcp.send(pack_num(len(file_name), 16))
        self.server_tcp.send(file_name.encode())

        data = file.read()

        self.server_tcp.send(pack_num(len(data), 32))
        self.server_tcp.sendall(data)

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
        self.server_tcp.send(pack_opcode(Operation.QUEUE))
        self.server_tcp.send(filename.encode())

    def get_song_list(self):
        """
        Gets the available songs for queueing from the server and prints them.
        """
        self.server_tcp.send(pack_opcode(Operation.LIST))

    def get_current_queue(self):
        """
        Gets the current queue prints it.
        """
        song_queue_str = ','.join(str(item) for item in self.song_name_queue.queue)
        print(f'[{song_queue_str}]')

    def pause_stream(self):
        """
        Stops the stream.
        """
        if self.stream:
            self.server_tcp.send(pack_opcode(Operation.PAUSE))
            self.is_paused = True
        else:
            print("No stream to stop.")

    def play_stream(self):
        """
        Plays the stream.
        """
        if self.stream:
            self.server_tcp.send(pack_opcode(Operation.PLAY))
            self.is_paused = False
        else:
            print("No stream to play.")

    def skip_song(self):
        """
        Skips the current song.
        """
        if self.stream:
            self.server_tcp.send(pack_opcode(Operation.SKIP))
            with self.curr_song_frames.mutex:
                self.curr_song_frames.queue.clear()
        else:
            print("No song to skip.")

    def get_audio_data(self):
        """
        Get audio data from the server.
        """
        inputs = [self.audio_udp_sock]

        try:
            self.audio_udp_sock.sendto(
                b'Connect', (self.host, self.audio_udp_port))
            for sock in poll_read_sock_no_exit(inputs, self.exit):
                frame, _ = sock.recvfrom(BUFF_SIZE)

                if len(frame) == 13:
                    delim, width, sample_rate, channels = unpack_audio_meta(
                        frame)

                    if delim == 0:
                        song = Song(width, sample_rate, channels)
                        self.song_queue.put(song)
                        continue

                song.add_frame(frame)
        except Exception:
            print(traceback.format_exc())
        finally:
            self.audio_udp_sock.close()
            print('Audio closed')

    def process_song(self):
        """
        Process the song queue.
        ...

        Parameters
        ----------
        song_q : queue.Queue
            The queue of song frames to process.
        """
        for frame in queue_rows(self.curr_song_frames):
            if self.exit.is_set():
                return
            # TODO definitely can do this better
            while self.stream.is_stopped():
                # TODO figure out better place to move frame index update
                if self.frame_index < self.server_frame_index:
                    self.frame_index += 1
                    # skip frame
                    self.curr_song_frames.get()
                if self.exit.is_set():
                    return
                # Start the steam again if someone hit play
                if not self.is_paused and self.stream:
                    self.stream.start_stream()
                time.sleep(0.1)
            self.frame_index += 1

            # Stop the stream if someone paused
            if self.is_paused and not self.stream.is_stopped():
                self.stream.stop_stream()
            # Write frame to the stream otherwise
            else:
                self.stream.write(frame)

    def stream_audio(self):
        """
        Stream audio from the server.
        """
        p = pyaudio.PyAudio()

        try:
            while not self.exit.is_set():
                if self.song_queue.empty():
                    time.sleep(0.01)
                    continue

                song = self.song_queue.get()
                self.song_index += 1

                self.stream = p.open(format=p.get_format_from_width(song.width),
                                     channels=song.n_channels,
                                     rate=song.sample_rate,
                                     output=True,
                                     frames_per_buffer=CHUNK)

                self.curr_song_frames = song.frames
                self.process_song()

                self.stream.stop_stream()
                self.stream.close()
                self.stream = None

                if not self.song_name_queue.empty():
                    self.song_name_queue.get()
        except Exception:
            print(traceback.format_exc())
        finally:
            p.terminate()
            print('Stream closed')

    def server_update(self):
        """
        Update the server with the current state of the audio stream for the client.
        """
        inputs = [self.update_udp_sock]
        self.update_udp_sock.sendto(
            b'Connect', (self.host, self.update_udp_port))

        try:
            for sock in poll_read_sock_no_exit(inputs, self.exit):
                data, _ = sock.recvfrom(BUFF_SIZE)

                if not data:
                    break

                self.server_song_index, self.server_frame_index, action = unpack_state(
                    data)

                if self.stream:
                    if action == Update.PAUSE and self.stream.is_active():
                        self.is_paused = True
                    elif action == Update.PLAY and not self.stream.is_active():
                        self.is_paused = False
                    elif action == Update.SKIP:
                        self.curr_song_frames.queue.clear()
        except Exception:
            print(traceback.format_exc())
        finally:
            self.update_udp_sock.close()
            print('Server update closed')

    def server_messages(self):
        """
        Listen for messages from the server on the TCP socket.
        """
        try:
            while not self.exit.is_set():
                data = self.server_tcp.recv(1)

                # If there is no data, the connection has been closed
                if not data:
                    break

                msgcode = unpack_msgcode(data)

                if msgcode == Message.PRINT:
                    message = self.server_tcp.recv(1024).decode()
                    print(message)
                elif msgcode == Message.QUEUE:
                    song_name = self.server_tcp.recv(1024).decode()
                    self.song_name_queue.put(song_name)
                elif msgcode == Message.DONE_UPLOADING:
                    message = self.server_tcp.recv(1024).decode()
                    print(message)
                    # Unpause user input
                    self.can_input.set()

        except Exception as e:
            print(e)

    def run_client(self):
        """
        Run the client.
        """
        self.server_tcp.connect((self.host, self.tcp_port))

        get_audio_data_proc = threading.Thread(
            target=self.get_audio_data, args=())
        get_audio_data_proc.start()

        stream_proc = threading.Thread(target=self.stream_audio, args=())
        stream_proc.start()

        server_update_proc = threading.Thread(
            target=self.server_update, args=())
        server_update_proc.start()

        server_messages_proc = threading.Thread(
            target=self.server_messages, args=())
        server_messages_proc.start()

        try:
            while not self.exit.is_set():
                time.sleep(0.1)
                self.can_input.wait()
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
                elif op_code == '4':
                    self.get_current_queue()
                elif op_code == '5':
                    self.pause_stream()
                elif op_code == '6':
                    self.play_stream()
                elif op_code == '7':
                    self.skip_song()
                else:
                    print("Invalid Operation Code. Please try again.")
        except Exception as e:
            print(e)
        finally:
            self.exit.set()

            self.server_tcp.close()

            stream_proc.join()
            get_audio_data_proc.join()
            server_update_proc.join()
            server_messages_proc.join()

            print('Client closed')
            sys.exit(1)


if __name__ == "__main__":
    client = Client()
    client.run_client()
