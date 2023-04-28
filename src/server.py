import math
import select
import socket
import threading
import time
import wave

import pyaudio

BUFF_SIZE = 65536
CHUNK = 10*1024

class Server:
    def __init__(self, tcp_port=1538, udp_port=1539):
        self.tcp_port = tcp_port
        self.udp_port = udp_port
        self.tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.udp_sock = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        self.udp_sock.setsockopt(socket.SOL_SOCKET,socket.SO_RCVBUF,BUFF_SIZE)
    
    # Receive a single file upload from client
    def recv_file(self, c_sock):
        size = c_sock.recv(16).decode() 
        size = int(size, 2)

        if not size:
            return

        filename = c_sock.recv(size).decode()
        filesize = c_sock.recv(32).decode()
        filesize = int(filesize, 2)

        file_to_write = open('server_files/' + filename, 'wb')
        chunksize = 4096

        while filesize > 0:
            if filesize < chunksize:
                chunksize = filesize
            data = c_sock.recv(chunksize)
            file_to_write.write(data)
            filesize -= len(data)

        file_to_write.close()
        print('File received successfully')

    
    def on_new_tcp_client(self, c_sock):
        while True:
            self.recv_file(c_sock)

    
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
            DATA_SIZE = math.ceil(wf.getnframes()/CHUNK)
            DATA_SIZE = str(DATA_SIZE).encode()
            print('[Sending data size]...',wf.getnframes()/sample_rate)
            c_sock.sendto(DATA_SIZE,addr)
            cnt=0
            while True:
                data = wf.readframes(CHUNK)
                c_sock.sendto(data,addr)
                time.sleep(0.001) # Here you can adjust it according to how fast you want to send data keep it > 0
                print(cnt)
                if cnt >(wf.getnframes()/CHUNK):
                    break
                cnt+=1

            break
        print('SENT...')
    
    def start_server(self):
        self.tcp_sock.bind((socket.gethostname(), self.tcp_port))
        self.udp_sock.bind((socket.gethostname(), self.udp_port))

        print('\nServer started!')

        self.tcp_sock.listen(5)

        inputs = [self.tcp_sock, self.udp_sock]
        procs = []

        print('\nWaiting for incoming connections...')
        self.server_running = True
        try:
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
                        inputs.append(sock) # TODO this is probably not right -\_(0_0)_/-

                        print(f'\n[+] UDP connected to {addr[0]} ({addr[1]})\n')
                        
                        # Start a new thread for each client
                        proc = threading.Thread(target=self.on_new_udp_client, args=(sock,addr,))
                        proc.start()
                        procs.append(proc)
                    # Otherwise, read the data from the socket
                    else:
                        data = sock.recv(1024)
                        if data:
                            sock.send("ping".encode(encoding='utf-8'))
                        # If there is no data, then the connection has been closed
                        else:
                            sock.close()
                            inputs.remove(sock)
        except Exception as e:
            print(e)
            for conn in inputs:
                conn.close()
            for proc in procs:
                proc.shutdown()
            for proc in procs:
                proc.join()

        # while True:
        #     c_sock, addr = self.tcp_sock.accept()

        #     print(f'\n[+] Connected to {addr[0]} ({addr[1]})\n')

        #     # Start a new thread for each client
        #     t = threading.Thread(target=self.on_new_client, args=(c_sock,))
        #     t.start()


if __name__ == "__main__":
    server = Server()
    server.start_server()



