import socket
import time
from wire_protocol import pack_packet

class Paxos:
    def __init__(self):
        self.servers = []
        self.id = 0
        self.clock = 0
        self.gen_number = 0

        self.accept_operation = None
        self.promise_value = 0
        self.promise_responses = {}


    def send_prepare(self):
        """
        Send a prepare message to all other servers with a unique generation number
        """
        # update internal clock and generation number
        self.clock += 1
        self.gen_number = f'{self.clock}{self.id}'

        # send generation number to servers
        for server in self.servers:
            conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            conn.connect((server.ip, server.internal_port))
            conn.send(pack_packet(str(self.gen_number), 8, ""))

    def send_promise(self, proposer_conn, gen_number):
        """
        After receiving a prepare message, send a promise message to proposing server
        """
        promise_message = self.gen_number
        if self.accept_operation is None:
            promise_message = max(promise_message, gen_number)
        proposer_conn.send(pack_packet(str(promise_message), 9, self.accept_operation))
        self.gen_number = promise_message

        return self.gen_number

    def handle_promise(self, server_id, gen_number, accept_operation):
        """
        Update dictionary of promise values from servers.
        If a majority of servers agree, send an accept message
        """

        # server accepted another value:
        if accept_operation:
            if gen_number > self.promise_value:
                self.promise_value = gen_number
                self.accept_operation = accept_operation
                self.servers[server_id].accepted = True
                # iterate through servers and update accepted value
                for server in self.servers:
                    if server.promise_value < self.promise_value:
                        server.accepted = False

            self.promise_responses[server_id] = self.gen_number
        else:
            # server agrees on proposed value or already promised another proposal
            if gen_number >= self.gen_number:
                self.promise_responses[server_id] = gen_number

        responses = sum(1 for value in self.promise_responses.values() if value == self.gen_number)

        # Quorum has been reached, send accept message to all servers
        if responses > len(self.servers) // 2:
            self.send_accept()

        # All servers have responded, and a quorum has not been reached
        elif None not in self.promise_responses.values():
            # After sleeping, resend prepares with higher generation number
            time.sleep(1)
            self.send_prepare()


    def send_accept(self):
        """
        Send an accept message to all servers
        """
        for server in self.servers:
            if not server.accepted:
                conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                conn.connect((server.ip, server.internal_port))
                # TODO send actual operation along with generation number
                conn.send(pack_packet(str(self.gen_number), 10, ""))

    def handle_accept(self, proposer_conn, op, gen_number):
        """
        Process an accept message. Only accept if the message's generation
        number is higher
        """
        if gen_number < self.gen_number:
            proposer_conn.send(pack_packet(str(self.id), 11, "reject"))
        else:
            self.accept_operation = op
            # TODO perform actual operation
            proposer_conn.send(pack_packet(str(self.gen_number), 11, "accept"))












