import re
import threading
from _thread import *
from typing import NewType

Response = NewType('response', tuple[int, str, str])

class Operation:
    def __init__(self, op, filename):
        self.op = op
        self.filename = filename

class User:
    """
    A class used to handling user state information.
    ...

    Attributes
    ----------
    conn :
        socket for the current user

    username : str
        username of the current user logged-in account

    Methods
    -------
    get_conn()
        Gets the socket connection

    get_name()
        Gets the username of the current account

    set_name(username=None)
        Sets the username of the current account
    """

    def __init__(self, conn, username: str = "", gen_number=0):
        self.conn = conn
        self.gen_number = gen_number
        self.username = username

    def get_conn(self):
        return self.conn

    def get_id(self):
        return int(self.username)

    def get_gen_number(self):
        return int(self.gen_number)

    def set_name(self, username: str = ""):
        self.username = username

    def stringify(self):
        return f"{self.conn}, {self.username}"


