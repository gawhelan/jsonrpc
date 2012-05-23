import SocketServer

from util import open_socket, socket_read


class Error(Exception):
    """A base class for all RPC errors"""
    pass


class ParseError(Error):
    pass


class InvalidRequestError(Error):
    pass


class MethodNotFoundError(Error):
    pass


class InvalidParamsError(Error):
    pass


class InvalidResponseError(Error):
    pass


class ProtocolError(Error):
    pass


class InternalError(Error):
    pass


class Serializer(object):
    """A base class for data serializers"""

    def encode(self, data):
        """Serialize an object."""
        raise NotImplementedError

    def decode(self, data):
        """Deserialize some data"""
        raise NotImplementedError


class Protocol(object):
    """A base class for defining RPC protocols."""

    def __init__(self, serializer):
        """Initialize the Protocol specifying the serialization format.

        Arguments:
        serializer -- a Serializer object to use for
                      encoding/decoding data

        """
        self.serializer = serializer

    def marshall_request(self, method, *args, **kwargs):
        """Create and serialize an RPC request."""
        raise NotImplementedError

    def unmarshall_request(self, data):
        """Deserialize and validate an RPC request."""
        raise NotImplementedError

    def marshall_response(self, request, result, error):
        """Create and serialize an RPC response."""
        raise NotImplementedError

    def unmarshall_response(self, data):
        """Deserialize and validate an RPC response"""
        raise NotImplementedError


class Dispatcher(object):
    """A base class for RPC method dispatchers."""

    def __init__(self):
        self.funcs = {}

    def register_function(self, function, name=None):
        """Register a function."""
        self.funcs[name or function.__name__] = function

    def dispatch(self, method, *args, **kwargs):
        """Invoke the named function."""
        try:
            func = self.funcs[method]
        except KeyError:
            raise rpc.MethodNotFoundError(method)

        try:
            return func(*args, **kwargs)
        except TypeError as e:
            raise InvalidParamsError(str(e))
        except Exception as e:
            raise InternalError(str(e))


class TCPRequestHandler(SocketServer.BaseRequestHandler):

    def handle(self):
        data = socket_read(self.request)
        request = result = error = None
        try:
            request, method, args, kwargs = \
                                self.server.protocol.unmarshall_request(data)
            result = self.server.dispatcher.dispatch(method, *args, **kwargs)
        except Error as e:
            error = e

        response = self.server.protocol.marshall_response(request,
                                                          result,
                                                          error)

        if response:
            self.request.send(response)


class TCPServer(SocketServer.TCPServer):
    allow_reuse_address = True

    def __init__(self, address, protocol, request_handler=TCPRequestHandler):
        SocketServer.TCPServer.__init__(self, address, request_handler)
        self.protocol = protocol()
        self.dispatcher = Dispatcher()

    def register_function(self, function, name=None):
        self.dispatcher.register_function(function, name)


class Transport(object):

    def __init__(self, address):
        self.address = address

    def send_request(self, data):
        raise NotImplementedError


class TCPSocketTransport(Transport):

    def send_request(self, data):
        with open_socket(self.address) as sock:
            sock.send(data)
            return socket_read(sock)


class _FunctionProxy(object):

    def __init__(self, remote_call, name):
        self.__remote_call = remote_call
        self.__name = name

    def __call__(self, *args, **kwargs):
        return self.__remote_call(self.__name, *args, **kwargs)


class ServerProxy(object):

    def __init__(self, address, transport, protocol):
        self._transport = transport(address)
        self._protocol = protocol()

    def __getattr__(self, name):
        return _FunctionProxy(self.__remote_call, name)

    def __remote_call(self, name, *args, **kwargs):
        request = self._protocol.marshall_request(name, *args, **kwargs)
        data = self._transport.send_request(request)
        if data:
            response, result = self._protocol.unmarshall_response(data)
            return result


class TCPServerProxy(ServerProxy):

    def __init__(self, address, protocol):
        ServerProxy.__init__(self, address,
                             transport=TCPSocketTransport,
                             protocol=protocol)
