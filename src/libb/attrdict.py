from abc import ABCMeta
from collections.abc import Mapping, MutableMapping

__all__ = [
    'attrdict',
    'lazydict',
    'emptydict',
    'bidict',
    'MutableDict',
    'CaseInsensitiveDict',
]


class attrdict(dict):
    """A dictionary subclass that allows attribute-style access.

    This is a dictionary that allows access to its keys as attributes
    (using dot notation) in addition to standard dictionary access methods.

    Basic Usage::

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
        >>> 'x' in d
        True
        >>> 'w' in d
        False
        >>> d.get('x')
        10
        >>> d.get('w')

    Deep Copy Behavior::

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

    Access Methods (handles ``obj.get('attr')``, ``obj['attr']``, and ``obj.attr``)::

        >>> class A(attrdict):
        ...     @property
        ...     def x(self):
        ...         return 1
        >>> a = A()
        >>> a['x'] == a.x == a.get('x')
        True
        >>> a.get('b')
        >>> a['b']
        Traceback (most recent call last):
            ...
        KeyError: 'b'
        >>> a.b
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
    """A dictionary where function values are lazily evaluated.

    Functions stored as values are called with the dictionary as argument
    when the key is accessed, making them behave like computed properties.

    Basic Usage::

        >>> a = lazydict(a=1, b=2, c=lambda x: x.a+x.b)
        >>> a.c
        3
        >>> a.a = 99
        >>> a.c  # Recalculated with new value
        101
        >>> a.z = 1
        >>> a.z
        1

    Instance Isolation (descriptors are not shared between instances)::

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
        >>> a.f
        Traceback (most recent call last):
            ...
        AttributeError: f
    """

    __slots__ = ()

    def __getattr__(self, attrname):
        if attrname not in self:
            raise AttributeError(attrname)
        attrval = self[attrname]
        if callable(attrval):
            return attrval(self)
        return attrval


class emptydict(attrdict):
    """A dictionary that returns None for non-existing keys without raising exceptions.

    Similar to attrdict but returns None instead of raising KeyError or AttributeError
    when accessing non-existing keys.

    Basic Usage::

        >>> a = emptydict(a=1, b=2)
        >>> a.c == None
        True
        >>> a.b
        2
        >>> a['b']
        2
        >>> 'c' in a
        False
        >>> 'b' in a
        True
        >>> a.get('b')
        2
        >>> a.get('c')
    """

    __slots__ = ()

    def __getattr__(self, attrname):
        try:
            return attrdict.__getattr__(self, attrname)
        except AttributeError:
            return

    def __getitem__(self, attrname):
        try:
            return attrdict.__getitem__(self, attrname)
        except AttributeError:
            return


class bidict(dict):
    """Bidirectional dictionary that allows multiple keys with the same value.

    Maintains an inverse mapping from values to lists of keys that enables
    bidirectional lookup.

    Basic Usage::

        >>> bd = bidict({'a': 1, 'b': 2})
        >>> bd
        {'a': 1, 'b': 2}
        >>> bd.inverse
        {1: ['a'], 2: ['b']}

    Multiple Keys with Same Value::

        >>> bd['c'] = 1
        >>> bd
        {'a': 1, 'b': 2, 'c': 1}
        >>> bd.inverse
        {1: ['a', 'c'], 2: ['b']}

    Removing Keys Updates Inverse::

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

    Changing Values Updates Inverse::

        >>> bd['b'] = 3
        >>> bd
        {'b': 3}
        >>> bd.inverse
        {2: [], 3: ['b']}
    """

    __slots__ = ('inverse',)

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
    """An ordered dictionary with additional insertion methods.

    Extends the standard dictionary with methods to insert items before
    or after existing keys. Relies on Python 3.7+ dictionary implementation
    which preserves insertion order.
    """

    __slots__ = ()

    def insert_before(self, key, new_key, val):
        """Insert new_key:value into dict before key.

        Example::

            >>> d = MutableDict({'a': 1, 'b': 2, 'c': 3})
            >>> d.insert_before('b', 'x', 10)
            >>> list(d.keys())
            ['a', 'x', 'b', 'c']
            >>> d['x']
            10
        """
        keys = list(self.keys())
        vals = list(self.values())

        insert_idx = keys.index(key)

        keys.insert(insert_idx, new_key)
        vals.insert(insert_idx, val)

        self.clear()
        self.update({x: vals[i] for i, x in enumerate(keys)})

    def insert_after(self, key, new_key, val):
        """Insert new_key:value into dict after key.

        Example::

            >>> d = MutableDict({'a': 1, 'b': 2, 'c': 3})
            >>> d.insert_after('a', 'x', 10)
            >>> list(d.keys())
            ['a', 'x', 'b', 'c']
            >>> d['x']
            10
        """
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
    """A case-insensitive dictionary-like object.

    Implements all methods and operations of ``MutableMapping`` as well as
    dict's ``copy``. Also provides ``lower_items``.

    All keys are expected to be strings. The structure remembers the
    case of the last key to be set, and ``iter(instance)``, ``keys()``,
    ``items()`` will contain case-sensitive keys. However, querying and
    contains testing is case insensitive:

        cid = CaseInsensitiveDict()
        cid['Accept'] = 'application/json'
        cid['aCCEPT'] == 'application/json'  # True
        list(cid) == ['Accept']  # True

    For example, ``headers['content-encoding']`` will return the
    value of a ``'Content-Encoding'`` response header, regardless
    of how the header name was originally stored.

    Note:
        If the constructor, ``.update``, or equality comparison
        operations are given keys that have equal ``.lower()`` values, the
        behavior is undefined.
    """

    __slots__ = ('_store',)

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
        """Like iteritems(), but with all lowercase keys.

        Example::

            >>> cid = CaseInsensitiveDict({'Content-Type': 'application/json'})
            >>> list(cid.lower_items())
            [('content-type', 'application/json')]
        """
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
    __import__('doctest').testmod(optionflags=4 | 8 | 32)
