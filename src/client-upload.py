import socket
import os

HOST = socket.gethostname()
PORT = 1538

class Client:
    def __init__(self, host=HOST, port=PORT):
        self.s = socket.socket()
        self.host = host
        self.port = port

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
        self.s.connect((self.host, self.port))

        while True:
            file_path = input()
            self.upload_file(file_path)

if __name__ == "__main__":
    client = Client()
    client.connect_to_server()
