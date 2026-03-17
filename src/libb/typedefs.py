from collections.abc import Iterable
from io import BytesIO, FileIO, TextIOWrapper
from typing import IO, Any

__all__ = ['FileLike', 'Attachable', 'Dimension']

#: Type alias for file-like objects (IO streams, BytesIO, FileIO, TextIOWrapper).
FileLike = IO[BytesIO] | BytesIO | FileIO | TextIOWrapper
#: Type alias for attachable content (string, dict, file-like, or nested iterable).
Attachable = str | dict | FileLike | Iterable[Iterable[Any]]
#: Type alias for dimensions as (width, height) tuple.
Dimension = tuple[int, int]
