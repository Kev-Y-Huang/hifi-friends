from typing import List

class Machine:
    """
    A class that represents the identity of a machine. Stores information about which
    ip/port the machine is listening on and what machines it connects to.
    """

    def __init__(
        self,
        id: int,
        ip: str,
        client_tcp_port: int,
        client_udp_port: int,
        internal_port: int,
        heart_port: int
    ) -> None:
        self.id = id
        self.ip = ip
        self.client_tcp_port = client_tcp_port
        self.client_udp_port = client_udp_port
        self.internal_port = internal_port
        self.heart_port = heart_port


MACHINE_ZERO = Machine(
    id=0,
    # ip="localhost",
    ip="10.250.0.195",
    client_tcp_port=26201,
    client_udp_port=26202,
    internal_port=26203,
    heart_port=26204,
)

MACHINE_ONE = Machine(
    id=1,
    # ip="localhost",
    ip="10.250.0.195",
    client_tcp_port=26211,
    client_udp_port=26212,
    internal_port=26213,
    heart_port=26214,
)

# MACHINE_TWO = Machine(
#     id=2,
#     ip="localhost",
#     # ip="10.250.0.195",
#     client_tcp_port=26221,
#     client_udp_port=26222,
#     internal_port=26223,
#     heart_port=26224,
# )

# Create a mapping from machine name to information about it
# MACHINES = [MACHINE_ZERO, MACHINE_ONE, MACHINE_TWO]
MACHINES = [MACHINE_ZERO, MACHINE_ONE]

def get_other_machines(id: int) -> List[Machine]:
    """
    Returns a list of all the machines that are not the machine with the given id.
    """
    return [machine for machine in MACHINES if machine.id != id]

def get_other_machines_ids(id: int) -> dict:
    return {key: None for key in get_other_machines(id)}
