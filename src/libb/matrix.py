from decimal import Decimal, localcontext

__all__ = [
    'printmat',
    'dot',
    'matrix',
    'trace',
    'diag',
    'matident',
    'matzero',
    'matdim',
    'matrandom',
    'matunitize',
    'matadd',
    'matsub',
    'transpose',
    'matprod',
    'matxtx',
    'gjinv',
    'gramm',
    'qr',
    'bsub',
    'linreg',
]


def printmat(X, prec=4, fmt='%8.4f'):
    """Print out the matrix using Decimal localcontext and strf

    >>> A = [[Decimal("12"), Decimal("-51"), Decimal("4")],
    ...      [Decimal("6"), Decimal("167"), Decimal("-68")],
    ...      [Decimal("-4"), Decimal("24"), Decimal("-41")]]
    ...
    >>> printmat(A)
     12.0000 -51.0000   4.0000
      6.0000 167.0000 -68.0000
     -4.0000  24.0000 -41.0000
    """
    with localcontext() as pctx:
        pctx.prec = prec
        for row in X:
            strf = ' '.join(fmt % +col for col in row)
            print(strf)


def dot(X, Y):
    """Dot product of vectors X and Y.

    >>> dot([1, 2, 3], [3, 2, 1])
    10
    """
    return sum(x * y for (x, y) in zip(X, Y))


def matrix(vector, cols=True):
    """1 column matrix out of array or vector X.

    >>> matrix([1, 2, 3])
    [[1], [2], [3]]
    >>> matrix([1, 2, 3], cols=False)
    [[1, 2, 3]]
    """
    if cols:
        return [[x] for x in vector]
    return [list(vector)]


def trace(A):
    """Trace of the matrix.

    >>> A = [[Decimal("12"), Decimal("-51"), Decimal("4")],
    ...      [Decimal("6"), Decimal("167"), Decimal("-68")],
    ...      [Decimal("-4"), Decimal("24"), Decimal("-41")]]
    ...
    >>> print((trace(A)))
    138
    """
    return sum(A[i][i] for i in range(len(A)))


def diag(A):
    """Just diagonal elements of A as a matrix

    >>> A = [[Decimal("12"), Decimal("-51")],
    ...      [Decimal("6"), Decimal("167")],
    ...      [Decimal("-4"), Decimal("24")]]
    ...
    >>> diag(A)
    Traceback (most recent call last):
    AssertionError: Can only get diagonal of a square matrix
    >>> B = [[Decimal("12"), Decimal("-51")],
    ...      [Decimal("-4"), Decimal("24")]]
    ...
    >>> printmat(diag(B))
     12.0000   0.0000
      0.0000  24.0000
    """
    m, n = matdim(A)
    if m != n:
        raise AssertionError('Can only get diagonal of a square matrix')
    for i in range(m):
        for j in range(n):
            if i != j:
                A[i][j] = Decimal(0)
    return A


def matident(m, n=None):
    """Identity matrix (m,n)

    >>> printmat(matident(2))
      1.0000   0.0000
      0.0000   1.0000
    """
    if n is None:
        n = m
    B = [[Decimal(0)] * n for i in range(m)]
    for i in range(m):
        B[i][i] = Decimal(1)
    return B


def matzero(m, n=None):
    """M by n zero matrix.

    >>> printmat(matzero(3))
      0.0000   0.0000   0.0000
      0.0000   0.0000   0.0000
      0.0000   0.0000   0.0000
    """
    if n is None:
        n = m
    return [[0] * n for i in range(m)]


def matdim(A):
    """Number of rows and columns of A

    >>> A = [[Decimal("12"), Decimal("-51"), Decimal("4")],
    ...      [Decimal("6"), Decimal("167"), Decimal("-68")],
    ...      [Decimal("-4"), Decimal("24"), Decimal("-41")]]
    ...
    >>> matdim(A)
    (3, 3)
    >>> B = [[Decimal("2"), Decimal("4")],
    ...      [Decimal("-3.4"), Decimal("-68")],
    ...      [Decimal("-9.24"), Decimal("-99")],
    ...      [Decimal("-1.2345"), Decimal("2")]]
    ...
    >>> matdim(B)
    (4, 2)
    """
    m = len(A)
    if hasattr(A[0], '__len__'):
        n = len(A[0])
    else:
        n = 0
    return (m, n)


def matrandom(nrow, ncol=None):
    """Random matrix useful for some linalg optimizations
    WARNING: have not tested for dependency of values
    e.g., http://arxiv.org/abs/0910.1205

    >>> matdim(matrandom(2))
    (2, 2)
    >>> matdim(matrandom(3,2))
    (3, 2)
    """
    from libb import random_random
    if ncol is None:
        ncol = nrow
    R = []
    for i in range(nrow):
        R.append([Decimal(str(random_random())) for j in range(ncol)])
    return R


def matunitize(X, inplace=False):
    """Transforms each vector in X to have unit length."""
    V = [x[:] for x in X] if not inplace else X
    nrow, ncol = matdim(X)
    for j in range(ncol):
        recipnorm = sum(X[j][j] ** Decimal(2) for j in range(ncol))
        for i in range(nrow):
            V[i][j] *= recipnorm
    return V


def matadd(A, B):
    """C = A + B, must have right dimensions
    TODO refactor matadd, matsub, other routines

    """
    m, n = matdim(A)
    mm, nn = matdim(B)
    if m != mm or n != nn:
        raise AssertionError('Can only add matrices with same dimensions')
    C = matzero(m, n)
    for i in range(m):
        for j in range(n):
            C[i][j] = A[i][j] + B[i][j]
    return C


def matsub(A, B):
    """C = A - B, must have right dimensions"""
    m, n = matdim(A)
    mm, nn = matdim(B)
    if m != mm or n != nn:
        raise AssertionError('Can only subtract matrices with same dimensions')
    C = matzero(m, n)
    for i in range(m):
        for j in range(n):
            C[i][j] = A[i][j] - B[i][j]
    return C


def transpose(a):
    """Duck typing zip since this transpose trick is easy to forget

    >>> A = [(Decimal("12"), Decimal("-51"), Decimal("4")),
    ...      (Decimal("-4"), Decimal("24"), Decimal("-41"))]
    ...
    >>> At = transpose(A)
    >>> matdim(A)
    (2, 3)
    >>> matdim(At)
    (3, 2)
    >>> Att = transpose(At)
    >>> A == Att
    True
    """
    return list(zip(*a))


def matprod(A, B):
    """Product of two matrices, i.e., dot product

    >>> A = [[Decimal("12"), Decimal("-51"), Decimal("4")],
    ...      [Decimal("-4"), Decimal("24"), Decimal("-41")]]
    ...
    >>> B = [[Decimal("2"), Decimal("4")],
    ...      [Decimal("-9.24"), Decimal("-99")],
    ...      [Decimal("-1.2345"), Decimal("2")]]
    ...
    >>> C = matprod(A,B)
    >>> matdim(C)
    (2, 2)
    >>> printmat(C)
    490.3000 5105.0000
    -179.1000 -2474.0000
    """
    m, n = matdim(A)
    p, q = matdim(B)
    if n != p:
        raise AssertionError('col(A) <> row(B)')
    if iter(B[0]):
        q = len(B[0])
    C = matzero(m, q)
    for i in range(m):
        for j in range(q):
            t = sum(A[i][k] * B[k][j] for k in range(p))
            C[i][j] = t
    return C


def matxtx(X):
    """Matrix of coefficients from least squares calc
    trying to speed up matrix multiplication on t(X), X
    """
    m = len(X)
    n = len(X[0])
    M = [[Decimal(0)] * n for i in range(n)]
    for i in range(n):
        for j in range(i, n):
            dot = 0.0
            for r in range(m):
                dot += X[r][i] * X[r][j]
            M[i][j] = dot
            if i != j:
                M[j][i] = dot
    return M


def gjinv(AA, inplace=False):
    """Inverse of square matrix by Gauss-Jordan reduction"""
    A = [row[:] for row in AA] if not inplace else AA
    n = len(AA)
    B = matident(n)

    # Divide the ith row by A[i][i]
    for i in range(n):
        m = Decimal(1) / A[i][i]
        for j in range(i, n):
            A[i][j] *= m
        for j in range(n):
            B[i][j] *= m

        # lower triangular elements.
        for k in range(i + 1, n):
            m = A[k][i]
            for j in range(i + 1, n):
                A[k][j] -= m * A[i][j]
            for j in range(n):
                B[k][j] -= m * B[i][j]

        # upper triangular elements.
        for k in range(i):
            m = A[k][i]
            for j in range(i + 1, n):
                A[k][j] -= m * A[i][j]
            for j in range(n):
                B[k][j] -= m * B[i][j]
    return B


def gramm(X, inplace=False):
    """Gramm-Schmidt orthogonalization of matrix X
    cleaned up from Ernesto P. Adorio's original:
    http://adorio-research.org/wordpress/?p=4353
    """
    V = [row[:] for row in X] if not inplace else X

    k = len(X[0])
    n = len(X)

    for j in range(k):
        for i in range(j):  # D = <Vi, Vj>
            D = sum(V[p][i] * V[p][j] for p in range(n))
            for p in range(n):  # Vj = Vj - <Vi,Vj> Vi/< Vi,Vi >
                V[p][j] -= D * V[p][i]

        # normalize column V[j]
        sum_of_sq = sum((V[p][j]) ** Decimal(2) for p in range(n))
        invnorm = Decimal(1) / sum_of_sq.sqrt()
        for p in range(n):
            V[p][j] *= invnorm

    return V


def qr(A):
    """QR decomposition of A via gramm-schmidt orthogonalization

    >>> A = [[Decimal("12"), Decimal("-51"), Decimal("4")],
    ...      [Decimal("6"), Decimal("167"), Decimal("-68")],
    ...      [Decimal("-4"), Decimal("24"), Decimal("-41")]]
    ...
    >>> with localcontext() as dctx:
    ...     dctx.prec = 10
    ...     Q,R = qr(A)
    ...     rez = matprod(Q, R)
    ...
    >>> printmat(rez, prec=4, fmt="%8.4f")
     12.0000 -51.0000   4.0000
      6.0000 167.0000 -68.0000
     -4.0000  24.0000 -41.0000
    """
    Q = gramm(A)
    R = matprod(transpose(Q), A)
    return Q, R


def bsub(r, z):
    """back-substitute "R b = z", where r is triangular"""
    m, n = matdim(r)
    p, q = matdim(z)
    b = [[Decimal(0)] * n]
    pp, qq = matdim(b)
    for j in range(n - 1, -1, -1):
        zz = z[0][j] - sum(r[j][k] * b[0][k] for k in range(j + 1, n))
        b[0][j] = zz / r[j][j]
    return b


def linreg(y, x):
    """Linear regression in pure python"""
    # prepend x with 1
    for xx in x:
        xx.insert(0, Decimal(1))

    # QR decomposition
    q, r = qr(x)

    # z = Q^T y
    z = matprod(transpose(q), matrix(y))

    # back substitute to find b in R b = z
    b = bsub(r, transpose(z))
    b = b[0]

    return b


if __name__ == '__main__':
    __import__('doctest').testmod(optionflags=4 | 8 | 32)
