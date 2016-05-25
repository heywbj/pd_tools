import logging
import os
import random
import socket
import time

import pdPythonLib

from .wrapper import wrap

__all__ = ['connect', 'PDApp']
logger = logging.getLogger(__name__)

def start(path, port=None):

    connection = PDApp()
    connection.start(path, port)

    app = wrap(connection, 'app')
    return connection, app

def connect(host, port):
    connection = PDApp()
    connection.connect(host, port)

    app = wrap(connection, 'app')
    return connection, app

class PDApp(pdPythonLib.pdApp):
    """remedies some minor stuffs

    - add support for 'with' statement.
    - alias methods to a more pythonic naming scheme
    - bypasses hairbrained port management
    """

    ports_in_use = set()

    def __init__(self, path=None, host=None, port=None, batch=False):
        # inheriting from old style class requires explicit call to __init__
        pdPythonLib.pdApp.__init__(self)

        self.host = host
        self.path = path
        self.port = port
        self.batch = batch

    def __enter__(self):
        """Connect to fimmwave"""
        if self.path:
            if self.host and self.host != 'localhost':
                raise ValueError('do not provide both path and host')
            self.start(self.path, self.port)
        elif self.host:
            self.connect(self.host, self.port)
        else:
            raise ValueError('neither host nor path provided')

        return wrap(self, 'app')

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Destroy the connection so someone else can connect on the port"""
        if self.batch:
            self.flush()
        self.disconnect()

    def __del__(self):
        self.disconnect()

    def CleanUpPort(self):
        raise NotImplementedError

    def ConnectToApp(self, hostname='localhost', portNo=5101):
        return self.connect(hostname, portNo)

    def ConnectToApp1(self, *args, **kwargs):
        raise NotImplementedError

    def StartApp(self, path, portNo=5101):
        self.start(path, portNo)

    def start(self, path, port):
        if port is None:
            port = random.randrange(5000,6000)

        # Determine the drive letter, attempt to switch to that drive
        a = path.rfind("\\")
        if (a!=-1):
            if (path[0:a]==''):
                os.chdir("\\")
            else:
                os.chdir(path[0:a])
        os.spawnv(os.P_DETACH,path,[path,"-pt",repr(port)])

        self.connect('localhost', port)

    def connect(self, host, port):
        self._cls_cache = {}

        if self.appSock:
            raise ValueError('already connected')

        if port in self.ports_in_use:
            raise ValueError('port %s in use' % port)
        else:
            appSock = None
            for i in range(5):
                try:
                    appSock = socket.create_connection((host, port), 5)
                    break
                except:
                    time.sleep(1)
                    logger.debug('connection failed, retrying...')
            if appSock:
                self.appSock = appSock
                self.ports_in_use.add(port)
                self._port = port
            else:
                logger.error('failed to connect')


    def disconnect(self):
        if self.cmdList:
            logger.warn('there are pending commands')

        if self.appSock is not None:
            self.appSock.close()
            self.appSock = None
            self.ports_in_use.remove(self._port)

    def do(self, *args):
        if self.batch:
            logger.debug('batch cmd: %s', repr(args))
            return self.AddCmd(*args)
        else:
            logger.debug('exec cmd: %s', repr(args))
            return self.Exec(*args)

    def do_raise(self, *args):
        if self.batch:
            raise ValueError('batch mode is ON')
        else:
            logger.debug('exec cmd: %s', repr(args))
            return self.Exec(*args)

    def toggle_mode(self):
        if self.batch:
            self.flush()

        self.batch = not self.batch

    def flush(self):
        if self.batch:
            logger.debug('flushing batched commands')
            return self.Exec('app') # 'app' is a dummy value
        else:
            raise ValueError('batch mode is OFF')
