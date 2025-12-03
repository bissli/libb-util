import tempfile

import pytest

from libb import base64file, kryptophy


class TestBase64file:
    """Tests for base64file function."""

    def test_base64file_basic(self):
        with tempfile.NamedTemporaryFile(mode='wb', delete=False) as f:
            f.write(b'Hello World')
            f.flush()
            result = base64file(f.name)
            # base64 encoding of 'Hello World' is 'SGVsbG8gV29ybGQ='
            assert b'SGVsbG8gV29ybGQ=' in result


class TestKryptophy:
    """Tests for kryptophy function."""

    def test_kryptophy_basic(self):
        # 'a' is 0x61, so 'a' should produce 0x61 = 97
        result = kryptophy('a')
        assert result == 0x61

    def test_kryptophy_multiple_chars(self):
        # 'ab' is 0x61, 0x62 -> '0x6162' = 24930
        result = kryptophy('ab')
        assert result == 0x6162

    def test_kryptophy_longer_string(self):
        result = kryptophy('abc')
        assert result == 0x616263

    def test_kryptophy_empty_raises(self):
        # Empty string would create '0x' which is invalid
        with pytest.raises(ValueError):
            kryptophy('')


if __name__ == '__main__':
    pytest.main([__file__])
