import os
import queue
import socket
import sys
import threading
import time

import pyaudio

HOST = socket.gethostname()
TCP_PORT = 1538
UDP_PORT = 1539

class Client:
    def __init__(self, host=HOST, tcp_port=TCP_PORT, udp_port=UDP_PORT):
        self.s = socket.socket()
        self.host = host
        self.tcp_port = tcp_port
        self.udp_port = udp_port

    def upload_file(self, file_path):
        filename = os.path.basename(file_path)
        size = len(filename)
        size = bin(size)[2:].zfill(16) # encode filename size as 16 bit binary, limit your filename length to 255 bytes

        self.s.send(size.encode())
        self.s.send(filename.encode())

        filesize = os.path.getsize(file_path)
        filesize = bin(filesize)[2:].zfill(32) # encode filesize as 32 bit binary
        self.s.send(filesize.encode())

        file_to_send = open(file_path, 'rb')

        l = file_to_send.read()
        self.s.sendall(l)
        file_to_send.close()
        print('File Sent')

    def connect_to_server(self):
        self.s.connect((self.host, self.tcp_port))

        while True:
            file_path = input()
            self.upload_file(file_path)

    def stream_audio(self):
        try:
            BUFF_SIZE = 65536
            client_socket = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
            client_socket.setsockopt(socket.SOL_SOCKET,socket.SO_RCVBUF,BUFF_SIZE)
            p = pyaudio.PyAudio()
            CHUNK = 10*1024
            stream = p.open(format=p.get_format_from_width(2),
                            channels=2,
                            rate=48000,
                            output=True,
                            frames_per_buffer=CHUNK)
                            
            # create socket
            message = b'Hello'
            client_socket.sendto(message,(self.host,self.udp_port))
            DATA_SIZE,_= client_socket.recvfrom(BUFF_SIZE)
            DATA_SIZE = int(DATA_SIZE.decode())
            q = queue.Queue(maxsize=DATA_SIZE)
            cnt=0
            def getAudioData():
                while True:
                    frame,_= client_socket.recvfrom(BUFF_SIZE)
                    q.put(frame)
                    # print('[Queue size while loading]...',q.qsize())
                        
            t1 = threading.Thread(target=getAudioData, args=())
            t1.start()
            time.sleep(5)
            DURATION = DATA_SIZE*CHUNK/48000
            # print('[Now Playing]... Data',DATA_SIZE,'[Audio Time]:',DURATION ,'seconds')
            while True:
                frame = q.get()
                stream.write(frame)
                # print('[Queue size while playing]...',q.qsize(),'[Time remaining...]',round(DURATION),'seconds')
                DURATION-=CHUNK/48000
                if q.empty():
                    break
        except:
            client_socket.close()
            print('Audio closed')
            sys.exit(1)

if __name__ == "__main__":
    client = Client()
    t1 = threading.Thread(target=client.stream_audio, args=())
    t1.start()
    client.connect_to_server()
