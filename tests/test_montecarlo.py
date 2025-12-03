import pytest

from libb import cholesky, choleskyTrans, halton, mat
from libb.montecarlo import Random, normal, normalVec, randomCorrelation


class TestHalton:
    """Tests for halton quasi-random number generator."""

    def test_halton_base_2(self):
        # halton(1, 2) = 1/2 = 0.5
        result = halton(1, 2)
        assert abs(result - 0.5) < 0.001

    def test_halton_base_3(self):
        # halton(1, 3) = 1/3
        result = halton(1, 3)
        assert abs(result - 1/3) < 0.001

    def test_halton_sequence(self):
        # First few halton numbers base 2: 0.5, 0.25, 0.75, 0.125, ...
        results = [halton(i, 2) for i in range(1, 5)]
        expected = [0.5, 0.25, 0.75, 0.125]
        for r, e in zip(results, expected):
            assert abs(r - e) < 0.001

    def test_halton_zero(self):
        result = halton(0, 2)
        assert result == 0.0


class TestMat:
    """Tests for mat matrix operations."""

    def test_mat_zero(self):
        result = mat.zero(2, 3)
        assert len(result) == 2
        assert len(result[0]) == 3
        assert all(result[i][j] == 0.0 for i in range(2) for j in range(3))

    def test_mat_zero_square(self):
        result = mat.zero(3, 3)
        assert len(result) == 3
        assert len(result[0]) == 3

    def test_mat_trans(self):
        M = [[1, 2, 3], [4, 5, 6]]
        result = mat.trans(M)
        assert result == [[1, 4], [2, 5], [3, 6]]

    def test_mat_trans_square(self):
        M = [[1, 2], [3, 4]]
        result = mat.trans(M)
        assert result == [[1, 3], [2, 4]]

    def test_mat_mul(self):
        A = [[1, 2], [3, 4]]
        B = [[5, 6], [7, 8]]
        result = mat.mul(A, B)
        # [[1*5+2*7, 1*6+2*8], [3*5+4*7, 3*6+4*8]]
        # [[19, 22], [43, 50]]
        assert result == [[19, 22], [43, 50]]

    def test_mat_mul_identity(self):
        A = [[1, 0], [0, 1]]
        B = [[5, 6], [7, 8]]
        result = mat.mul(A, B)
        assert result == [[5, 6], [7, 8]]

    def test_mat_mul_dimension_mismatch(self):
        A = [[1, 2, 3], [4, 5, 6]]
        B = [[1, 2], [3, 4]]  # 2x2, but A is 2x3
        with pytest.raises(Exception, match='bad matricies'):
            mat.mul(A, B)

    def test_mat_mulVec(self):
        M = [[1, 2], [3, 4]]
        v = [1, 1]
        result = mat.mulVec(M, v)
        assert result == [3.0, 7.0]

    def test_mat_mulVec_identity(self):
        M = [[1, 0], [0, 1]]
        v = [5, 7]
        result = mat.mulVec(M, v)
        assert result == [5.0, 7.0]


class TestCholesky:
    """Tests for cholesky decomposition."""

    def test_choleskyTrans_identity(self):
        # Identity matrix decomposes to identity
        A = [[1.0, 0.0], [0.0, 1.0]]
        L = choleskyTrans(A)
        assert abs(L[0][0] - 1.0) < 0.001
        assert abs(L[1][1] - 1.0) < 0.001
        assert abs(L[0][1]) < 0.001
        assert abs(L[1][0]) < 0.001

    def test_choleskyTrans_basic(self):
        # Simple positive definite matrix
        A = [[4.0, 2.0], [2.0, 2.0]]
        L = choleskyTrans(A)
        # L should be [[2, 0], [1, 1]]
        assert abs(L[0][0] - 2.0) < 0.001
        assert abs(L[1][0] - 1.0) < 0.001
        assert abs(L[1][1] - 1.0) < 0.001

    def test_cholesky_basic(self):
        # Simple positive definite matrix
        A = [[4.0, 2.0], [2.0, 2.0]]
        U = cholesky(A)
        # U should be [[2, 1], [0, 1]] (transpose of L)
        assert abs(U[0][0] - 2.0) < 0.001
        assert abs(U[0][1] - 1.0) < 0.001
        assert abs(U[1][1] - 1.0) < 0.001

    def test_cholesky_roundtrip(self):
        # Verify L * L^T = A
        A = [[4.0, 2.0], [2.0, 2.0]]
        L = choleskyTrans(A)
        LT = mat.trans(L)
        result = mat.mul(L, LT)
        for i in range(2):
            for j in range(2):
                assert abs(result[i][j] - A[i][j]) < 0.001


class MockGenerator:
    """Mock generator that wraps _Callable methods properly."""
    @staticmethod
    def nextUniform01():
        return Random.BuiltinGenerator.nextUniform01.__call__()

    @staticmethod
    def seed():
        pass


class TestNormal:
    """Tests for normal distribution generator."""

    def test_normal_with_mock_generator(self):
        # Use mock generator that properly wraps the _Callable
        values = [normal(MockGenerator) for _ in range(100)]
        # Normal values should be distributed around 0
        mean = sum(values) / len(values)
        assert abs(mean) < 1.0  # Should be close to 0
        # Some values should be positive, some negative
        assert any(v > 0 for v in values)
        assert any(v < 0 for v in values)


class TestNormalVec:
    """Tests for normalVec function."""

    def test_normalVec_basic(self):
        vec = normalVec(5, MockGenerator)
        assert len(vec) == 5
        # All should be floats
        assert all(isinstance(v, float) for v in vec)


class TestBuiltinGenerator:
    """Tests for Random.BuiltinGenerator.

    Note: The _Callable wrapper requires calling .__call__() explicitly.
    """

    def test_builtin_generator_seed(self):
        # Seed takes self but does nothing - pass a dummy value
        Random.BuiltinGenerator.seed.__call__(None)

    def test_builtin_generator_nextUniform01(self):
        value = Random.BuiltinGenerator.nextUniform01.__call__()
        assert 0.0 <= value <= 1.0


class TestExpGenerator:
    """Tests for Random.ExpGenerator.

    Note: The _Callable wrapper requires calling .__call__() explicitly.
    """

    def test_exp_generator_seed(self):
        # Seed with a value
        Random.ExpGenerator.seed.__call__(12345)
        assert Random.ExpGenerator.cur is not None

    def test_exp_generator_nextUniform01(self):
        # Seed first
        Random.ExpGenerator.seed.__call__(42)
        value = Random.ExpGenerator.nextUniform01.__call__()
        assert 0.0 <= value <= 1.0

    def test_exp_generator_reproducible(self):
        # Same seed should give same sequence
        Random.ExpGenerator.seed.__call__(12345)
        v1 = Random.ExpGenerator.nextUniform01.__call__()
        v2 = Random.ExpGenerator.nextUniform01.__call__()

        Random.ExpGenerator.seed.__call__(12345)
        v3 = Random.ExpGenerator.nextUniform01.__call__()
        v4 = Random.ExpGenerator.nextUniform01.__call__()

        assert v1 == v3
        assert v2 == v4


class TestRandomCorrelation:
    """Tests for randomCorrelation function."""

    def test_random_correlation_basic(self):
        corr = randomCorrelation(3, MockGenerator)
        # Should return 3x3 matrix
        assert len(corr) == 3
        assert all(len(row) == 3 for row in corr)
        # Diagonal should be close to 1
        for i in range(3):
            assert abs(corr[i][i] - 1.0) < 0.01
        # Should be symmetric
        for i in range(3):
            for j in range(3):
                assert abs(corr[i][j] - corr[j][i]) < 0.01

    def test_random_correlation_2x2(self):
        corr = randomCorrelation(2, MockGenerator)
        assert len(corr) == 2
        # Correlation values should be between -1 and 1
        for i in range(2):
            for j in range(2):
                assert -1.01 <= corr[i][j] <= 1.01


if __name__ == '__main__':
    pytest.main([__file__])
