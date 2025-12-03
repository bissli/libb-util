import warnings

import pytest

from libb import composable, compose, copydoc, repeat, timing
from libb.func import MultiMethod, find_decorators, get_calling_function
from libb.func import is_instance_method, multimethod, suppresswarning


class TestCompose:
    """Tests for compose function."""

    def test_compose_two_functions(self):
        f = lambda x: x + 1
        g = lambda x: x * 2
        h = compose(f, g)
        # compose(f, g)(x) = f(g(x)) = (x * 2) + 1
        assert h(5) == 11

    def test_compose_multiple_functions(self):
        f = lambda x: x + 1
        g = lambda x: x * 2
        h = lambda x: x - 3
        composed = compose(f, g, h)
        # compose(f, g, h)(x) = f(g(h(x))) = ((x - 3) * 2) + 1
        assert composed(10) == 15


class TestComposable:
    """Tests for composable decorator."""

    def test_composable_with_decorator_list(self):
        def double(func):
            def wrapped(n):
                return func(n) * 2
            return wrapped

        def add_one(func):
            def wrapped(n):
                return func(n) + 1
            return wrapped

        @composable([double, add_one])
        def identity(x):
            return x

        # Decorators applied in reverse: first add_one, then double
        # identity(5) -> add_one wraps it -> 6 -> double wraps it -> 12
        assert identity(5) == 12


class TestCopydoc:
    """Tests for copydoc decorator."""

    def test_copydoc_copies_docstring(self):
        def source():
            """This is the source docstring."""

        @copydoc(source)
        def target():
            pass

        assert target.__doc__ == source.__doc__


class TestRepeat:
    """Tests for repeat decorator."""

    def test_repeat_basic(self):
        call_count = 0

        @repeat(3)
        def increment():
            nonlocal call_count
            call_count += 1

        increment()
        assert call_count == 3


class TestTiming:
    """Tests for timing decorator."""

    def test_timing_returns_result(self):
        @timing
        def add(a, b):
            return a + b

        result = add(2, 3)
        assert result == 5


class TestIsInstanceMethod:
    """Tests for is_instance_method function."""

    def test_is_instance_method_true(self):
        class MyClass:
            def my_method(self):
                pass
        assert is_instance_method(MyClass.my_method) is True

    def test_is_instance_method_false(self):
        # Use a module-level function to avoid nested qualname
        assert is_instance_method(compose) is False


class TestFindDecorators:
    """Tests for find_decorators function."""

    def test_find_decorators_basic(self):
        # find_decorators inspects source code and returns dict of func -> decorators
        import libb.func
        result = find_decorators(libb.func)
        assert isinstance(result, dict)
        # Should find function definitions
        assert 'compose' in result
        assert 'timing' in result

    def test_find_decorators_finds_all_functions(self):
        import libb.func
        result = find_decorators(libb.func)
        # Should find all top-level function and method definitions
        assert 'is_instance_method' in result
        assert 'composable' in result
        # These top-level functions don't have decorators applied
        assert result['compose'] == []


class TestComposableSingleDecorator:
    """Tests for composable with a single decorator (not a list)."""

    def test_composable_with_single_decorator(self):
        def triple(func):
            def wrapped(n):
                return func(n) * 3
            return wrapped

        @composable(triple)
        def identity(x):
            return x

        # Single decorator applied
        assert identity(5) == 15


class TestCopydocWithExistingDoc:
    """Tests for copydoc when target has existing docstring."""

    def test_copydoc_combines_docstrings(self):
        def source():
            """Source documentation."""

        @copydoc(source)
        def target():
            """Target documentation."""

        assert 'Source documentation.' in target.__doc__
        assert 'Target documentation.' in target.__doc__

    def test_copydoc_basefirst_false(self):
        def source():
            """Source doc."""

        @copydoc(source, basefirst=False)
        def target():
            """Target doc."""

        # With basefirst=False, target doc comes first
        assert target.__doc__.index('Target doc.') < target.__doc__.index('Source doc.')

    def test_copydoc_disables_doctests(self):
        def source():
            """>>> 2 + 2
            4
            """

        @copydoc(source)
        def target():
            pass

        assert '# doctest: +DISABLE' in target.__doc__


class TestGetCallingFunction:
    """Tests for get_calling_function."""

    def test_get_calling_function_basic(self):
        def outer():
            return get_calling_function()

        result = outer()
        assert result is outer

    def test_get_calling_function_in_method(self):
        class MyClass:
            def my_method(self):
                return get_calling_function()

        obj = MyClass()
        result = obj.my_method()
        assert result.__name__ == 'my_method'

    def test_get_calling_function_not_found(self):
        # Call from eval to make it impossible to find the function
        with pytest.raises(AttributeError, match='func not found'):
            eval('get_calling_function()')


class TestSuppresswarning:
    """Tests for suppresswarning decorator."""

    def test_suppresswarning_suppresses(self):
        @suppresswarning
        def warn_func():
            warnings.warn('This should be suppressed', UserWarning, stacklevel=2)
            return 'done'

        # Should not raise and should return result
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always')
            result = warn_func()
            # The inner warning should be suppressed
            assert result == 'done'

    def test_suppresswarning_preserves_function_name(self):
        @suppresswarning
        def my_named_func():
            pass

        assert my_named_func.__name__ == 'my_named_func'


class TestMultiMethod:
    """Tests for MultiMethod class."""

    def test_multimethod_basic(self):
        mm = MultiMethod('test_mm')
        mm.register((int, int), lambda a, b: a + b)
        mm.register((str, str), lambda a, b: a + ' ' + b)

        assert mm(1, 2) == 3
        assert mm('hello', 'world') == 'hello world'

    def test_multimethod_no_match(self):
        mm = MultiMethod('test_mm')
        mm.register((int, int), lambda a, b: a + b)

        with pytest.raises(TypeError, match='no match'):
            mm('a', 1)

    def test_multimethod_duplicate_registration(self):
        mm = MultiMethod('test_mm')
        mm.register((int, int), lambda a, b: a + b)

        with pytest.raises(TypeError, match='duplicate registration'):
            mm.register((int, int), lambda a, b: a * b)


class TestMultimethodDecorator:
    """Tests for multimethod decorator."""

    def test_multimethod_decorator(self):
        @multimethod(int, int)
        def add(a, b):
            return a + b

        @multimethod(float, float)
        def add(a, b):
            return a + b + 0.5

        assert add(1, 2) == 3
        assert add(1.0, 2.0) == 3.5


if __name__ == '__main__':
    pytest.main([__file__])
