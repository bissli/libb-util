import pytest

from libb import guess_extension, guess_type, magic_mime_from_buffer

try:
    import magic
    HAS_MAGIC = True
except ImportError:
    HAS_MAGIC = False


@pytest.mark.skipif(not HAS_MAGIC, reason='magic module not installed')
class TestMagicMimeFromBuffer:
    """Tests for magic_mime_from_buffer function."""

    def test_magic_mime_from_buffer_png(self):
        # PNG header magic bytes with IHDR chunk
        png_header = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
        result = magic_mime_from_buffer(png_header)
        assert result == 'image/png'

    def test_magic_mime_from_buffer_jpeg(self):
        # JPEG header magic bytes
        jpeg_header = b'\xff\xd8\xff\xe0\x00\x10JFIF'
        result = magic_mime_from_buffer(jpeg_header)
        assert result == 'image/jpeg'

    def test_magic_mime_from_buffer_text(self):
        # Plain text
        text_content = b'Hello, World!\n'
        result = magic_mime_from_buffer(text_content)
        assert 'text' in result


class TestGuessExtension:
    """Tests for guess_extension function."""

    def test_guess_extension_jpeg(self):
        result = guess_extension('image/jpeg')
        assert result == '.jpg'

    def test_guess_extension_png(self):
        result = guess_extension('image/png')
        assert result == '.png'

    def test_guess_extension_html(self):
        result = guess_extension('text/html')
        assert result in {'.htm', '.html'}

    def test_guess_extension_unknown(self):
        result = guess_extension('application/x-unknown-type-xyz')
        assert result is None


class TestGuessType:
    """Tests for guess_type function."""

    def test_guess_type_jpeg(self):
        result = guess_type('image.jpg')
        assert result == 'image/jpeg'

    def test_guess_type_png(self):
        result = guess_type('image.png')
        assert result == 'image/png'

    def test_guess_type_html(self):
        result = guess_type('page.html')
        assert result == 'text/html'

    def test_guess_type_unknown(self):
        result = guess_type('file.xyz123')
        assert result is None


if __name__ == '__main__':
    pytest.main([__file__])
