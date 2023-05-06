import logging
import select
import threading
from enum import Enum

# from wire_protocol import pack_opcode


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


class ActionType(Enum):
    """
    Enum for the different types of events that can occur.
    """
    PING = 0
    PAUSE = 1
    PLAY = 2
    SKIP = 3


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
    def __init__(self, q, block=False, timeout=None):
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


def queue_rows(q, block=False, timeout=None):
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


def poll_read_sock_no_exit(inputs, exit: threading.Event(), timeout=0.1):
    """
    Generator that polls the read sockets while the exit event is not set.
    ...

    Parameters
    ----------
    inputs : list
        The list of sockets to poll.
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
            yield sock


def send_to_all_addrs(sock, addrs, data: bytes):
    """
    Send data to all UDP addresses.
    ...

    Parameters
    ----------
    data : bytes
        The data to send.
    """
    for addr in addrs:
        sock.sendto(data, addr)


# def upload_file(sock, file_path):
#     """
#     Upload a file to the server.
#     ...

#     Parameters
#     ----------
#     file_path : str
#         The path to the file to upload.
#     """
#     sock.send(pack_opcode(5))
#     filename = os.path.basename(file_path)
#     size = len(filename)
#     # encode filename size as 16 bit binary, limit your filename length to 255 bytes
#     size = bin(size)[2:].zfill(16)

#     sock.send(size.encode())
#     sock.send(filename.encode())

#     filesize = os.path.getsize(file_path)
#     # encode filesize as 32 bit binary
#     filesize = bin(filesize)[2:].zfill(32)
#     sock.send(filesize.encode())

#     file_to_send = open(file_path, 'rb')

#     l = file_to_send.read()
#     sock.sendall(l)
#     file_to_send.close()
#     print('File Sent')
