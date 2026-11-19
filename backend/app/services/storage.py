"""Local-disk storage for original uploads (a Docker volume in Compose).

Files are saved under random names; the user's filename is never used as a path.
Swap this class for an S3 implementation with the same two methods to scale out.
"""

import uuid
from pathlib import Path


class LocalFileStore:
    def __init__(self, root: str) -> None:
        self.root = Path(root).resolve()

    def save(self, content: bytes, extension: str) -> str:
        self.root.mkdir(parents=True, exist_ok=True)
        ext = extension.lower().lstrip(".")
        if not ext.isalnum():
            raise ValueError("bad extension")
        name = f"{uuid.uuid4().hex}.{ext}"
        (self.root / name).write_bytes(content)
        return name

    def delete(self, name: str) -> None:
        path = (self.root / name).resolve()
        if path.parent != self.root:  # defence in depth against path traversal
            raise ValueError("path outside upload directory")
        path.unlink(missing_ok=True)

    def exists(self, name: str) -> bool:
        return (self.root / name).is_file()
