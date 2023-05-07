import socket
import time

from utils import Operation
import os
from wire_protocol import pack_packet, pack_opcode, pack_num


class Paxos:
    def __init__(self, server_id):
        self.machines = dict()
        self.server_id = server_id
        self.clock = 0
        self.gen_number = 0
        self.conn = None
        self.connected = True

        self.accept_operation = ""
        self.quorum_reached = False
        self.promise_value = 0
        self.accept_sent = False

    def send_prepare(self):
        """
        Send a prepare message to all other servers with a unique generation number
        """
        # update internal clock and generation number
        self.clock += 1
        self.gen_number = int(f'{self.clock}{self.server_id}')
        # send generation number to servers
        for server in self.machines:
            try:
                self.machines[server].conn.send(pack_opcode(Operation.PREPARE))
                self.machines[server].conn.send(pack_packet(self.server_id, self.gen_number, ""))
            except BrokenPipeError:
                self.machines[server].connected = False

        print('prepares sent')

    def send_promise(self, server_id, gen_number):
        """
        After receiving a prepare message, send a promise message to proposing server
        """
        proposer_conn = self.machines[server_id].conn
        promise_message = self.gen_number

        # if there is no accept, send a promise message with most updated gen_number
        if self.accept_operation == "":
            promise_message = max(promise_message, int(gen_number))

        proposer_conn.send(pack_opcode(Operation.PROMISE))
        proposer_conn.send(pack_packet(self.server_id, promise_message, self.accept_operation))
        self.gen_number = promise_message
        print('promise sent')

    def handle_promise(self, server_id, gen_number, filename, accept_operation=False):
        """
        Update dictionary of promise values from servers.
        If a majority of servers agree, send an accept message
        """
        server_id = int(server_id)
        # server accepted another value:
        if accept_operation:
            # the accepted operation is higher-ordered and takes precedence
            if gen_number > self.promise_value:
                self.promise_value = gen_number
                self.accept_operation = accept_operation
                self.machines[server_id].accepted = True
                # iterate through servers and update accepted value
                for server in self.machines:
                    if self.machines[server].promise_value < self.promise_value:
                        server.accepted = False

            self.machines[server_id].promise_value = self.gen_number
        else:
            # server agrees on proposed value or already promised another proposal
            if int(gen_number) >= self.gen_number:
                self.machines[server_id].promise_value = gen_number

        responses = sum(1 for value in self.machines.values() if value.promise_value == self.gen_number)

        # Quorum has been reached, send accept message to all servers
        if responses >= len(self.machines) // 2 and not self.accept_sent:
            self.accept_sent = True
            self.send_accept(filename)
            print('accept sent')

        # All servers have responded, and a quorum has not been reached
        elif any(x.promise_value is None for x in self.machines.values()):
            # After sleeping, resend prepares with higher generation number
            time.sleep(1)
            print('send another prepare')
            self.send_prepare()


    def send_accept(self, filename):
        """
        Send an accept message to all servers
        """
        for server_id in self.machines:
            server = self.machines[server_id]
            if server.connected and not server.accepted:
                try:
                    # op code 10 refers to an upload operation
                    server.conn.send(pack_opcode(Operation.ACCEPT))
                    server.conn.send(pack_packet(self.server_id, self.gen_number, filename))
                except BrokenPipeError:
                    server.connected = False


    def handle_accept(self, server_id, gen_number):
        """
        Process an accept message. Only accept if the message's generation
        number is higher
        """
        proposer_conn = self.machines[server_id].conn
        proposer_conn.send(pack_opcode(Operation.ACCEPT_RESPONSE))
        if gen_number < self.gen_number:
            proposer_conn.send(pack_packet(self.server_id,  self.gen_number, "reject"))
        else:
            # TODO perform actual operation
            proposer_conn.send(pack_packet(self.server_id,  self.gen_number, "accept"))

    def commit_op(self, server_id, filename, operation):
        if operation == "upload":
            server = self.machines[server_id]
            if not server.accepted:
                try:
                    s = socket.socket()
                    s.connect((server.ip, server.internal_port))
                    upload_file(s, f'server_{self.server_id}_files/{filename}')
                except:
                    print(f'server {server_id} is dead')

        self.accept_sent = False


def upload_file(conn, file_path):
    """
    Upload a file to the server.
    ...

    Parameters
    ----------
    file_path : str
        The path to the file to upload.
    """
    conn.send(pack_opcode(Operation.SERVER_UPLOAD))

    file_name = os.path.basename(file_path)
    conn.send(pack_num(len(file_name), 16))
    conn.send(file_name.encode())
    conn.send(pack_num(os.path.getsize(file_path), 32))

    with open(file_path, 'rb') as file_to_send:
        conn.sendall(file_to_send.read())

    print('File Sent')



