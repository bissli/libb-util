import math
import random

__all__ = [
    'normal',
    'normalVec',
    'Random',
    'halton',
    'mat',
    'randomCorrelation',
    'choleskyTrans',
    'cholesky',
]


class _Callable:
    def __init__(self, call):
        self.__call__ = call


def _mul(lhs, rhs):
    return {
        'lo': (lhs['lo'] * rhs['lo']) & 0x7FFF,
        'hi': (((lhs['lo'] * rhs['lo']) >> 15) + lhs['lo'] * rhs['hi'] + lhs['hi'] * rhs['lo']) & 0x7FFF,
    }


def normal(generator):
    w = 1.0
    while w >= 1.0:
        x1 = 2.0 * generator.nextUniform01() - 1.0
        x2 = 2.0 * generator.nextUniform01() - 1.0
        w = x1 * x1 + x2 * x2
    w = math.sqrt((-2.0 * math.log(w)) / w)
    return x1 * w


def normalVec(n, generator):
    v = []
    for i in range(n):
        v.insert(i, normal(generator))
    return v


class Random:
    class BuiltinGenerator:
        def seed(self):
            pass

        seed = _Callable(seed)

        def nextUniform01():
            return random.random()

        nextUniform01 = _Callable(nextUniform01)

    class ExpGenerator:
        base = {'lo': 300773 & 0x7FFF, 'hi': 300773 >> 15}
        cur = None

        def seed(self):
            Random.ExpGenerator.cur = {'lo': 1, 'hi': 0}
            mask = 1
            mult = {'lo': Random.ExpGenerator.base['lo'], 'hi': Random.ExpGenerator.base['hi']}
            for i in range(30):
                if self & mask:
                    Random.ExpGenerator.cur = _mul(Random.ExpGenerator.cur, mult)
                mult = _mul(mult, mult)
                mask <<= 1

        seed = _Callable(seed)

        def nextUniform01():
            Random.ExpGenerator.cur = _mul(Random.ExpGenerator.cur, Random.ExpGenerator.base)
            seed = (Random.ExpGenerator.cur['lo'] + (Random.ExpGenerator.cur['hi'] << 15)) & 0x3FFFFFFF
            return seed / 1073741824.0

        nextUniform01 = _Callable(nextUniform01)


def halton(n, b):
    """Halton quasi random number generator
    n - index, should be coprime with b
    b - prime number base
    """
    n0 = n
    H = 0.0
    f = 1.0 / b
    while n0 > 0.0:
        n1 = int(n0 / b)
        r = n0 - n1 * b
        H += f * r
        f /= b
        n0 = n1
    return H


class mat:
    """Matrix operations as static methods."""

    @staticmethod
    def zero(rows, cols):
        """Create a zero matrix with given dimensions.

        >>> mat.zero(2, 3)
        [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]]
        """
        M = []
        for i in range(rows):
            M.insert(i, [])
            for j in range(cols):
                M[i].insert(j, 0.0)
        return M

    @staticmethod
    def mulVec(M, v):
        """Multiply matrix M by vector v.

        >>> mat.mulVec([[1, 2], [3, 4]], [1, 1])
        [3.0, 7.0]
        """
        r = []
        for i in range(len(M)):
            total = 0.0
            for j in range(len(v)):
                total += M[i][j] * v[j]
            r.insert(i, total)
        return r

    @staticmethod
    def mul(M, N):
        """Multiply matrix M by matrix N.

        >>> mat.mul([[1, 2], [3, 4]], [[5, 6], [7, 8]])
        [[19, 22], [43, 50]]
        """
        R = []
        for i in range(len(M)):
            if len(M[i]) != len(N):
                raise Exception('bad matricies')
            R.insert(i, [])
            for j in range(len(N[0])):
                total = 0
                for k in range(len(N)):
                    total += M[i][k] * N[k][j]
                R[i].insert(j, total)
        return R

    @staticmethod
    def trans(M):
        """Transpose matrix M.

        >>> mat.trans([[1, 2, 3], [4, 5, 6]])
        [[1, 4], [2, 5], [3, 6]]
        """
        R = []
        for i in range(len(M[0])):
            R.insert(i, [])
            for j in range(len(M)):
                R[i].insert(j, M[j][i])
        return R


def randomCorrelation(n, prng):
    T = []

    # Generate n uniform random columns
    for i in range(n):
        T.insert(i, [])
        for j in range(n):
            T[i].insert(j, normal(prng))

    # Normalize the columns
    for j in range(n):
        sqSum = 0
        for i in range(n):
            sqSum += T[i][j] * T[i][j]
        norm = math.sqrt(sqSum)
        for i in range(n):
            T[i][j] /= norm

    # result is T'*T
    return mat.mul(mat.trans(T), T)


def choleskyTrans(A):
    """Cholesky decomposition returning lower triangular matrix L.

    >>> L = choleskyTrans([[4.0, 2.0], [2.0, 2.0]])
    >>> abs(L[0][0] - 2.0) < 0.001
    True
    """
    n = len(A)

    L = mat.zero(n, n)
    for i in range(n):
        for j in range(i + 1):
            s = 0.0
            for k in range(j):
                s += L[i][k] * L[j][k]
            if i == j:
                L[i][i] = math.sqrt(A[i][i] - s)
            else:
                L[i][j] = 1.0 / L[j][j] * (A[i][j] - s)
    return L


def cholesky(A):
    """Cholesky decomposition returning upper triangular matrix."""
    return mat.trans(choleskyTrans(A))


if __name__ == '__main__':
    __import__('doctest').testmod()
