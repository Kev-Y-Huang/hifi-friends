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
