import logging
import os
import random
from functools import wraps

logger = logging.getLogger(__name__)

__all__ = [
    'random_choice',
    'random_int',
    'random_sample',
    'random_random',
]


def rseed(func):
    """Decorator to seed random with OS entropy before function call.

    :param func: Function to wrap.
    :returns: Wrapped function with OS-seeded randomness.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        RAND_SIZE = 4
        random_data = os.urandom(RAND_SIZE)
        random_seed = int.from_bytes(random_data, byteorder='big')
        random.seed(random_seed)
        return func(*args, **kwargs)
    return wrapper


@rseed
def random_choice(choices: list):
    """Random choice from a list, seeded with OS entropy.

    :param list choices: List of items to choose from.
    :returns: Randomly selected item.

    Example::

        >>> result = random_choice(['a', 'b', 'c'])
        >>> result in ['a', 'b', 'c']
        True
    """
    choices = list(choices)  # copy to avoid mutating input
    random.shuffle(choices)
    return choices[0]


@rseed
def random_int(a: int, b: int):
    """Random integer between a and b inclusive, seeded with OS entropy.

    :param int a: Lower bound.
    :param int b: Upper bound.
    :returns: Random integer in [a, b].
    :rtype: int

    Example::

        >>> result = random_int(1, 10)
        >>> 1 <= result <= 10
        True
    """
    return random.randint(a, b)


@rseed
def random_random():
    """Random float in [0, 1), seeded with OS entropy.

    :returns: Random float.
    :rtype: float

    Example::

        >>> result = random_random()
        >>> 0 <= result < 1
        True
    """
    return random.random()


@rseed
def random_sample(arr, size: int = 1):
    """Random sample of N elements from numpy array.

    :param np.array arr: Array to sample from.
    :param int size: Number of elements to sample.
    :returns: Array of sampled elements.
    :rtype: np.array
    """
    import numpy as np
    return arr[np.random.choice(len(arr), size=size, replace=False)]
