import socket
from contextlib import contextmanager


@contextmanager
def open_socket(address, family=socket.AF_INET, type=socket.SOCK_STREAM):
    """A basic context manager for sockets."""
    sock = socket.socket(family, type)
    sock.connect(address)
    yield sock
    sock.close()


def socket_recv(sock, bufsize):
    """Read data from a socket.

    Raises a socket.error if the socket is closed.
    """
    data = sock.recv(bufsize)
    if not data:
        raise socket.error
    return data


def socket_read(sock, bufsize=4096):
    """Read all the data available on the socket"""
    data = socket_recv(sock, bufsize)
    timeout = sock.gettimeout()
    sock.settimeout(0.0)

    while True:
        try:
            data += socket_recv(sock, bufsize)
        except socket.error:
            break

    sock.settimeout(timeout)
    return data
