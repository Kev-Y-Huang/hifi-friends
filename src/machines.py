from typing import List
import socket
IP = socket.gethostname()

class Machine:
    """
    A class that represents the identity of a machine. Stores information about which
    ip/port the machine is listening on and what machines it connects to.
    """

    def __init__(
        self,
        id: int,
        ip: str,
        tcp_port: int,
        audio_udp_port: int,
        update_udp_port: int,
        internal_port: int
    ) -> None:
        self.id = id
        self.ip = ip
        self.tcp_port = tcp_port
        self.audio_udp_port = audio_udp_port
        self.update_udp_port = update_udp_port
        self.internal_port = internal_port
        self.conn = None
        self.accepted = False
        self.promise_value = 0


MACHINE_ZERO = Machine(
    id=0,
    # ip="localhost",
    ip=IP,
    tcp_port=6201,
    audio_udp_port=6202,
    update_udp_port=6203,
    internal_port=6204
)

MACHINE_ONE = Machine(
    id=1,
    # ip="localhost",
    ip=IP,
    tcp_port=6211,
    audio_udp_port=6212,
    update_udp_port=6213,
    internal_port=6214
)

MACHINE_TWO = Machine(
    id=2,
    # ip="localhost",
    ip=IP,
    tcp_port=6221,
    audio_udp_port=6222,
    update_udp_port=6223,
    internal_port=6224
)

# Create a mapping from machine name to information about it
# MACHINES = [MACHINE_ZERO, MACHINE_ONE, MACHINE_TWO]
MACHINES = dict(enumerate([MACHINE_ZERO, MACHINE_ONE]))


def get_other_machines(id: int):
    """
    Returns a list of all the machines that are not the machine with the given id.
    """
    machines_copy = MACHINES.copy()
    del machines_copy[id]
    return machines_copy

