"""
A wrapper for the fimmwave scripting language.

Script in python like it was the fimmwave command prompt! Proxies all
accessors, function calls and assignment to fimmwave via variety of magic
methods
"""
import re
import logging
import sys
logger = logging.getLogger(__name__)

__all__ = ['wrap']

_linepat = re.compile(r"""
            \s*(?P<name>\S+)\s+ # the name
            (?P<nodetype>\S+) # the type
            (?:
                \s+-\s+ # optional hyphen + description
                (?:\(.*?\):\s+)? # optional function args
                (?P<description>.*)
            )?$
            """, re.X)
_typepat = re.compile(r'\s+(?P<nodetype>\S+)')


def wrap(pd_app, path='app'):
    return _get_node(pd_app, path)


def _get_node(pd_app, path):
    if path not in pd_app._cls_cache:
        _create_node_class(pd_app, path)
    cls = pd_app._cls_cache[path]

    if not pd_app.batch and not cls._initialized:
        _init_node_class(cls)

    return cls()


def _create_node_class(pd_app, path):
    attrs = {
        '_pd_app': pd_app,
        '_path': path,
        '_initialized': False,
    }

    cls = type(path, (Node,), attrs)

    assert path not in pd_app._cls_cache
    pd_app._cls_cache[path] = cls

    logger.debug('added %s to cache' % repr(path))


def _init_node_class(cls):
    """initializes the node from its help"""

    assert cls._initialized is False
    cls._initialized = True

    raw_help = _get_help(cls._pd_app, cls._path)
    info = _parse_help(raw_help)
    nodetype = info['matchdict']['nodetype']

    attrs = {
        attribute['name']: Attribute(attribute['name'], attribute['nodetype'])
        for attribute in info['attributes']
    }

    attrs['_nodetype'] = nodetype

    if sys.version_info >= (3,3):
        # docstrings not mutable until Python 3.3
        attrs['__doc__'] = raw_help

    for key, val in attrs.items():
        setattr(cls, key, val)

    logger.debug('initialized %s' % repr(cls._path))

def _join_path(path, attrname):
    return '{path}.{name}'.format(path=path, name=attrname)


def _idx_path(path, idx):
    return '{path}[{idx}]'.format(path=path, idx=_convert_arg(idx))


def _assign_cmd(path, attr, value):
    return '{path}={value}'.format(
        path=_join_path(path, attr), value=_convert_arg(value))


def _call_cmd(path, args):
    arglist = [_convert_arg(arg) for arg in args]
    return '{path}({args})'.format(path=path, args=','.join(arglist))


def _get_help(pd_app, nodepath):
    """returns the help string for a given node"""
    return pd_app.do_raise('help {nodepath}'.format(nodepath=nodepath))


def _parse_help(helpstr):
    logger.debug('parsing string: %s' % repr(helpstr))

    # if it's an error, propagate it up
    if helpstr.startswith('ERROR'):
        raise ValueError(helpstr)
    lines = helpstr.split('\n')

    # match the first line
    match = _linepat.match(lines[0])
    if match is None:
        match = _typepat.match(lines[0])
    assert match is not None, 'first line no match: %s' % lines[0]
    matchdict = match.groupdict(None)
    logger.debug('matched params: %s' % repr(matchdict))

    atts = []
    childlines = lines[2:]
    if len(childlines) > 0:
        assert lines[1] == 'Children:'

        # get a list of child attribute names
        for line in childlines:
            m = _linepat.match(line)
            if m is None:
                logger.warn('discarding line: %s' % repr(line))
                continue

            atts.append(m.groupdict(None))

    rval = {}
    rval['matchdict'] = matchdict
    rval['rawlines'] = lines
    rval['attributes'] = atts
    return rval


def _convert_arg(arg):
    return '%s' % arg if type(arg) is str else repr(arg)


class Attribute(object):
    def __init__(self, name, nodetype):
        self.name = name
        self.nodetype = nodetype

    def __get__(self, instance, owner):
        path = _join_path(instance._path, self.name)

        if self.nodetype in Node.PRIMITIVE_TYPES:
            return instance._pd_app.do_raise(path)
        else:
            if not hasattr(self, '_cached_node'):
                self._cached_node = _get_node(instance._pd_app, path)
            return self._cached_node

    def __set__(self, instance, value):
        if self.nodetype in Node.PRIMITIVE_TYPES:
            return instance._pd_app.do(
                _assign_cmd(instance._path, self.name, value))
        else:
            raise TypeError('not a primitive: %s' % self)

    def __str__(self):
        return '{n}[{t}]'.format(n=self.name, t=self.nodetype)

class Node(object):
    FUNCTION_TYPE = 'FUNCTION'
    LIST_TYPE = 'LIST'
    PRIMITIVE_TYPES = (
        'INTEGER',
        'FLOAT',
        'STRING',
        'MATRIX<COMPLEX>'
    )

    def __getitem__(self, idx):
        """calls get_node. If the node it returns is initialized, do stuff"""
        if self._initialized:
            # initialized, do it
            if self._nodetype.startswith(self.LIST_TYPE):
                node = _get_node(self._pd_app, _idx_path(self._path, idx))
                if node._nodetype in self.PRIMITIVE_TYPES:
                    return node.__get__(self)
                else:
                    return node
            else:
                raise TypeError('not a list')
        elif self._pd_app.batch:
            # not initialized, but batch mode so flying blind
            return _get_node(self._pd_app, _idx_path(self._path, idx))
        else:
            # batch mode is off, but not initialized, so initialize it and try
            # again
            _init_node_class(self.__class__)
            return self[idx]

    def __len__(self):
        """does nothing if batch mode is ON"""
        if self._initialized:
            if self._nodetype.startswith(self.LIST_TYPE):
                r = self._pd_app.do_raise(self._path)
                if type(r) is str and '<EMPTY>' in r:
                    return 0
                elif type(r) is list:
                    return len(r)
                else:
                    raise TypeError('not a list?')
            else:
                raise TypeError('not a list')
        elif self._pd_app.batch:
            raise ValueError('batch mode is ON')
        else:
            _init_node_class(self.__class__)
            return len(self)

    def __getattr__(self, key):
        """does nothing special if this is initialized (delegate to attribute),
        if it is not initialized and batch mode OFF, initialize, then delegate.
        otherwise calls _get_node for a child attribute"""
        if self._initialized:
            object.__getattribute__(self, key)
        elif self._pd_app.batch:
            return _get_node(self._pd_app, _join_path(self._path, key))
        else:
            _init_node_class(self.__class__)
            return getattr(self, key)

    def __setattr__(self, key, value):
        """if this instance is initialized, do nothing special (delegate to
        attribute). if not initialized, add cmd"""
        if self._initialized:
            object.__setattr__(self, key, value)
        elif self._pd_app.batch:
            self._pd_app.do(_assign_cmd(self._path, key, value))
        else:
            _init_node_class(self.__class__)
            setattr(self, key, value)

    def __iter__(self):
        for i in range(1,len(self)+1):
            yield self[i]

    def __call__(self, *args, **kwargs):
        """if initialized, callable. if not initialized, still callable
        (without checks)"""
        get_set = kwargs.get('get_set', None)
        get_ref = kwargs.get('get_ref', None)
        if self._initialized and self._nodetype != self.FUNCTION_TYPE:
            raise TypeError('not a function')
        elif (
                self._initialized and self._nodetype == self.FUNCTION_TYPE
                or
                self._pd_app.batch):
            cmd = _call_cmd(self._path, args)
            if get_ref:
                return self._pd_app.ref(cmd)
            elif get_set:
                return self._pd_app.set(cmd)
            else:
                return self._pd_app.do(cmd)
        else:
            _init_node_class(self.__class__)
            return self(*args)

    def __str__(self):
        return '{path}[{nodetype}]'.format(
            path=self._path, nodetype=self._nodetype)

    def __repr__(self):
        return '<Node {path}[{nodetype}]>'.format(
            path=self._path, nodetype=self._nodetype)

    def help(self):
        print(_get_help(self._pd_app, self._path))
