import pathlib

import wrapt


@wrapt.patch_function_wrapper('mimetypes', 'init')
def patch_mimetypes_init(wrapped, instance, args, kwargs):
    """Patch mimetypes init to use custom known files."""
    knownfiles = pathlib.Path(__file__).parent.absolute() / 'mime.types'
    return wrapped([str(knownfiles)])


import mimetypes


def magic_mime_from_buffer(buffer: bytes) -> str:
    """Detect mimetype using the ``magic`` library.

    :param bytes buffer: Buffer from header of file.
    :returns: The detected mimetype.
    :rtype: str
    """
    import magic
    return magic.from_buffer(buffer, mime=True)


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


__all__ = ['guess_type', 'guess_extension', 'magic_mime_from_buffer']

if __name__ == '__main__':
    # universal type
    assert guess_extension('image/jpeg') == '.jpg'
    assert guess_type('a.jpg') == 'image/jpeg'
    # custom patched type
    assert guess_extension('x-epoc/x-sisx-app') == '.sisx'
    assert guess_type('a.sisx') == 'x-epoc/x-sisx-app'
