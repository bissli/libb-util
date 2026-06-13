import io
import zipfile

import pytest

from libb import guess_extension, guess_type, magic_mime_from_buffer
from libb import sniff_format
from libb.mime import _refine_zip_mime

try:
    import magic
    HAS_MAGIC = True
except ImportError:
    HAS_MAGIC = False


DOCX_MIME = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
XLSX_MIME = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
PPTX_MIME = 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
ODS_MIME = 'application/vnd.oasis.opendocument.spreadsheet'


def _ooxml(top_dir: str) -> bytes:
    """Build a minimal OOXML archive with the given part top-dir."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as archive:
        archive.writestr('[Content_Types].xml', '<?xml version="1.0"?><Types/>')
        archive.writestr(f'{top_dir}/document.xml', '<x/>')
    return buf.getvalue()


def _odf(mimetype: str) -> bytes:
    """Build a minimal ODF archive declaring the given mimetype member."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as archive:
        archive.writestr('mimetype', mimetype)
        archive.writestr('content.xml', '<x/>')
    return buf.getvalue()


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


class TestRefineZipMime:
    """Tests for OOXML/ODF disambiguation of zip-container buffers."""

    def test_docx_resolved_from_word_topdir(self):
        assert _refine_zip_mime(_ooxml('word')) == DOCX_MIME

    def test_xlsx_resolved_from_xl_topdir(self):
        assert _refine_zip_mime(_ooxml('xl')) == XLSX_MIME

    def test_pptx_resolved_from_ppt_topdir(self):
        assert _refine_zip_mime(_ooxml('ppt')) == PPTX_MIME

    def test_odf_resolved_from_mimetype_member(self):
        assert _refine_zip_mime(_odf(ODS_MIME)) == ODS_MIME

    def test_plain_zip_is_not_refined(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w') as archive:
            archive.writestr('readme.txt', 'hello')
        assert _refine_zip_mime(buf.getvalue()) is None

    def test_non_zip_buffer_returns_none(self):
        assert _refine_zip_mime(b'not a zip at all') is None


@pytest.mark.skipif(not HAS_MAGIC, reason='magic module not installed')
class TestSniffFormat:
    """End-to-end content sniff -> (mimetype, extension)."""

    def test_pdf_sniffs_to_pdf(self):
        pdf = b'%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF'
        assert sniff_format(pdf) == ('application/pdf', '.pdf')

    def test_xlsx_refined_past_zip(self):
        mime, ext = sniff_format(_ooxml('xl'))
        assert mime == XLSX_MIME
        assert ext == '.xlsx'

    def test_docx_refined_past_zip(self):
        mime, ext = sniff_format(_ooxml('word'))
        assert mime == DOCX_MIME
        assert ext == '.docx'

    def test_plain_text(self):
        mime, ext = sniff_format(b'just plain research text\n')
        assert mime.startswith('text/')


if __name__ == '__main__':
    pytest.main([__file__])
