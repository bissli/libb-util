import logging
from abc import ABCMeta
from collections.abc import Mapping, MutableMapping, MutableSet

logger = logging.getLogger(__name__)


class OrderedSet(MutableSet):
    """From Raymond Hettinger on ActiveState
    https://code.activestate.com/recipes/576694/

    >>> s = OrderedSet('abracadaba')
    >>> t = OrderedSet('simsalabim')
    >>> (s | t)
    OrderedSet(['a', 'b', 'r', 'c', 'd', 's', 'i', 'm', 'l'])
    >>> (s & t)
    OrderedSet(['a', 'b'])
    >>> (s - t)
    OrderedSet(['r', 'c', 'd'])
    """

    def __init__(self, iterable=None):
        self.end = end = []
        end += [None, end, end]         # sentinel node for doubly linked list
        self.map = {}                   # key --> [key, prev, next]
        if iterable is not None:
            self |= iterable

    def __len__(self):
        return len(self.map)

    def __contains__(self, key):
        return key in self.map

    def add(self, key):
        if key not in self.map:
            end = self.end
            curr = end[1]
            curr[2] = end[1] = self.map[key] = [key, curr, end]

    def discard(self, key):
        if key in self.map:
            key, prev, next = self.map.pop(key)
            prev[2] = next
            next[1] = prev

    def __iter__(self):
        end = self.end
        curr = end[2]
        while curr is not end:
            yield curr[0]
            curr = curr[2]

    def __reversed__(self):
        end = self.end
        curr = end[1]
        while curr is not end:
            yield curr[0]
            curr = curr[1]

    def pop(self, last=True):
        if not self:
            raise KeyError('set is empty')
        key = self.end[1][0] if last else self.end[2][0]
        self.discard(key)
        return key

    def __repr__(self):
        if not self:
            return '%s()' % (self.__class__.__name__,)
        return '%s(%r)' % (self.__class__.__name__, list(self))

    def __eq__(self, other):
        if isinstance(other, OrderedSet):
            return len(self) == len(other) and list(self) == list(other)
        return set(self) == set(other)


# Dictionary Collections


class attrdict(dict):
    """The vanilla attrdict everyone has in their utils

    >>> import copy
    >>> d = attrdict(x=10, y='foo')
    >>> d.x
    10
    >>> d['x']
    10
    >>> d.y = 'baa'
    >>> d['y']
    'baa'
    >>> g = d.copy()
    >>> g.x = 11
    >>> d.x
    10
    >>> d.z = 1
    >>> d.z
    1
    >>> tricky = [d, g]
    >>> tricky2 = copy.copy(tricky)
    >>> tricky2[1].x
    11
    >>> tricky2[1].x = 12
    >>> tricky[1].x
    12
    >>> righty = copy.deepcopy(tricky)
    >>> righty[1].x
    12
    >>> righty[1].x = 13
    >>> tricky[1].x
    12

    Handles obj.get('attr'), obj['attr'], and obj.attr
    >>> class A(attrdict):
    ...     @property
    ...     def x(self):
    ...         return 1
    >>> a = A()
    >>> a['x'] == a.x == a.get('x')
    True
    >>> a.get('b')
    >>> a['b'] # doctest: +ELLIPSIS
    Traceback (most recent call last):
        ...
    KeyError: 'b'
    >>> a.b # doctest: +ELLIPSIS
    Traceback (most recent call last):
        ...
    AttributeError: b
    """

    __slots__ = ()

    def __getattr__(self, attrname):
        if attrname not in self:
            raise AttributeError(attrname)
        return self[attrname]

    def __setattr__(self, attrname, attrval):
        if isinstance(attrval, ABCMeta):
            dict.__setattr__(self, attrname, attrval)
        else:
            self[attrname] = attrval

    def __delattr__(self, attrname):
        if attrname not in self:
            raise AttributeError(attrname)
        self.pop(attrname)

    def __getitem__(self, attrname):
        if attrname in self:
            return dict.__getitem__(self, attrname)
        if hasattr(self, attrname):
            return dict.__getattribute__(self, attrname)
        raise KeyError(attrname)

    def get(self, key, default=None):
        try:
            return self.__getitem__(key)
        except KeyError:
            return default

    def update(self, *args, **kwargs):
        dict.update(self, *args, **kwargs)
        return self

    def copy(self, **kwargs):
        newdict = attrdict(dict.copy(self))
        return newdict.update(**kwargs)


class lazydict(attrdict):
    """Attrdict where functions get stored as lazy calculations

    >>> a = lazydict(a=1, b=2, c=lambda x: x.a+x.b)
    >>> a.c
    3
    >>> a.a = 99
    >>> a.c
    101
    >>> a.z = 1
    >>> a.z
    1

    make sure we dont share descriptors, could cause awful bugs
    >>> z = lazydict(a=2, y=4, f=lambda x: x.a*x.y)
    >>> z.b
    Traceback (most recent call last):
        ...
    AttributeError: b
    >>> z.c
    Traceback (most recent call last):
        ...
    AttributeError: c
    >>> z.f
    8

    a's attrs should be unaffected
    >>> a.f
    Traceback (most recent call last):
        ...
    AttributeError: f
    """

    def __getattr__(self, attrname):
        if attrname not in self:
            raise AttributeError(attrname)
        attrval = self[attrname]
        if callable(attrval):
            return attrval(self)
        return attrval


class emptydict(attrdict):
    """Attrdict where non-existing fields return None silently

    >>> a = emptydict(a=1, b=2)
    >>> a.c == None
    True
    """

    def __getattr__(self, attrname):
        if attrname not in self:
            return None
        return self.get(attrname, None)

    def __getitem__(self, attrname):
        return self.__getattr__(attrname)


class bidict(dict):
    """Bidirectional dictionary that allows multiple keys with same value

    >>> bd = bidict({'a': 1, 'b': 2})
    >>> bd
    {'a': 1, 'b': 2}
    >>> bd.inverse
    {1: ['a'], 2: ['b']}

    two keys can have the same value (= 1)
    >>> bd['c'] = 1
    >>> bd
    {'a': 1, 'b': 2, 'c': 1}
    >>> bd.inverse
    {1: ['a', 'c'], 2: ['b']}

    remove a key
    >>> del bd['c']
    >>> bd
    {'a': 1, 'b': 2}
    >>> bd.inverse
    {1: ['a'], 2: ['b']}
    >>> del bd['a']
    >>> bd
    {'b': 2}
    >>> bd.inverse
    {2: ['b']}

    set key to new value
    >>> bd['b'] = 3
    >>> bd
    {'b': 3}
    >>> bd.inverse
    {2: [], 3: ['b']}
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.inverse = {}
        for key, value in list(self.items()):
            self.inverse.setdefault(value, []).append(key)

    def __setitem__(self, key, value):
        if key in self:
            self.inverse[self[key]].remove(key)
        super().__setitem__(key, value)
        self.inverse.setdefault(value, []).append(key)

    def __delitem__(self, key):
        self.inverse.setdefault(self[key], []).remove(key)
        if self[key] in self.inverse and not self.inverse[self[key]]:
            del self.inverse[self[key]]
        super().__delitem__(key)


class MutableDict(dict):
    """Extends dictionary to include insert_before and insert_after methods.
    Since python3.7 dictionaries keep insert order.
    """

    def insert_before(self, key, new_key, val):
        """Insert new_key:value into dict before key"""
        keys = list(self.keys())
        vals = list(self.values())

        insert_idx = keys.index(key)

        keys.insert(insert_idx, new_key)
        vals.insert(insert_idx, val)

        self.clear()
        self.update({x: vals[i] for i, x in enumerate(keys)})

    def insert_after(self, key, new_key, val):
        """Insert new_key:value into dict after key"""
        keys = list(self.keys())
        vals = list(self.values())

        insert_idx = keys.index(key) + 1

        if keys[-1] != key:
            keys.insert(insert_idx, new_key)
            vals.insert(insert_idx, val)
            self.clear()
            self.update({x: vals[i] for i, x in enumerate(keys)})
        else:
            self.update({new_key: val})


class CaseInsensitiveDict(MutableMapping):
    """A case-insensitive ``dict``-like object.
    Implements all methods and operations of
    ``MutableMapping`` as well as dict's ``copy``. Also
    provides ``lower_items``.
    All keys are expected to be strings. The structure remembers the
    case of the last key to be set, and ``iter(instance)``,
    ``keys()``, ``items()``, ``iterkeys()``, and ``iteritems()``
    will contain case-sensitive keys. However, querying and contains
    testing is case insensitive::
        cid = CaseInsensitiveDict()
        cid['Accept'] = 'application/json'
        cid['aCCEPT'] == 'application/json'  # True
        list(cid) == ['Accept']  # True
    For example, ``headers['content-encoding']`` will return the
    value of a ``'Content-Encoding'`` response header, regardless
    of how the header name was originally stored.
    If the constructor, ``.update``, or equality comparison
    operations are given keys that have equal ``.lower()``s, the
    behavior is undefined.
    """

    def __init__(self, data=None, **kwargs):
        self._store = {}
        if data is None:
            data = {}
        self.update(data, **kwargs)

    def __setitem__(self, key, value):
        self._store[key.lower()] = (key, value)

    def __getitem__(self, key):
        return self._store[key.lower()][1]

    def __delitem__(self, key):
        del self._store[key.lower()]

    def __iter__(self):
        return (casedkey for casedkey, mappedvalue in self._store.values())

    def __len__(self):
        return len(self._store)

    def lower_items(self):
        """Like iteritems(), but with all lowercase keys."""
        return ((lowerkey, keyval[1]) for (lowerkey, keyval) in self._store.items())

    def __eq__(self, other):
        if isinstance(other, Mapping):
            other = CaseInsensitiveDict(other)
        else:
            return NotImplemented
        return dict(self.lower_items()) == dict(other.lower_items())

    def copy(self):
        return CaseInsensitiveDict(self._store.values())

    def __repr__(self):
        return str(dict(self.items()))


if __name__ == '__main__':
    __import__('doctest').testmod()
