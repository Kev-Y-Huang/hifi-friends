import logging
import queue
import select
import socket
import threading
from enum import Enum

class Operation(Enum):
    """
    Enum for the different types of operations that can be performed.
    """
    CLOSE = 0
    UPLOAD = 1
    QUEUE = 2
    LIST = 3
    QUEUED = 4
    PAUSE = 5
    PLAY = 6
    SKIP = 7
    PING = 8

class ServerOperation(Enum):
    """
    Enum for different types of operations that can be sent between servers.
    """
    UPLOAD = 0
    PREPARE = 1
    PROMISE = 2
    ACCEPT = 3
    ACCEPT_RESPONSE = 4

class Update(Enum):
    """
    Enum for the different types of events that can occur.
    """
    PING = 0
    PAUSE = 1
    PLAY = 2
    SKIP = 3

class Message(Enum):
    """
    Enum for the different types of messages that can be sent from the server.
    """
    PRINT = 0
    QUEUE = 1
    DONE_UPLOADING = 2


def setup_logger(level: int = logging.INFO) -> logging.Logger:
    """
    Setup the logger for the machine process.
    ...

    Parameters
    ----------
    name : str
        The name of the logger.
    level : int
        The level of logging to record.

    Returns
    -------
    logging.Logger
        The logger object.

    """
    logger = logging.getLogger()
    formatter = logging.Formatter('%(asctime)s : %(message)s')

    # Set up the stream handler for printing to the console
    streamHandler = logging.StreamHandler()
    streamHandler.setFormatter(formatter)

    logger.setLevel(level)
    logger.addHandler(streamHandler)

    return logger


class read_from_q:
    def __init__(self, q: queue.Queue, block=False, timeout=None):
        """
        Context manager for reading from a queue.
        ...

        Parameters
        ----------
        q : Queue.Queue
            The queue to read from.
        block : bool
            Whether to block until an item is available.
        timeout : int
            The timeout for blocking.
        """
        self.q = q
        self.block = block
        self.timeout = timeout

    def __enter__(self):
        return self.q.get(self.block, self.timeout)

    def __exit__(self, _type, _value, _traceback):
        self.q.task_done()


def queue_rows(q: queue.Queue, block: bool = False, timeout: int = None):
    """
    Generator that yields rows from a queue.
    ...

    Parameters
    ----------
    q : Queue.Queue
        The queue to read from.
    block : bool
        Whether to block until an item is available.
    timeout : int
        The timeout for blocking.

    Yields
    ------
    list
        A row from the queue.
    """
    while not q.empty():
        with read_from_q(q, block, timeout) as row:
            yield row


def poll_read_sock_no_exit(inputs: list, exit: threading.Event, timeout=0.1):
    """
    Generator that polls the read sockets while the exit event is not set.
    ...

    Parameters
    ----------
    inputs : list
        The list of sockets to poll.
    exit : threading.Event()
        The event to check for exiting.
    timeout : float
        The timeout for the select call.

    Yields
    ------
    socket.socket
        A socket that is ready to be read from.
    """
    while not exit.is_set():
        read_sockets, _, _ = select.select(inputs, [], [], timeout)
        for sock in read_sockets:
            if not exit.is_set():
                yield sock


def send_to_all_addrs(sock: socket.socket, addrs: list, data: bytes):
    """
    Send data to all UDP addresses.
    ...

    Parameters
    ----------
    sock : socket.socket
        The socket to send from.
    addrs : list
        The list of addresses to send to.
    data : bytes
        The data to send.
    """
    for addr in addrs:
        sock.sendto(data, addr)