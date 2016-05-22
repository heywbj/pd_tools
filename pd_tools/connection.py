import os
import socket

import pdPythonLib

from .wrapper import wrap

__all__ = ['connect', 'PDApp']

def connect(*args, **kwargs):
    connection = PDApp(*args, **kwargs)
    connection.connect()

    app = wrap(connection, 'app')

    return connection, app

class PDApp(pdPythonLib.pdApp):
    """remedies some minor stuffs

    - add support for 'with' statement.
    - alias methods to a more pythonic naming scheme
    - bypasses hairbrained port management
    """

    ports_in_use = set()

    def __init__(self, *conn_args, **conn_kwargs):
        # inheriting from old style class requires explicit call to __init__
        pdPythonLib.pdApp.__init__(self)
        self.conn_args = conn_args
        self.conn_kwargs = conn_kwargs

    def __enter__(self):
        """Connect to fimmwave"""
        self.connect(**self.conn_kwargs)
        return wrap(self, 'app')

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Destroy the connection so someone else can connect on the port"""
        self.disconnect()

    def __del__(self):
        self.disconnect()

    def CleanUpPort(self):
        raise NotImplementedError

    def ConnectToApp(self, hostname='localhost', portNo=5101):
        return self.connect(hostname, portNo)

    def ConnectToApp1(self, *args, **kwargs):
        raise NotImplementedError

    def StartApp(self, path, port):
        # Determine the drive letter, attempt to switch to that drive
        a = rfind(path,"\\")
        if (a!=-1):
            if (path[0:a]==''):
                os.chdir("\\")
            else:
                os.chdir(path[0:a])
        os.spawnv(os.P_DETACH,path,[path,"-pt",repr(portNo)])

    def connect(self, *args, **kwargs):
        if args or kwargs:
            self._connect(*args, **kwargs)
        else:
            self._connect(*self.conn_args, **self.conn_kwargs)

    def _connect(self, hostname='localhost', port=5101, timeout=10.0):
        if self.appSock:
            raise ValueError('already connected')

        if port in self.ports_in_use:
            raise ValueError('port %s in use' % port)
        else:
            self.appSock = socket.create_connection((hostname, port), timeout)
            self.ports_in_use.add(port)
            self._port = port

    def disconnect(self):
        if self.appSock is not None:
            self.appSock.close()
            self.appSock = None
            self.ports_in_use.remove(self._port)

    def exc(self, *args):
        return self.Exec(*args)

    def add(self, *args):
        return self.AddCmd(*args)

