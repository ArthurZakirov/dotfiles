"""Read consistent private SQLite snapshots without touching source sidecars."""
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time


class SnapshotConnection(sqlite3.Connection):
    def close(self):
        try:
            super().close()
        finally:
            self.snapshot.cleanup()


def _signature(path):
    try:
        stat = path.stat()
        return stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns
    except FileNotFoundError:
        return None


def open_snapshot(path: Path) -> sqlite3.Connection | None:
    """Copy DB and committed WAL together; SQLite rebuilds SHM only in scratch.

    Retry if the writer changed either file during capture. On macOS an APFS
    clone avoids copying large histories; other filesystems use a normal copy.
    """
    path = path.resolve()
    if not path.is_file():
        return None
    sources = [path, Path(str(path) + "-wal"), Path(str(path) + "-journal")]
    for attempt in range(4):
        scratch = tempfile.TemporaryDirectory(prefix="codex-history-")
        target = Path(scratch.name) / path.name
        before = [_signature(source) for source in sources]
        try:
            for source, signature in zip(sources, before):
                if signature is None:
                    continue
                destination = Path(scratch.name) / source.name
                cloned = False
                if sys.platform == "darwin":
                    cloned = subprocess.run(
                        ["/bin/cp", "-c", str(source), str(destination)],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                        check=False,
                    ).returncode == 0
                if not cloned:
                    shutil.copyfile(source, destination)
            if before != [_signature(source) for source in sources]:
                raise BlockingIOError("History changed during snapshot")
            connection = sqlite3.connect(target.as_uri() + "?mode=rw", uri=True,
                                         factory=SnapshotConnection)
            connection.snapshot = scratch
            connection.execute("PRAGMA query_only=ON")
            return connection
        except (FileNotFoundError, BlockingIOError):
            scratch.cleanup()
            if attempt == 3:
                raise RuntimeError("Codex history is changing too quickly to capture safely") from None
            time.sleep(0.05)
        except BaseException:
            scratch.cleanup()
            raise
