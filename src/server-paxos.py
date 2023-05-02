import math
import select
import socket
import threading
import time
import wave
import argparse
import sys

from music_service import User

import pyaudio
import logging

from machines import MACHINES, get_other_machines, get_other_machines_ids
from wire_protocol import pack_packet, unpack_packet
from queue import Queue
from paxos import *
FREQUENCY = 1 # Frequency of heartbeat in seconds

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

        # Paxos
        self.clock = 0
        self.gen_number = 0
        self.promise_responses = {}
        self.accept_operation = ""
        self.paxos = Paxos(server_id)
        self.paxos.servers = get_other_machines(server_id)

        self.queue = Queue()
        self.lockReady = threading.Lock()
        self.server_running = True
        self.filename = None
        self.operation = None

    def initiate_paxos(self):
        print("paxos initiated")
        self.paxos.send_prepare()
        # Wait for servers to send back promise messages
        time.sleep(1)



    # Receive a single file upload from client
    def recv_file(self, c_sock):
        size = c_sock.recv(16).decode()
        size = int(size, 2)


        if not size:
            return
        filename = c_sock.recv(size).decode()
        filesize = c_sock.recv(32).decode()
        filesize = int(filesize, 2)

        self.filename = filename
        self.operation = 'upload'


        file_to_write = open(f'server_{self.server_id}_files/' + filename, 'wb')
        chunksize = 4096

        while filesize > 0:
            if filesize < chunksize:
                chunksize = filesize
            data = c_sock.recv(chunksize)
            file_to_write.write(data)
            filesize -= len(data)

        file_to_write.close()
        print('File received successfully')
        # self.initiate_paxos()

    def on_new_tcp_client(self, conn):
        curr_user = User(conn)
        inputs = [conn]

        try:
            # Continuously poll for messages while exit event has not been set
            while self.server_running:
                self.recv_file(conn)
        except:
            for sock in inputs:
                sock.close()

    def on_new_udp_client(self, c_sock, addr):
        wf = wave.open("temp.wav")
        p = pyaudio.PyAudio()
        stream = p.open(format=p.get_format_from_width(wf.getsampwidth()),
                        channels=wf.getnchannels(),
                        rate=wf.getframerate(),
                        input=True,
                        frames_per_buffer=CHUNK)

        data = None
        sample_rate = wf.getframerate()
        while True:
            DATA_SIZE = math.ceil(wf.getnframes() / CHUNK)
            DATA_SIZE = str(DATA_SIZE).encode()
            print('[Sending data size]...', wf.getnframes() / sample_rate)
            c_sock.sendto(DATA_SIZE, addr)
            cnt = 0
            while True:
                data = wf.readframes(CHUNK)
                c_sock.sendto(data, addr)
                time.sleep(0.001)  # Here you can adjust it according to how fast you want to send data keep it > 0
                print(cnt)
                if cnt > (wf.getnframes() / CHUNK):
                    break
                cnt += 1

            break
        print('SENT...')

    def handle_queue(self):
        """
        Handles the queue of messages from the clients
        """
        while self.server_running:
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
            while self.server_running:
                read_sockets, _, _ = select.select(inputs, [], [], 0.1)

                for sock in read_sockets:
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
            # self.heart_socket.close()

    def setup_connections(self):
        """
        Sets up the connections to the other servers
        """
        for backup in self.machines:
            while True:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(FREQUENCY)
                # Ping the servers every FREQUENCY seconds to check if they are still alive
                # using the heart port
                try:
                    sock.connect((backup.ip, backup.heart_port))
                    sock.send("ping".encode(encoding='utf-8'))
                    sock.recv(2048)
                    sock.close()
                    break
                except:
                    logging.info(f"Setup failed for {backup.id}")
                    pass

        logging.info("Connection success")

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
                logging.info(f"Setup failed for {backup.id}")
                pass

    def start_server(self):
        print('\nServer started!')
        inputs = [self.tcp_sock, self.udp_sock]
        procs = []

        self.server_running = True
        try:
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

            print('\nWaiting for incoming client connections...')
            while self.server_running:
                read_sockets, _, _ = select.select(inputs, [], [], 0.1)

                for sock in read_sockets:
                    # If the socket is the server socket, accept as a connection
                    if sock == self.tcp_sock:
                        client, addr = sock.accept()
                        inputs.append(client)

                        print(f'\n[+] TCP connected to {addr[0]} ({addr[1]})\n')

                        # Start a new thread for each client
                        proc = threading.Thread(target=self.on_new_tcp_client, args=(client,))
                        proc.start()
                        procs.append(proc)

                    # If the socket is the server socket, accept as a connection
                    if sock == self.udp_sock:
                        _, addr = sock.recvfrom(BUFF_SIZE)
                        inputs.append(sock)  # TODO this is probably not right -\_(0_0)_/-

                        print(f'\n[+] UDP connected to {addr[0]} ({addr[1]})\n')

                        # Start a new thread for each client
                        proc = threading.Thread(target=self.on_new_udp_client, args=(sock, addr,))
                        proc.start()
                        procs.append(proc)
                    # Otherwise, read the data from the socket
                    else:
                        break  # TODO pls fix
                        # data = sock.recv(1024)
                        # if data:
                        #     sock.send("ping".encode(encoding='utf-8'))
                        # # If there is no data, then the connection has been closed
                        # else:
                        #     sock.close()
                        #     inputs.remove(sock)
        except Exception as e:
            print(e)
            for conn in inputs:
                conn.close()
            for proc in procs:
                proc.join()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Replicated Music Server")

    parser.add_argument("--server_number", "-s", choices=[0, 1, 2], type=int)
    args = parser.parse_args()

    server = Server(args.server_number)
    server.start_server()
