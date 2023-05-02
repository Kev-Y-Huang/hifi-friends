import socket
import time
from wire_protocol import pack_packet
from machines import MACHINES, get_other_machines, get_other_machines_ids
from collections import defaultdict


class PaxServer:
    def __init__(self):
        self.conn = None
        self.accepted = False
        self.promise_value = 0

class Paxos:
    def __init__(self, server_id):
        self.machines = defaultdict(PaxServer)
        self.server_id = server_id
        self.clock = 0
        self.gen_number = 0

        self.accept_operation = ""
        self.quorum_reached = False
        self.promise_value = 0

    def send_prepare(self):
        """
        Send a prepare message to all other servers with a unique generation number
        """
        # update internal clock and generation number
        self.clock += 1
        self.gen_number = int(f'{self.clock}{self.server_id}')
        # send generation number to servers
        print('gen_number', self.gen_number)
        for server in self.machines:
            conn = self.machines[server].conn
            conn.send(pack_packet(self.server_id, self.gen_number, 8, ""))

    def send_promise(self, server_id, gen_number):
        """
        After receiving a prepare message, send a promise message to proposing server
        """
        print("gen_number: ", str(gen_number))
        proposer_conn = self.machines[server_id].conn
        promise_message = self.gen_number

        # if there is no accept, send a promise message with most updated gen_number
        if self.accept_operation == "":
            promise_message = max(promise_message, int(gen_number))

        print("promise_message: ", str(promise_message))
        proposer_conn.send(pack_packet(self.server_id, promise_message, 9, self.accept_operation))
        self.gen_number = promise_message
        print("new gen number:", self.gen_number)

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
        if responses >= len(self.machines) // 2:
            print('should accept')
            self.send_accept(filename)

        # All servers have responded, and a quorum has not been reached
        elif any(x.promise_value is None for x in self.machines.values()):
            # After sleeping, resend prepares with higher generation number
            time.sleep(1)
            print('send another prepare')
            # self.send_prepare()


    def send_accept(self, filename):
        """
        Send an accept message to all servers
        """
        for server_id in self.machines:
            server = self.machines[server_id]
            if not server.accepted:
                # op code 10 refers to an upload operation
                server.conn.send(pack_packet(self.server_id, self.gen_number, 10, filename))

    def handle_accept(self, server_id, gen_number):
        """
        Process an accept message. Only accept if the message's generation
        number is higher
        """
        proposer_conn = self.machines[server_id].conn
        if gen_number < self.gen_number:
            proposer_conn.send(pack_packet(self.server_id,  self.gen_number, 11, "reject"))
        else:
            # TODO perform actual operation
            proposer_conn.send(pack_packet(self.server_id,  self.gen_number, 11, "accept"))
