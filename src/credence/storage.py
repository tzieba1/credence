"""Uploaded PDFs on disk, one file per distinct document, named by content hash."""

from pathlib import Path


class DocumentStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    def path_for(self, sha256: str) -> Path:
        return self.root / sha256[:2] / f"{sha256}.pdf"

    def save(self, sha256: str, pdf: bytes) -> Path:
        path = self.path_for(sha256)
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            tmp = path.with_suffix(".part")
            tmp.write_bytes(pdf)
            tmp.replace(path)  # a reader never sees a half-written file
        return path

    def read(self, stored_path: str) -> bytes:
        return Path(stored_path).read_bytes()
