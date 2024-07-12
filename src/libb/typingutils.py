from io import BytesIO, FileIO, TextIOWrapper
from typing import IO, Any, Union
from collections.abc import Iterable

__all__ = ['FileLike', 'Attachable', 'Dimension']

FileLike = Union[IO[BytesIO], BytesIO, FileIO, TextIOWrapper]
Attachable = Union[str, dict, FileLike, Iterable[Iterable[Any]]]
Dimension = tuple[int, int]
