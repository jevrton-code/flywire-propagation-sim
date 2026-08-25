"""Fetching and caching of the raw FlyWire files.

Both raw files are large (852 MB for the connectivity dump) and immutable -- they
are versioned, published artefacts. So we cache them on disk, verify them by MD5
against the checksum published by the upstream record, and never re-download a
file that already validates.

The cache directory is *not* versioned in git (see ``.gitignore``); only the
small curated subgraph in ``data/subgraphs/`` is.
"""

from __future__ import annotations

import concurrent.futures as futures
import hashlib
import os
import shutil
import urllib.request
from pathlib import Path

from .provenance import CONNECTIVITY, AnnotationRelease

#: Override with FLYWIRE_CACHE_DIR to reuse a dump you already have on disk.
CACHE_DIR_ENV = "FLYWIRE_CACHE_DIR"
DEFAULT_CACHE_DIR = Path("data/raw")

_CHUNK = 1 << 20


def cache_dir(override: Path | None = None) -> Path:
    if override is not None:
        path = Path(override)
    elif env := os.environ.get(CACHE_DIR_ENV):
        path = Path(env)
    else:
        path = DEFAULT_CACHE_DIR
    path.mkdir(parents=True, exist_ok=True)
    return path


def md5sum(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(_CHUNK), b""):
            digest.update(block)
    return digest.hexdigest()


class ChecksumMismatch(RuntimeError):
    """A downloaded or cached file does not match its published checksum."""


def _verify(path: Path, expected_md5: str) -> None:
    actual = md5sum(path)
    if actual != expected_md5:
        raise ChecksumMismatch(
            f"{path}: expected md5 {expected_md5}, got {actual}. "
            "Delete the file and re-run to re-download."
        )


def _download_simple(url: str, dest: Path) -> None:
    tmp = dest.with_suffix(dest.suffix + ".part")
    with urllib.request.urlopen(url, timeout=300) as response, tmp.open("wb") as out:
        shutil.copyfileobj(response, out, length=_CHUNK)
    tmp.replace(dest)


def _download_ranged(url: str, dest: Path, workers: int = 16) -> None:
    """Download with parallel HTTP range requests.

    Zenodo throttles a single stream hard; 850 MB over one connection takes tens
    of minutes. Falls back to a plain download if the server will not serve
    ranges or does not report a length.
    """
    try:
        head = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(head, timeout=60) as response:
            size = int(response.headers["Content-Length"])
            ranges_ok = response.headers.get("Accept-Ranges", "").lower() == "bytes"
    except (KeyError, TypeError, OSError):
        size, ranges_ok = 0, False

    if not ranges_ok or size <= 0:
        _download_simple(url, dest)
        return

    tmp = dest.with_suffix(dest.suffix + ".part")
    with tmp.open("wb") as handle:
        handle.truncate(size)

    step = -(-size // workers)
    spans = [(i * step, min((i + 1) * step, size) - 1) for i in range(workers)]
    spans = [(start, end) for start, end in spans if start <= end]

    def fetch(span: tuple[int, int]) -> None:
        start, end = span
        last: Exception | None = None
        for _ in range(5):
            try:
                request = urllib.request.Request(
                    url, headers={"Range": f"bytes={start}-{end}"}
                )
                with urllib.request.urlopen(request, timeout=900) as response:
                    payload = response.read()
                if len(payload) != end - start + 1:
                    raise OSError(f"short read for bytes {start}-{end}")
                with tmp.open("r+b") as handle:
                    handle.seek(start)
                    handle.write(payload)
                return
            except OSError as error:  # transient network failure
                last = error
        raise OSError(f"failed to fetch bytes {start}-{end}") from last

    with futures.ThreadPoolExecutor(workers) as pool:
        for _ in pool.map(fetch, spans):
            pass
    tmp.replace(dest)


def ensure_file(url: str, dest: Path, expected_md5: str, *, parallel: bool) -> Path:
    """Return ``dest``, downloading it first unless a valid copy already exists."""
    if dest.exists():
        try:
            _verify(dest, expected_md5)
            return dest
        except ChecksumMismatch:
            dest.unlink()

    dest.parent.mkdir(parents=True, exist_ok=True)
    if parallel:
        _download_ranged(url, dest)
    else:
        _download_simple(url, dest)
    _verify(dest, expected_md5)
    return dest


def connectivity_path(cache: Path | None = None) -> Path:
    """Path to the verified v783 proofread connection table (downloads if needed)."""
    directory = cache_dir(cache)
    return ensure_file(
        CONNECTIVITY.url,
        directory / CONNECTIVITY.filename,
        CONNECTIVITY.md5,
        parallel=True,
    )


def annotations_path(release: AnnotationRelease, cache: Path | None = None) -> Path:
    """Path to the verified neuron annotation table (downloads if needed)."""
    directory = cache_dir(cache)
    return ensure_file(
        release.url,
        directory / release.cache_name,
        release.md5,
        parallel=False,
    )
