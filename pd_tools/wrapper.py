"""
A wrapper for the fimmwave scripting language.

Script in python like it was the fimmwave command prompt! Proxies all
accessors, function calls and assignment to fimmwave via variety of magic
methods
"""
import re
import logging
logger = logging.getLogger(__name__)

__all__ = ['wrap']

_linepat = re.compile(r"""
            \s*?(?:(?P<name>\S+)\s+)? # the name
            (?P<nodetype>\S+) # the type
            (?:\s+-)? # optional hyphen
            (?:\s+\(.*?\):)? # optional function arguments
            (?P<description>\s+.*)? # the description
            """, re.X)


_cls_cache = {}
_cls_types = set()

def wrap(pd_app, path='app'):
    return _get_node(pd_app, path)


def _get_node(pd_app, path):

    if path not in _cls_cache:
        _create_node_class(pd_app, path)
    cls = _cls_cache[path]
    return cls()


def _create_node_class(pd_app, path):
    info = _parse_help(_get_help(pd_app, path))
    nodetype = info['matchdict']['nodetype']

    attrs = {
        attribute['name']: Attribute(attribute['name'], attribute['nodetype'])
        for attribute in info['attributes']
    }

    attrs['_pd_app'] = pd_app
    attrs['_path'] = path
    attrs['_nodetype'] = nodetype

    cls = type(nodetype, (Node,), attrs)

    assert path not in _cls_cache
    if nodetype not in _cls_types:
        _cls_types.add(nodetype)
        logger.debug('adding type %s' % nodetype)

    _cls_cache[path] = cls


def _join_path(path, attrname):
    return '{path}.{name}'.format(path=path, name=attrname)


def _get_help(pd_app, nodepath):
    """returns the help string for a given node"""
    return pd_app.Exec('help {nodepath}'.format(nodepath=nodepath))


def _parse_help(helpstr):
    if helpstr.startswith('ERROR'):
        raise ValueError(helpstr)
    lines = helpstr.split('\n')

    # match the first line
    match = _linepat.match(lines[0])
    assert match is not None, \
        'first line no match: %s' % lines[0]

    # get a list of child attribute names
    atts = [
        _linepat.match(line).groupdict(None)
        for line in lines[2:]
    ] if len(lines) > 2 else []

    rval = {}
    rval['matchdict'] = match.groupdict(None)
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
            return instance._pd_app.Exec(path)
        else:
            if not hasattr(self, '_cached_node'):
                self._cached_node = _get_node(instance._pd_app, path)
            return self._cached_node

    def __set__(self, instance, value):
        if self.nodetype in Node.PRIMITIVE_TYPES:
            return instance._pd_app.Exec('{path}={value}'.format(
                path=_join_path(instance._path, self.name),
                value=_convert_arg(value)))
        else:
            raise TypeError('not a primitive: %s' % self)

class Node(object):
    FUNCTION_TYPE = 'FUNCTION'
    LIST_TYPE = 'LIST'
    PRIMITIVE_TYPES = (
        'INTEGER',
        'FLOAT',
        'STRING',
    )

    def __getitem__(self, idx):
        """if we are in a list"""
        if self._nodetype.startswith(self.LIST_TYPE):
            node = _get_node(self._pd_app,
                '{path}[{idx}]'.format(path=self._path, idx=_convert_arg(idx)))
            if node._nodetype in self.PRIMITIVE_TYPES:
                return node.__get__(self)
            else:
                return node
        else:
            raise TypeError('not a list')

    def __len__(self):
        if self._nodetype.startswith(self.LIST_TYPE):
            r = self._pd_app.Exec(self._path)
            if type(r) is str and '<EMPTY>' in r:
                return 0
            elif type(r) is list:
                return len(r)
            else:
                raise TypeError('not a list?')
        else:
            raise TypeError('not a list')

    def __iter__(self):
        for i in range(len(self)):
            yield self[i]

    def __call__(self, *args):
        """callable if a function"""
        if self._nodetype == self.FUNCTION_TYPE:
            arglist = [_convert_arg(arg) for arg in args]

            return self._pd_app.Exec(
                '{path}({args})'
                .format(path=self._path, args=','.join(arglist)))
        else:
            raise TypeError('not a function')

    def help(self):
        print(_get_help(self._pd_app, self._path))

