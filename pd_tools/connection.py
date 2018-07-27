import logging
import os
import random
import socket
import time
import re

import pdPythonLib

from .wrapper import wrap

__all__ = ['connect', 'PDApp']
logger = logging.getLogger(__name__)

testpat = re.compile(r""".*""", re.X | re.M | re.S)
retmsgpat = re.compile(r"""
        \ARETVAL:(?P<body>.*)\n\x00\Z""", re.X | re.M | re.S)
retlinepat = re.compile(r"""
        \A(?:\s*(?P<first>\S+))
        \s*(?P<second>\S+)?\Z""", re.X)
listlabelpat = re.compile(r"""
        \A(?P<label>[^[\]]+)
        \[(?P<idx1>\d+)\]
        (?:\[(?P<idx2>\d+)\])?\Z""",re.X)

# monkey patch InterpretString3 method
def InterpretString3(recmsg):
    """Monkey patch for original method

    Structure of return values is 'RETVAL:' followed by, any of:
    a) a single value to be converted to number or string, or
    b) a list of values separated by newlines and representing a 1d (or 2d)
    matrix to be returned as a native python list (of lists) of numbers or
    strings, or
    c) a help message, error, or other string value, to be returned as a
    string.

    If a matrix, each line represents a single value of the matrix. Each line
    consists of some whitespace, followed by an identifier indicating the
    position of the element within the matrix, followed by whitespace, followed
    by the value of the element. The value is sometimes empty in the case of a
    list of objects, in which case we return the identifying label as a string
    within the python list.
    """
    logger.debug('return value: %s', repr(recmsg))

    # match the body of the message
    m = retmsgpat.match(recmsg)
    assert m

    gd1 = m.groupdict()
    body = gd1['body']

    # split the body into lines and check the first line
    lines = re.split(r'\n', body)
    firstline = lines[0]
    m = retlinepat.match(firstline)
    if not m:
        # not matrix
        return pdPythonLib.getNumOrStr(body)

    # check the first argument of the first line
    gd2 = m.groupdict()
    firstarg = gd2['first']
    m = listlabelpat.match(firstarg)
    if not m:
        # not matrix
        return pdPythonLib.getNumOrStr(body)

    # definitely a matrix
    elements = []

    # a 2d matrix
    gd3 = m.groupdict()
    for line in lines:
        linematch = retlinepat.match(line)
        linedict = linematch.groupdict()

        # value is the second one, if available. Otherwise, just use the string
        # identifier
        if linedict['second']:
            lineval = pdPythonLib.getNumOrStr(linedict['second'])
        else:
            lineval = linedict['first']

        # match indices
        labelmatch = listlabelpat.match(linedict['first'])
        labeldict = labelmatch.groupdict()
        idx1 = int(labeldict['idx1'])
        if labeldict['idx2']:
            idx2 = int(labeldict['idx2'])
            # 2d matrix
            if idx1 > len(elements):
                elements.append([])
                assert len(elements) == idx1

            elements[idx1-1].append(lineval)
            assert len(elements[idx1-1]) == idx2
        else:
            # 1d matrix
            elements.append(lineval)
            assert len(elements) == idx1
    return elements
pdPythonLib.InterpretString3 = InterpretString3

complexpat = re.compile(
    r'\s*\((?P<realpart>[^(,)]*),(?P<imagpart>[^(,)]*)\)\s*')
realpat = re.compile(
    r'\s*(?P<realpart>.*)\s*') # note, '.' does not match line breaks by default

def getNumOrStr(msgstr):
    """Monkey patch for the original method

    Don't use string indexing, because that leads to indexing errors. And don't
    assume that all numeric values are newline terminated, because that's
    also fragile."""
    cmatch = complexpat.match(msgstr);

    # Test if complex
    if cmatch:
        cdict = cmatch.groupdict()
        try:
            return float(cdict['realpart']) + 1j*float(cdict['imagpart'])
        except:
            return msgstr
    rmatch = realpat.match(msgstr);
    if rmatch:
        rdict = rmatch.groupdict()
        try:
            return float(rdict['realpart'])
        except:
            return msgstr
    return msgstr
pdPythonLib.getNumOrStr = getNumOrStr

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
        self.refcount = 0

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
            for i in range(8):
                try:
                    appSock = socket.create_connection((host, port))
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

    def ref(self, cmd):
        """calls the command, but creates a ref of the output.

        calls the command and creates a reference. then wraps that reference
        and returns the wrapped thing"""

        refname = "xx{idx}".format(idx=self.refcount)
        self.refcount += 1

        self.do("Ref& {r}={cmd}".format(r=refname, cmd=cmd))
        return wrap(self, refname)

    def set(self, cmd):
        refname = "xx{idx}".format(idx=self.refcount)
        self.refcount += 1

        self.do("Set {r}={cmd}".format(r=refname, cmd=cmd))
        return wrap(self, refname)

    def do(self, cmd):
        if self.batch:
            logger.debug('batch cmd: %s', repr(cmd))
            return self.AddCmd(cmd)
        else:
            logger.debug('exec cmd: %s', repr(cmd))
            return self.Exec(cmd)

    def do_raise(self, cmd):
        if self.batch:
            raise ValueError('batch mode is ON')
        else:
            logger.debug('exec cmd: %s', repr(cmd))
            return self.Exec(cmd)

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
