import logging

import pytest

from libb import ErrorCatcher, attrs, cachedstaticproperty, catch_exception
from libb import classproperty, delegate, extend_instance, include
from libb import lazy_property, makecls, memoize, singleton
from libb import staticandinstancemethod, ultimate_type


class TestAttrs:
    """Tests for attrs function."""

    def test_attrs_basic(self):
        class Foo:
            _a = 1
            _b = 2
            attrs('a', 'b')

        f = Foo()
        assert f.a == 1
        assert f.b == 2

    def test_attrs_setter(self):
        class Foo:
            _a = 1
            attrs('a')

        f = Foo()
        f.a = 99
        assert f.a == 99
        assert f._a == 99


class TestInclude:
    """Tests for include function."""

    def test_include_all(self):
        d = {'x': 10, 'y': 'foo'}

        class Foo:
            include(d)

        assert Foo.x == 10
        assert Foo.y == 'foo'

    def test_include_selective(self):
        d = {'x': 10, 'y': 'foo'}

        class Boo:
            include(d, ('y',))

        assert not hasattr(Boo, 'x')
        assert hasattr(Boo, 'y')


class TestSingleton:
    """Tests for singleton decorator."""

    def test_singleton_same_instance(self):
        @singleton
        class Foo:
            x = 100

        assert Foo() is Foo() is Foo
        assert id(Foo()) == id(Foo())

    def test_singleton_shared_state(self):
        @singleton
        class Bar:
            _x = 50
            attrs('x')

        f = Bar()
        assert f.x == Bar().x == 50
        Bar.x = 75
        assert f.x == Bar().x == 75


class TestMemoize:
    """Tests for memoize decorator."""

    def test_memoize_caches_result(self):
        call_count = 0

        @memoize
        def expensive(n):
            nonlocal call_count
            call_count += 1
            return n * 2

        assert expensive(5) == 10
        assert expensive(5) == 10
        assert call_count == 1

    def test_memoize_different_args(self):
        @memoize
        def add(a, b):
            return a + b

        assert add(1, 2) == 3
        assert add(3, 4) == 7
        assert ((1, 2), ()) in add.cache
        assert ((3, 4), ()) in add.cache


class TestClassproperty:
    """Tests for classproperty decorator."""

    def test_classproperty_computed(self):
        class Foo:
            a = 1
            b = 2

            @classproperty
            def c(cls):
                return cls.a + cls.b

        assert Foo.c == 3

    def test_classproperty_dynamic(self):
        class Foo:
            a = 1
            b = 2

            @classproperty
            def c(cls):
                return cls.a + cls.b

        Foo.a = 10
        assert Foo.c == 12


class TestDelegate:
    """Tests for delegate function."""

    def test_delegate_attribute(self):
        class X:
            a = 1

        class Y:
            x = X()
            delegate('x', 'a')

        assert Y().a == 1

    def test_delegate_method(self):
        class A:
            def echo(self, msg):
                return msg

        class B:
            a = A()
            delegate('a', ['echo'])

        assert B().echo('hello') == 'hello'


class TestLazyProperty:
    """Tests for lazy_property decorator."""

    def test_lazy_property_computed_once(self):
        call_count = 0

        class Foo:
            @lazy_property
            def expensive(self):
                nonlocal call_count
                call_count += 1
                return 42

        f = Foo()
        assert f.expensive == 42
        assert f.expensive == 42
        assert call_count == 1

    def test_lazy_property_caches(self):
        class Foo:
            @lazy_property
            def value(self):
                return 100

        f = Foo()
        assert not hasattr(f, '_lazy_value')
        _ = f.value
        assert hasattr(f, '_lazy_value')

    def test_lazy_property_deleter(self):
        call_count = 0

        class Foo:
            @lazy_property
            def value(self):
                nonlocal call_count
                call_count += 1
                return 42

        f = Foo()
        assert f.value == 42
        assert call_count == 1
        del f.value
        assert not hasattr(f, '_lazy_value')
        assert f.value == 42
        assert call_count == 2


class TestCachedstaticproperty:
    """Tests for cachedstaticproperty decorator."""

    def test_cachedstaticproperty_computed_once(self):
        call_count = 0

        class Foo:
            @cachedstaticproperty
            def computed():
                nonlocal call_count
                call_count += 1
                return 'result'

        assert Foo.computed == 'result'
        assert Foo.computed == 'result'
        assert call_count == 1


class TestStaticandinstancemethod:
    """Tests for staticandinstancemethod decorator."""

    def test_staticandinstancemethod_static_call(self):
        class Foo:
            @staticandinstancemethod
            def bar(self, x):
                return self is None

        assert Foo.bar(1) is True

    def test_staticandinstancemethod_instance_call(self):
        class Foo:
            @staticandinstancemethod
            def bar(self, x):
                return self is None

        assert Foo().bar(1) is False


class TestMakecls:
    """Tests for makecls function."""

    def test_makecls_resolves_conflict(self):
        class M_A(type):
            pass

        class M_B(type):
            pass

        class A(metaclass=M_A):
            pass

        class B(metaclass=M_B):
            pass

        # This should work without raising TypeError
        class C(A, B, metaclass=makecls()):
            pass

        assert C is not None

    def test_makecls_single_metaclass(self):
        class M_Single(type):
            pass

        class A(metaclass=M_Single):
            pass

        # Single metaclass case
        class B(A, metaclass=makecls()):
            pass

        assert B is not None

    def test_makecls_cached(self):
        class M_A(type):
            pass

        class M_B(type):
            pass

        class A(metaclass=M_A):
            pass

        class B(metaclass=M_B):
            pass

        # Call twice to test caching
        class C1(A, B, metaclass=makecls()):
            pass

        class C2(A, B, metaclass=makecls()):
            pass

        assert C1 is not None
        assert C2 is not None


class TestExtendInstance:
    """Tests for extend_instance function."""

    def test_extend_instance_left(self):
        class Mixin:
            def greet(self):
                return 'hello'

        class Base:
            pass

        b = Base()
        extend_instance(b, Mixin, left=True)
        assert b.greet() == 'hello'

    def test_extend_instance_right(self):
        class Mixin:
            def greet(self):
                return 'hello'

        class Base:
            pass

        b = Base()
        extend_instance(b, Mixin, left=False)
        assert b.greet() == 'hello'


class TestUltimateType:
    """Tests for ultimate_type function."""

    def test_ultimate_type_basic(self):
        import datetime

        class DateFoo(datetime.date):
            pass

        class DateBar(DateFoo):
            pass

        d0 = datetime.date(2000, 1, 1)
        d1 = DateFoo(2000, 1, 1)
        d2 = DateBar(2000, 1, 1)

        assert ultimate_type(d0) == datetime.date
        assert ultimate_type(d1) == datetime.date
        assert ultimate_type(d2) == datetime.date

    def test_ultimate_type_none(self):
        assert isinstance(None, ultimate_type(None))

    def test_ultimate_type_object(self):
        assert ultimate_type(object) == object


class TestCatchException:
    """Tests for catch_exception decorator."""

    def test_catch_exception_returns_none(self):
        @catch_exception
        def divide(x, y):
            return x / y

        assert divide(1, 0) is None

    def test_catch_exception_normal_return(self):
        @catch_exception
        def divide(x, y):
            return x / y

        assert divide(10, 2) == 5.0

    def test_catch_exception_with_level(self):
        @catch_exception(level=logging.ERROR)
        def risky():
            raise ValueError('test')

        assert risky() is None


class TestErrorCatcher:
    """Tests for ErrorCatcher metaclass."""

    def test_error_catcher_catches_exceptions(self):
        logging.getLogger('libb.classes').setLevel(logging.CRITICAL)

        class Test(metaclass=ErrorCatcher):
            def __init__(self, val):
                self.val = val

            def calc(self):
                return self.val / 0

        t = Test(5)
        assert t.calc() is None

    def test_error_catcher_normal_methods_work(self):
        logging.getLogger('libb.classes').setLevel(logging.CRITICAL)

        class Test(metaclass=ErrorCatcher):
            def add(self, a, b):
                return a + b

        t = Test()
        assert t.add(2, 3) == 5


if __name__ == '__main__':
    pytest.main([__file__])
