"""Download the attributed public teaching dataset with byte-level integrity."""

from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path
from urllib.request import Request, urlopen

SOURCE_URL = "https://jse.amstat.org/v19n3/decock/AmesHousing.txt"
SOURCE_SHA256 = "6cfe6cb525ba437de428653a1040e2aed7d696640bf75203786a6d7a0e67cfcc"
MAX_DOWNLOAD_BYTES = 5_000_000


def download_ames(destination: str | Path, *, force: bool = False) -> Path:
    """No credentials, model binaries, or external user data are transmitted."""
    destination = Path(destination)
    if destination.exists() and not force:
        if hashlib.sha256(destination.read_bytes()).hexdigest() != SOURCE_SHA256:
            raise ValueError("Existing Ames file differs from the reference checksum. Use --force to replace it explicitly.")
        return destination
    request = Request(SOURCE_URL, headers={"User-Agent": "Sprint-Educational-ML-Lab/1.0"})
    with urlopen(request, timeout=45) as response:
        content = response.read(MAX_DOWNLOAD_BYTES + 1)
    if len(content) > MAX_DOWNLOAD_BYTES:
        raise ValueError("Dataset download exceeds the expected size limit.")
    actual = hashlib.sha256(content).hexdigest()
    if actual != SOURCE_SHA256:
        raise ValueError(f"Dataset checksum mismatch: expected {SOURCE_SHA256}, received {actual}. No file was written.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(dir=destination.parent, suffix=".download", delete=False) as handle:
            temporary_path = Path(handle.name)
            handle.write(content)
        os.replace(temporary_path, destination)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()
    return destination
