import logging
import sys
from functools import wraps

logger = logging.getLogger(__name__)


def attrs(*attrnames):
    """Lazily stuff in get/setters

    >>> class Foo:
    ...     _a = 1
    ...     _b = 2
    ...     _c = 3
    ...     _z = (_a, _b, _c)
    ...     attrs('a', 'b', 'c', 'z')

    vanilla attrs work fine
    >>> f = Foo()
    >>> f.a
    1
    >>> f.a+f.b==f.c
    True

    setter flows through to instance
    >>> f.a = 2
    >>> f.a==f._a==2
    True

    we can also do lazy definitions like our `z`
    >>> len(f.z)==3
    True
    >>> sum(f.z)==6
    True
    >>> f.z[0]==f._z[0]==1
    True
    >>> f.z = (4, 5, 6,)
    >>> sum(f.z)
    15
    >>> f.a==2
    True
    """
    def _makeprop(name):
        _get = lambda self: getattr(self, f'_{name}')
        _set = lambda self, value: setattr(self, f'_{name}', value)
        return property(_get, _set)

    caller_locals = sys._getframe(1).f_locals
    for attrname in attrnames:
        caller_locals[attrname] = _makeprop(attrname)


def include(source, names=()):
    """Include greedy classproperty dict in declaration

    >>> d = dict(x=10, y='foo')
    >>> class Foo:
    ...     include(d)

    >>> Foo.x
    10
    >>> Foo.y
    'foo'
    >>> class Boo:
    ...     include(d, ('y',))

    >>> hasattr(Boo, 'x')
    False
    >>> hasattr(Boo, 'y')
    True
    """
    sys._getframe(1).f_locals.update({name: source[name] for name in names} if names else source)


def singleton(cls):
    """Elegant singleton enforcement via python decorators wiki

    >>> @singleton
    ... class Foo:
    ...     _x = 100
    ...     _y = 'y'
    ...     attrs('x', 'y')

    >>> F = Foo
    >>> F() is F() is F
    True
    >>> id(F()) == id(F())
    True
    >>> f = F()
    >>> f.x == F().x == f.x == 100
    True
    >>> F.x = 50
    >>> f.x == F().x == F.x == 50
    True

    >>> import copy
    >>> fc = copy.deepcopy(f)
    >>> FC = copy.deepcopy(F)
    >>> fc.y==f.y==F.y==FC.y=='y'
    True
    """
    obj = cls()
    # dunders are looked up on the type (class), not instance
    obj.__class__ = type(obj.__class__.__name__, (obj.__class__,), {})
    obj.__class__.__call__ = lambda x: x
    return obj


def memoize(obj):
    """Keep dict of function calls as a function attribute
    re: http://stackoverflow.com/a/3243694/424380
    re: https://wiki.python.org/moin/PythonDecoratorLibrary#Memoize
    NOTE: we also have one from web.py which is nice ...

    unique n-length arrays of ints whose abs val sums to k:
    V(n,0)=1; V(0,k)=0; V(n,k) = V(n-1,k) + V(n,k-1) + V(n-1,k-1);

    >>> def n_with_sum_k(n, k):
    ...     if n==0:
    ...         return 0
    ...     elif k==0:
    ...         return 1
    ...     else:
    ...         less_n = n_with_sum_k(n-1, k)
    ...         less_k = n_with_sum_k(n, k-1)
    ...         less_both = n_with_sum_k(n-1, k-1)
    ...         return less_n + less_k + less_both

    >>> n_with_sum_k_mz = memoize(n_with_sum_k)
    >>> n_with_sum_k_mz(3, 5)
    61
    >>> n_with_sum_k_mz.cache
    {'(3, 5){}': 61}
    """

    cache = obj.cache = {}

    @wraps(obj)
    def memoizer(*args, **kwargs):
        key = str(args) + str(kwargs)
        if key not in cache:
            cache[key] = obj(*args, **kwargs)
        return cache[key]

    return memoizer


class classproperty(property):
    """Decorator like @property for classes instead of instances

    >>> class Foo:
    ...     include(dict(a=1, b=2))
    ...     @classproperty
    ...     def c(cls):
    ...         return cls.a+cls.b

    >>> Foo.a
    1
    >>> Foo.b
    2
    >>> Foo.c
    3
    >>> Foo.a = 2
    >>> Foo.c
    4
    """

    def __get__(desc, self, cls):
        return desc.fget(cls)


def delegate(deleg, attrs):
    """Delegate methods to other objects attached to your object

    >>> class X:
    ...     a = 1

    >>> class Y:
    ...     x = X()
    ...     delegate('x', 'a')

    >>> Y().a
    1

    >>> class A:
    ...     def echo(self, x):
    ...         print(x)

    >>> class B:
    ...     a = A()
    ...     delegate('a', ['echo'])

    >>> B().echo('whoa!')
    whoa!
    """

    def _makeprop(attr):
        return property(lambda self: getattr(getattr(self, deleg), attr))

    caller_locals = sys._getframe(1).f_locals
    for attr in attrs:
        caller_locals[attr] = _makeprop(attr)


def lazy_property(fn):
    """Decorator that makes a property lazy-evaluated.

    >>> import time
    >>> class Sloth:
    ...     def _slow_cool(self, n):
    ...         time.sleep(n)
    ...         return n**2
    ...     @lazy_property
    ...     def slow(self):
    ...         return True
    ...     @lazy_property
    ...     def cool(self):
    ...         return self._slow_cool(3)
    >>> x = time.time()
    >>> s = Sloth()
    >>> time.time()-x < 1
    True
    >>> time.time()-x < 1
    True
    >>> hasattr(s, '_lazy_slow')
    False
    >>> s.slow
    True
    >>> hasattr(s, '_lazy_slow')
    True
    >>> s.cool
    9
    >>> 3 < time.time()-x < 6
    True
    >>> s.cool
    9
    >>> 3 < time.time()-x < 6
    True
    """
    attr_name = '_lazy_' + fn.__name__

    @property
    def _lazy_property(self):
        if not hasattr(self, attr_name):
            setattr(self, attr_name, fn(self))
        return getattr(self, attr_name)

    return _lazy_property


class cachedstaticproperty:
    """Works like @property and @staticmethod combined

    >>> def somecalc():
    ...     print('Running somecalc...')
    ...     return 1

    >>> class Foo:
    ...    @cachedstaticproperty
    ...    def somefunc():
    ...        return somecalc()

    >>> Foo.somefunc
    Running somecalc...
    1
    >>> Foo.somefunc
    1
    """
    def __init__(self, func):
        self.func = func

    def __get__(self, inst, owner):
        result = self.func()
        setattr(owner, self.func.__name__, result)
        return result


class staticandinstancemethod:
    """Allows method to be either static or instance

    >>> class Foo:
    ...     @staticandinstancemethod
    ...     def bar(self, x, y):
    ...         print(self is None and "static" or "instance")
    >>> Foo.bar(1,2)
    static
    >>> Foo().bar(1,2)
    instance
    """
    def __init__(self, f):
        self.f = f

    def __get__(self, obj, klass=None):
        def newfunc(*args, **kw):
            return self.f(obj, *args, **kw)
        return newfunc


def extend_instance(obj, cls, left=True):
    """Apply mixins/extend base class after creation

    TODO: add better tests. ABC changes order precedence L-R.

    >>> from pprint import pprint
    >>> class X:pass
    >>> class Y: pass
    >>> class Z:pass
    >>> class A(X,Y):pass
    >>> class B(A,Y,Z):pass
    >>> class F(B): pass
    >>> pprint(F.mro())
    [<class '....F'>,
     <class '....B'>,
     <class '....A'>,
     <class '....X'>,
     <class '....Y'>,
     <class '....Z'>,
     <class 'object'>]
    >>> class F_L:
    ...     def __init__(self):
    ...         extend_instance(self, B, left=True)
    >>> class F_R:
    ...     def __init__(self):
    ...         extend_instance(self, B, left=False)
    >>> f_l = F_L()
    >>> pprint(f_l.__class__.__mro__)
    (<class '....F_L'>,
     <class '....B'>,
     <class '....A'>,
     <class '....X'>,
     <class '....Y'>,
     <class '....Z'>,
     <class '....F_L'>,
     <class 'object'>)
    >>> f_r = F_R()
    >>> pprint(f_r.__class__.__mro__)
    (<class '....F_R'>,
     <class '....F_R'>,
     <class '....B'>,
     <class '....A'>,
     <class '....X'>,
     <class '....Y'>,
     <class '....Z'>,
     <class 'object'>)
    """
    if left:
        obj.__class__ = type(obj.__class__.__name__, (cls, obj.__class__), {})
    else:
        obj.__class__ = type(obj.__class__.__name__, (obj.__class__, cls), {})


def ultimate_type(typeobj: object | type | None):
    """Resolve ultimate base of object (but not object base)

    >>> import datetime
    >>> class DateFoo(datetime.date):
    ...     pass
    >>> class DateBar(DateFoo):
    ...    pass
    >>> d0 = datetime.date(2000, 1, 1)
    >>> d1 = DateFoo(2000, 1, 1)
    >>> d2 = DateBar(2000, 1, 1)
    >>> ultimate_type(d0)
    <class 'datetime.date'>
    >>> ultimate_type(d1)
    <class 'datetime.date'>
    >>> ultimate_type(d1)
    <class 'datetime.date'>
    >>> ultimate_type(d1.__class__)
    <class 'datetime.date'>
    >>> ultimate_type(d2.__class__)
    <class 'datetime.date'>

    >>> ultimate_type(None)
    <class 'NoneType'>
    """
    if not isinstance(typeobj, type):
        typeobj = type(typeobj)
    bases, this = [typeobj], typeobj
    while True:
        try:
            bases.append(this.__bases__[-1])
            this = bases[-1]
        except IndexError:
            break
    return bases[-2]


def catch_exception(f):
    @wraps(f)
    def func(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            print('Caught an exception in', f.__name__)
    return func


class ErrorCatcher(type):
    """
    >>> class Test(metaclass=ErrorCatcher):
    ...     def __init__(self, val):
    ...         self.val = val
    ...     def calc(self):
    ...         return self.val / 0
    >>> t = Test(5)
    >>> t.calc()
    Caught an exception in calc
    """
    def __new__(cls, name, bases, dct):
        for m in dct:
            if callable(dct[m]):
                dct[m] = catch_exception(dct[m])
        return type.__new__(cls, name, bases, dct)


if __name__ == '__main__':
    __import__('doctest').testmod(optionflags=4 | 8 | 32)
