import logging


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
         :param Queue.Queue q:
         :param bool block:
         :param timeout:
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
     :param Queue.Queue q:
     :param bool block:
     :param int timeout:
    """
    while not q.empty():
        with read_from_q(q, block, timeout) as row:
            yield row