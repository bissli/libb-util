from __future__ import annotations

import io
import pathlib
import zipfile

import wrapt


@wrapt.patch_function_wrapper('mimetypes', 'init')
def patch_mimetypes_init(wrapped, instance, args, kwargs):
    """Patch mimetypes init to use custom known files."""
    knownfiles = pathlib.Path(__file__).parent.absolute() / 'mime.types'
    return wrapped([str(knownfiles)])


import mimetypes

# Zip-container documents that libmagic reports as the generic
# ``application/zip``: OOXML (docx/xlsx/pptx) carry a ``[Content_Types].xml``
# alongside a format-specific top-level part directory; ODF stores its type
# verbatim in an uncompressed ``mimetype`` member.
_OOXML_MIME_BY_TOPDIR = {
    'word': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'xl': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'ppt': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    }

# What libmagic returns when it cannot see past the zip container.
_ZIP_CONTAINER_MIMES = frozenset({
    'application/zip', 'application/octet-stream'})


def _refine_zip_mime(buffer: bytes) -> str | None:
    """Resolve a zip-container buffer to its precise OOXML/ODF mimetype.

    libmagic reports OOXML (docx/xlsx/pptx) and many ODF documents as the
    generic ``application/zip``. Inspect the archive to recover the true
    type: ODF from its verbatim ``mimetype`` member, OOXML from the
    top-level part directory next to ``[Content_Types].xml``. The whole
    file is required (the zip directory lives at the end of the stream).

    :param bytes buffer: Full file bytes.
    :returns: Precise mimetype, or None when it is not a readable
        OOXML/ODF archive.
    :rtype: str
    """
    try:
        archive = zipfile.ZipFile(io.BytesIO(buffer))
        names = archive.namelist()
    except (zipfile.BadZipFile, OSError):
        return None
    if 'mimetype' in names:
        odf = archive.read('mimetype').decode('ascii', 'ignore').strip()
        if odf.startswith('application/vnd.oasis.opendocument'):
            return odf
    if '[Content_Types].xml' in names:
        top_dirs = {name.split('/', 1)[0] for name in names}
        for top_dir, mime in _OOXML_MIME_BY_TOPDIR.items():
            if top_dir in top_dirs:
                return mime
    return None


def magic_mime_from_buffer(buffer: bytes) -> str:
    """Detect mimetype from a file's bytes using the ``magic`` library.

    OOXML (docx/xlsx/pptx) and ODF documents that libmagic reports as the
    generic ``application/zip`` are refined to their precise type by
    inspecting the archive -- pass the whole file, not just a header, for
    that refinement to apply.

    :param bytes buffer: File bytes (whole file recommended).
    :returns: The detected mimetype.
    :rtype: str
    """
    import magic
    mime = magic.from_buffer(buffer, mime=True)
    if mime in _ZIP_CONTAINER_MIMES:
        return _refine_zip_mime(buffer) or mime
    return mime


def guess_extension(mimetype: str) -> str:
    """Guess file extension for a mimetype.

    :param str mimetype: The mimetype to look up.
    :returns: File extension (including dot) or None.
    :rtype: str

    Example::

        >>> guess_extension('image/jpeg')
        '.jpg'
    """
    return mimetypes.guess_extension(mimetype)


def guess_type(url: str):
    """Guess mimetype from a URL or filename.

    :param str url: URL or filename to examine.
    :returns: Guessed mimetype or None.
    :rtype: str

    Example::

        >>> guess_type('document.pdf')
        'application/pdf'
        >>> guess_type('image.jpg')
        'image/jpeg'
    """
    return mimetypes.guess_type(url)[0]


def sniff_format(buffer: bytes) -> tuple[str, str | None]:
    """Sniff a file's ``(mimetype, extension)`` from its bytes.

    Convenience over ``magic_mime_from_buffer`` + ``guess_extension``:
    detect the mimetype from content (OOXML/ODF refined to their precise
    type) and map it to a dotted extension (``None`` when no extension is
    known for that type).

    :param bytes buffer: File bytes (whole file recommended).
    :returns: ``(mimetype, extension_or_None)``.
    :rtype: tuple

    Example::

        >>> mime, ext = sniff_format(open('model.xlsx', 'rb').read())
        >>> ext
        '.xlsx'
    """
    mime = magic_mime_from_buffer(buffer)
    return mime, guess_extension(mime)


__all__ = [
    'guess_type', 'guess_extension', 'magic_mime_from_buffer',
    'sniff_format']

if __name__ == '__main__':
    # universal type
    assert guess_extension('image/jpeg') == '.jpg'
    assert guess_type('a.jpg') == 'image/jpeg'
    # custom patched type
    assert guess_extension('x-epoc/x-sisx-app') == '.sisx'
    assert guess_type('a.sisx') == 'x-epoc/x-sisx-app'
