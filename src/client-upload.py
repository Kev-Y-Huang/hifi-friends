import socket
import os

s = socket.socket()
host = socket.gethostname()
port = 1538
s.connect((host, port))
path = "samples"
directory = os.listdir(path)

while True:
    file_path = input()

    filename = os.path.basename(file_path)
    size = len(filename)
    size = bin(size)[2:].zfill(16) # encode filename size as 16 bit binary, limit your filename length to 255 bytes

    s.send(size.encode())
    s.send(filename.encode())

    filesize = os.path.getsize(file_path)
    filesize = bin(filesize)[2:].zfill(32) # encode filesize as 32 bit binary
    s.send(filesize.encode())

    file_to_send = open(file_path, 'rb')

    l = file_to_send.read()
    s.sendall(l)
    file_to_send.close()
    print('File Sent')

    

s.close()