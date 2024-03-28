import logging
import os
import random

import numpy as np
from typing_extensions import List

logger = logging.getLogger(__name__)


def randomseed() -> int:
    """Random seed through the OS
    """
    RAND_SIZE = 4
    random_data = os.urandom(RAND_SIZE)
    random_seed: int = int.from_bytes(random_data, byteorder='big')
    return int(random_seed)


def random_choice(choices: List):
    """Random choice amont list of choices"""
    random.seed(randomseed())
    random.shuffle(choices)
    return choices[0]


def random_sample(arr: np.array, size: int = 1) -> np.array:
    """Random sample size N element from numpy array"""
    return arr[np.random.choice(len(arr), size=size, replace=False)]
