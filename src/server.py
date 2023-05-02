import math
import select
import socket
import threading
import time
import wave

import pyaudio

from utils import setup_logger

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

    def recv_file(self, c_sock):
        """
        Receive a file from the client.
        ...

        Parameters
        ----------
        c_sock : socket.socket
            The socket to receive the file from.
        """
        filename_size = c_sock.recv(16)
        filename_size = int(filename_size, 2)

        filename = c_sock.recv(filename_size)
        filesize = c_sock.recv(32)
        filesize = int(filesize, 2)

        file_to_write = open('server_files/' + filename, 'wb')
        chunksize = 4096

        self.logger.info('Receiving file: ' + filename)

        # TODO figure out how to rewrite
        while filesize > 0:
            if filesize < chunksize:
                chunksize = filesize
            data = c_sock.recv(chunksize)
            file_to_write.write(data)
            filesize -= len(data)

        file_to_write.close()

        self.logger.info('File received successfully.')
    
    def handle_tcp_client(self, c_sock):
        """
        Handle a TCP client connection.
        ...

        Parameters
        ----------
        c_sock : socket.socket
            The socket to handle.
        """
        inputs = [c_sock]

        try:
            # Continuously poll for messages while exit event has not been set
            while not self.exit.is_set():
                # Use select.select to poll for messages
                read_sockets, _, _ = select.select(inputs, [], [], 1)

                for sock in read_sockets:
                    data = sock.recv(1)
                    if data:
                        opcode = data.decode()

                        # If the opcode is 1, we are receiving a file
                        if opcode == '1':
                            self.logger.info('[1] Receiving file.')
                            self.recv_file(sock)
                        # TODO implement the rest of the opcodes
                        # If the opcode is 2, we are queuing a file
                        elif opcode == '2':
                            self.logger.info('[1] Queuing file.')
                    # If there is no data, we remove the connection
                    else:
                        for sock in inputs:
                            sock.close()
        except:
            for sock in inputs:
                sock.close()

        print("thread closed")

    def handle_udp_client(self, c_sock, addr):
        """
        Handle a UDP client connection.
        ...

        Parameters
        ----------
        c_sock : socket.socket
            The socket to handle.
        addr : tuple
            The address of the client.
        """
        wf = wave.open("temp.wav")
        p = pyaudio.PyAudio()
        stream = p.open(format=p.get_format_from_width(wf.getsampwidth()),
                        channels=wf.getnchannels(),
                        rate=wf.getframerate(),
                        input=True,
                        frames_per_buffer=CHUNK)

        data = None
        sample_rate = wf.getframerate()
        while not self.exit.is_set():
            DATA_SIZE = math.ceil(wf.getnframes()/CHUNK)
            DATA_SIZE = str(DATA_SIZE).encode()
            self.logger.info(
                f'Sending data size {wf.getnframes()/sample_rate}')
            c_sock.sendto(DATA_SIZE, addr)
            cnt = 0
            while not self.exit.is_set():
                data = wf.readframes(CHUNK)
                c_sock.sendto(data, addr)
                # Here you can adjust it according to how fast you want to send data keep it > 0
                time.sleep(0.001)

                if cnt > (wf.getnframes()/CHUNK):
                    break
                cnt += 1

            break
        stream.stop_stream()
        stream.close()
        p.terminate()
        wf.close()
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

        # Create a list of sockets to listen to
        inputs = [self.tcp_sock, self.udp_sock]

        # Create a list of threads
        procs = []

        self.logger.info('Waiting for incoming connections')
        try:
            while not self.exit.is_set():
                read_sockets, _, _ = select.select(inputs, [], [], 0.1)

                for sock in read_sockets:
                    # If the socket is the server socket, accept as a connection
                    if sock == self.tcp_sock:
                        client, addr = sock.accept()
                        inputs.append(client)

                        self.logger.info(
                            f'[+] TCP connected to {addr[0]} ({addr[1]})')

                        # Start a new thread for each client
                        proc = threading.Thread(
                            target=self.handle_tcp_client, args=(client,))
                        proc.start()
                        procs.append(proc)
                    # If the socket is the server socket, accept as a connection
                    if sock == self.udp_sock:
                        _, addr = sock.recvfrom(BUFF_SIZE)
                        # TODO this is probably not right -\_(0_0)_/-
                        inputs.append(sock)

                        self.logger.info(
                            f'[+] UDP connected to {addr[0]} ({addr[1]})')

                        # Start a new thread for each client
                        proc = threading.Thread(
                            target=self.handle_udp_client, args=(sock, addr,))
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
            self.exit.set()
            for proc in procs:
                proc.join()
            # for conn in inputs:
            #     conn.close()


if __name__ == "__main__":
    server = Server()
    server.run_server()
