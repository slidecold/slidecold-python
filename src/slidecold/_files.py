import mimetypes
import os
from pathlib import Path
from typing import IO, Tuple, Union

FileInput = Union[str, "os.PathLike[str]", bytes, IO[bytes], Tuple[str, bytes]]


def to_upload(file: FileInput, default_name: str = "upload") -> Tuple[str, bytes, str]:
    """Normalize a file argument into an httpx multipart tuple (filename, content, content_type)."""
    # shortcut: reads the whole file into memory (fine for photos/CSVs); stream it if large uploads appear.
    if isinstance(file, tuple):
        name, content = file
    elif isinstance(file, bytes):
        name, content = default_name, file
    elif isinstance(file, (str, os.PathLike)):
        path = Path(file)
        name, content = path.name, path.read_bytes()
    else:
        name, content = Path(getattr(file, "name", default_name)).name, file.read()
    return name, content, mimetypes.guess_type(name)[0] or "application/octet-stream"
