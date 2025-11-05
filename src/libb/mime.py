import pathlib

import wrapt


@wrapt.patch_function_wrapper('mimetypes', 'init')
def patch_mimetypes_init(wrapped, instance, args, kwargs):
    """Patch init known files"""
    knownfiles = pathlib.Path(__file__).parent.absolute() / 'mime.types'
    return wrapped([str(knownfiles)])


import mimetypes


def magic_mime_from_buffer(buffer: bytes) -> str:
    """Try to detect mimetype using ``magic`` library.
    :param buffer: buffer from header of file.
    :return: The mimetype
    """
    import magic
    return magic.from_buffer(buffer, mime=True)


def guess_extension(mimetype: str) -> str:
    return mimetypes.guess_extension(mimetype)


def guess_type(url: str):
    return mimetypes.guess_type(url)[0]


__all__ = ['guess_type', 'guess_extension', 'magic_mime_from_buffer']

if __name__ == '__main__':
    # universal type
    assert guess_extension('image/jpeg') == '.jpg'
    assert guess_type('a.jpg') == 'image/jpeg'
    # custom patched type
    assert guess_extension('x-epoc/x-sisx-app') == '.sisx'
    assert guess_type('a.sisx') == 'x-epoc/x-sisx-app'
