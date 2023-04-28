import socket
import threading

class Server:
    def __init__(self, port=1538):
        self.port = port
        self.tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    
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

    
    def on_new_client(self, c_sock):
        while True:
            self.recv_file(c_sock)
    
    def start_server(self):
        self.tcp_sock.bind((socket.gethostname(), 1538))

        print('\nServer started!')

        self.tcp_sock.listen(5)

        print('\nWaiting for incoming connections...')

        while True:
            c_sock, addr = self.tcp_sock.accept()

            print(f'\n[+] Connected to {addr[0]} ({addr[1]})\n')

            # Start a new thread for each client
            t = threading.Thread(target=self.on_new_client, args=(c_sock,))
            t.start()


if __name__ == "__main__":
    server = Server()
    server.start_server()



