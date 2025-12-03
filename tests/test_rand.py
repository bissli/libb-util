import numpy as np
import pytest

from libb import random_choice, random_int, random_random, random_sample


class TestRandomChoice:
    """Tests for random_choice function."""

    def test_random_choice_returns_from_list(self):
        choices = ['a', 'b', 'c']
        result = random_choice(choices)
        assert result in choices

    def test_random_choice_does_not_mutate_input(self):
        original = [1, 2, 3, 4, 5]
        copy = original.copy()
        random_choice(original)
        assert original == copy


class TestRandomInt:
    """Tests for random_int function."""

    def test_random_int_in_range(self):
        result = random_int(1, 10)
        assert 1 <= result <= 10

    def test_random_int_same_bounds(self):
        result = random_int(5, 5)
        assert result == 5


class TestRandomRandom:
    """Tests for random_random function."""

    def test_random_random_in_range(self):
        result = random_random()
        assert 0.0 <= result < 1.0


class TestRandomSample:
    """Tests for random_sample function."""

    def test_random_sample_returns_subset(self):
        arr = np.array([1, 2, 3, 4, 5])
        result = random_sample(arr, size=3)
        assert len(result) == 3
        for val in result:
            assert val in arr

    def test_random_sample_default_size(self):
        arr = np.array([10, 20, 30])
        result = random_sample(arr)
        assert len(result) == 1
        assert result[0] in arr


if __name__ == '__main__':
    pytest.main([__file__])
