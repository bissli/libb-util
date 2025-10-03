import contextlib
import logging
import os
import random
from functools import wraps

with contextlib.suppress(ImportError, ModuleNotFoundError):
    import numpy as np


logger = logging.getLogger(__name__)

__all__ = [
    'random_choice',
    'random_int',
    'random_sample',
    'random_random',
]


def rseed(func):
    """Random seed through the OS"""
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
    """Random choice amont list of choices"""
    random.shuffle(choices)
    return choices[0]


@rseed
def random_int(a: int, b: int):
    return random.randint(a, b)


@rseed
def random_random():
    return random.random()


@rseed
def random_sample(arr: 'np.array', size: int = 1) -> 'np.array':
    """Random sample size N element from numpy array"""
    return arr[np.random.choice(len(arr), size=size, replace=False)]
