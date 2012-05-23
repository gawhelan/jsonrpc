import json

import rpc


ERRORS = {
    rpc.ParseError: {'code': -32700, 'message': 'Parse Error'},
    rpc.InvalidRequestError: {'code': -32600, 'message': 'Invalid Request'},
    rpc.MethodNotFoundError: {'code': -32601, 'message': 'Method not found'},
    rpc.InvalidParamsError: {'code': -32602, 'message': 'Invalid params'},
    rpc.InternalError: {'code': -32603, 'message': 'Internal error'},
}


EXCEPTIONS = {
    -32700: rpc.ParseError,
    -32600: rpc.InvalidRequestError,
    -32601: rpc.MethodNotFoundError,
    -32602: rpc.InvalidParamsError,
    -32603: rpc.InternalError,
}


class JSONSerializer(rpc.Serializer):
    """A JSON serializer"""

    def encode(self, data):
        try:
            return json.dumps(data)
        except ValueError as e:
            raise rpc.ParseError(str(e))

    def decode(self, data):
        try:
            return json.loads(data)
        except ValueError as e:
            raise rpc.ParseError(str(e))


class JSONRPCProtocol(rpc.Protocol):
    """Implementation of the JSON-RPC 2.0 spec."""

    def __init__(self):
        rpc.Protocol.__init__(self, serializer=JSONSerializer())

    def marshall_request(self, method, *args, **kwargs):
        """Create a string representing a JSON-RPC request."""
        # "jsonrpc" and "method" members are required
        req = {'jsonrpc': '2.0', 'method': method}

        # Cannot use positional and keyword arguments
        if args and kwargs:
            raise rpc.ProtocolError('Cannot use both positional and '
                                    'keyword arguments')
        # don't use "params" if there are no arguments
        elif args or kwargs:
            req['params'] = args or kwargs

        # TODO: how to handle request ids?
        req['id'] = 0

        # return the serialized data
        return self.serializer.encode(req)

    def unmarshall_request(self, data):
        """Extract a JSON-RPC request from a data string."""
        request = self.serializer.decode(data)

        # must contain "jsonrpc" member with value "2.0"
        try:
            if request['jsonrpc'] != '2.0':
                raise rpc.InvalidRequestError('Only JSON-RPC 2.0 is supported')
        except KeyError:
            raise rpc.InvalidRequestError('No "jsonrpc" member found')

        # must contain "method" member with a string value
        try:
            method = request['method']
            if not (isinstance(method, unicode) or isinstance(method, str)):
                raise rpc.InvalidRequestError('"method" member must be string')
        except KeyError:
            raise rpc.InvalidRequestError('No "method" member found')

        # look for positional or keyword arguments
        args, kwargs = request.get('params', ()), {}
        if isinstance(args, dict):
            args, kwargs = (), args
            # workaround for Python Issue4978, keywords must be str
            kwargs = dict((str(k), v) for k, v in kwargs.items())

        return request, method, args, kwargs

    def marshall_response(self, request, result=None, error=None):
        """Create a string representing a JSON-RPC response"""
        # don't respond to notifications
        if request and 'id' not in request:
            return

        # must contain "jsonrpc" member with a value of "2.0"
        resp = {'jsonrpc': '2.0'}
        # must contain "id" member with same value as request
        # or null if the request was invalid
        resp['id'] = request['id'] if request else None

        # "result" and "error" members are mutually exclusive
        if error is not None:
            resp['error'] = self.marshall_error(error)
        else:
            resp['result'] = result

        return self.serializer.encode(resp)

    def unmarshall_response(self, data):
        """Extract a JSON-RPC response from a data string."""
        response = self.serializer.decode(data)

        # must contain "jsonrpc" member with value "2.0"
        try:
            if response['jsonrpc'] != '2.0':
                raise rpc.InvalidResponseError('Only JSON-RPC 2.0 supported')
        except KeyError:
            raise rpc.InvalidResponseError('No "jsonrpc" member in response')

        # "id" member is required
        if 'id' not in response:
            raise rpc.InvalidResponseError('No "id" member found in response')

        # if an error occured, raise the appropriate exception
        if 'error' in response:
            raise self.unmarshall_error(response['error'])
        # if we got a result, return it
        elif 'result' in response:
            return response, response['result']
        # an "error" or "result" member is required
        else:
            raise rpc.InvalidResponseError('No "result" or "error" member '
                                           'found in response')

    def marshall_error(self, exc):
        try:
            error = ERRORS[type(exc)]
            error['data'] = exc.args or None
            return error
        except KeyError:
            return None

    def unmarshall_error(self, error):
        try:
            code = error['code']
            message = '%s: %s' % (error['message'], error['data'])
            return EXCEPTIONS[code](message)
        except KeyError:
            return None


class TCPServer(rpc.TCPServer):

    def __init__(self, address):
        rpc.TCPServer.__init__(self, address, protocol=JSONRPCProtocol)


class TCPServerProxy(rpc.TCPServerProxy):

    def __init__(self, address):
        rpc.TCPServerProxy.__init__(self, address, protocol=JSONRPCProtocol)


if __name__ == '__main__':
    print 'Runnning JSON-RPC server on port 8000'
    s = TCPServer(('localhost', 8000))
    s.register_function(pow)
    s.register_function(lambda x, y: x + y, 'add')
    s.serve_forever()
