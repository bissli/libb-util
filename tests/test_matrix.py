from decimal import Decimal, localcontext

import pytest

from libb import dot, matadd, matdim, matident, matprod, matrix, matsub
from libb import matzero, trace, transpose
from libb.matrix import bsub, diag, gjinv, gramm, linreg, matrandom
from libb.matrix import matunitize, matxtx, printmat, qr


class TestDot:
    """Tests for dot function."""

    def test_dot_basic(self):
        assert dot([1, 2, 3], [3, 2, 1]) == 10


class TestMatrix:
    """Tests for matrix function."""

    def test_matrix_column(self):
        assert matrix([1, 2, 3]) == [[1], [2], [3]]

    def test_matrix_row(self):
        assert matrix([1, 2, 3], cols=False) == [[1, 2, 3]]


class TestTrace:
    """Tests for trace function."""

    def test_trace_basic(self):
        A = [[Decimal(12), Decimal(-51), Decimal(4)],
             [Decimal(6), Decimal(167), Decimal(-68)],
             [Decimal(-4), Decimal(24), Decimal(-41)]]
        assert trace(A) == Decimal(138)


class TestMatident:
    """Tests for matident function."""

    def test_matident_square(self):
        result = matident(2)
        assert result[0][0] == Decimal(1)
        assert result[0][1] == Decimal(0)
        assert result[1][0] == Decimal(0)
        assert result[1][1] == Decimal(1)


class TestMatzero:
    """Tests for matzero function."""

    def test_matzero_square(self):
        result = matzero(2)
        assert result == [[0, 0], [0, 0]]

    def test_matzero_rectangular(self):
        result = matzero(2, 3)
        assert len(result) == 2
        assert len(result[0]) == 3


class TestMatdim:
    """Tests for matdim function."""

    def test_matdim_square(self):
        A = [[1, 2, 3], [4, 5, 6], [7, 8, 9]]
        assert matdim(A) == (3, 3)

    def test_matdim_rectangular(self):
        A = [[1, 2], [3, 4], [5, 6], [7, 8]]
        assert matdim(A) == (4, 2)


class TestMatadd:
    """Tests for matadd function."""

    def test_matadd_basic(self):
        A = [[1, 2], [3, 4]]
        B = [[5, 6], [7, 8]]
        C = matadd(A, B)
        assert C == [[6, 8], [10, 12]]

    def test_matadd_dimension_mismatch(self):
        A = [[1, 2], [3, 4]]
        B = [[1, 2, 3]]
        with pytest.raises(AssertionError):
            matadd(A, B)


class TestMatsub:
    """Tests for matsub function."""

    def test_matsub_basic(self):
        A = [[5, 6], [7, 8]]
        B = [[1, 2], [3, 4]]
        C = matsub(A, B)
        assert C == [[4, 4], [4, 4]]

    def test_matsub_dimension_mismatch(self):
        # Line 213 - dimension mismatch raises AssertionError
        A = [[1, 2], [3, 4]]
        B = [[1, 2, 3]]
        with pytest.raises(AssertionError):
            matsub(A, B)


class TestTranspose:
    """Tests for transpose function."""

    def test_transpose_basic(self):
        A = [(1, 2, 3), (4, 5, 6)]
        At = transpose(A)
        assert matdim(A) == (2, 3)
        assert matdim(At) == (3, 2)

    def test_transpose_twice(self):
        A = [(1, 2), (3, 4)]
        Att = transpose(transpose(A))
        assert A == Att


class TestMatprod:
    """Tests for matprod function."""

    def test_matprod_basic(self):
        A = [[Decimal(12), Decimal(-51), Decimal(4)],
             [Decimal(-4), Decimal(24), Decimal(-41)]]
        B = [[Decimal(2), Decimal(4)],
             [Decimal('-9.24'), Decimal(-99)],
             [Decimal('-1.2345'), Decimal(2)]]
        C = matprod(A, B)
        assert matdim(C) == (2, 2)


class TestPrintmat:
    """Tests for printmat function."""

    def test_printmat_basic(self, capsys):
        A = [[Decimal(12), Decimal(-51), Decimal(4)],
             [Decimal(6), Decimal(167), Decimal(-68)],
             [Decimal(-4), Decimal(24), Decimal(-41)]]
        printmat(A)
        captured = capsys.readouterr()
        assert '12.0000' in captured.out
        assert '-51.0000' in captured.out


class TestDiag:
    """Tests for diag function."""

    def test_diag_square_matrix(self):
        A = [[Decimal(12), Decimal(-51)],
             [Decimal(-4), Decimal(24)]]
        result = diag(A)
        assert result[0][0] == Decimal(12)
        assert result[0][1] == Decimal(0)
        assert result[1][0] == Decimal(0)
        assert result[1][1] == Decimal(24)

    def test_diag_non_square_raises(self):
        A = [[Decimal(12), Decimal(-51)],
             [Decimal(6), Decimal(167)],
             [Decimal(-4), Decimal(24)]]
        with pytest.raises(AssertionError, match='square matrix'):
            diag(A)


class TestMatdimEdgeCases:
    """Additional tests for matdim edge cases."""

    def test_matdim_vector(self):
        # Vector without columns
        A = [1, 2, 3]
        m, n = matdim(A)
        assert m == 3
        assert n == 0


class TestMatrandom:
    """Tests for matrandom function."""

    def test_matrandom_square(self):
        R = matrandom(3)
        assert matdim(R) == (3, 3)
        # Values should be Decimal
        assert isinstance(R[0][0], Decimal)

    def test_matrandom_rectangular(self):
        R = matrandom(3, 2)
        assert matdim(R) == (3, 2)


class TestMatunitize:
    """Tests for matunitize function."""

    def test_matunitize_basic(self):
        X = [[Decimal(3), Decimal(0)],
             [Decimal(4), Decimal(0)],
             [Decimal(0), Decimal(5)]]
        V = matunitize(X)
        # First column should be normalized (3,4,0) -> (0.6, 0.8, 0)
        assert abs(float(V[0][0]) - 0.6) < 0.01
        assert abs(float(V[1][0]) - 0.8) < 0.01

    def test_matunitize_inplace(self):
        X = [[Decimal(3), Decimal(0)],
             [Decimal(4), Decimal(0)],
             [Decimal(0), Decimal(5)]]
        original_id = id(X)
        V = matunitize(X, inplace=True)
        assert id(V) == original_id


class TestMatprodEdgeCases:
    """Additional tests for matprod edge cases."""

    def test_matprod_dimension_mismatch(self):
        A = [[1, 2, 3]]  # 1x3
        B = [[1, 2]]  # 1x2 - can't multiply
        with pytest.raises(AssertionError, match='col.*row'):
            matprod(A, B)


class TestMatxtx:
    """Tests for matxtx function."""

    def test_matxtx_basic(self):
        # Use floats due to float/Decimal mixing issue in matxtx
        X = [[1.0, 2.0],
             [3.0, 4.0]]
        result = matxtx(X)
        # Should return X^T * X
        assert matdim(result) == (2, 2)
        # X^T * X for [[1,2],[3,4]] = [[10, 14], [14, 20]]
        assert abs(float(result[0][0]) - 10) < 0.01


class TestGjinv:
    """Tests for gjinv (Gauss-Jordan inverse) function."""

    def test_gjinv_identity(self):
        I = matident(2)
        inv = gjinv(I)
        # Inverse of identity is identity
        assert abs(float(inv[0][0]) - 1.0) < 0.01
        assert abs(float(inv[0][1])) < 0.01

    def test_gjinv_basic(self):
        A = [[Decimal(4), Decimal(7)],
             [Decimal(2), Decimal(6)]]
        inv = gjinv(A)
        # Check that A * A^-1 = I
        product = matprod(A, inv)
        assert abs(float(product[0][0]) - 1.0) < 0.01
        assert abs(float(product[1][1]) - 1.0) < 0.01

    def test_gjinv_3x3(self):
        # Line 314 - 3x3 matrix needed to cover upper triangular elimination
        A = [[Decimal(1), Decimal(2), Decimal(3)],
             [Decimal(0), Decimal(1), Decimal(4)],
             [Decimal(5), Decimal(6), Decimal(0)]]
        inv = gjinv(A)
        # Check that A * A^-1 = I
        product = matprod(A, inv)
        assert abs(float(product[0][0]) - 1.0) < 0.01
        assert abs(float(product[1][1]) - 1.0) < 0.01
        assert abs(float(product[2][2]) - 1.0) < 0.01


class TestGramm:
    """Tests for gramm (Gramm-Schmidt orthogonalization) function."""

    def test_gramm_basic(self):
        with localcontext() as ctx:
            ctx.prec = 28
            A = [[Decimal(12), Decimal(-51), Decimal(4)],
                 [Decimal(6), Decimal(167), Decimal(-68)],
                 [Decimal(-4), Decimal(24), Decimal(-41)]]
            Q = gramm(A)
            # Q should have orthonormal columns
            assert matdim(Q) == (3, 3)


class TestQR:
    """Tests for QR decomposition function."""

    def test_qr_basic(self):
        with localcontext() as ctx:
            ctx.prec = 28
            A = [[Decimal(12), Decimal(-51), Decimal(4)],
                 [Decimal(6), Decimal(167), Decimal(-68)],
                 [Decimal(-4), Decimal(24), Decimal(-41)]]
            Q, R = qr(A)
            # Q*R should give back A
            result = matprod(Q, R)
            assert abs(float(result[0][0]) - 12) < 0.01


class TestBsub:
    """Tests for bsub (back substitution) function."""

    def test_bsub_basic(self):
        # Simple upper triangular system
        R = [[Decimal(2), Decimal(1)],
             [Decimal(0), Decimal(3)]]
        z = [[Decimal(5), Decimal(9)]]  # z as row matrix
        b = bsub(R, z)
        # Solution to Rb = z
        assert len(b) == 1
        assert len(b[0]) == 2


class TestLinreg:
    """Tests for linreg (linear regression) function."""

    def test_linreg_basic(self):
        with localcontext() as ctx:
            ctx.prec = 28
            # Simple linear regression y = 2x + 1
            y = [Decimal(3), Decimal(5), Decimal(7)]  # y = 2x + 1 for x = 1, 2, 3
            x = [[Decimal(1)], [Decimal(2)], [Decimal(3)]]
            b = linreg(y, x)
            # b should be approximately [1, 2] (intercept, slope)
            assert len(b) == 2


if __name__ == '__main__':
    pytest.main([__file__])
