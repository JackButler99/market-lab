"""OS-owned lock on the same disk as SQLite; released automatically on process exit."""

from contextlib import contextmanager


@contextmanager
def exclusive(path):
    handle = open(path, "a+b")
    try:
        if __import__("os").name == "nt":
            import msvcrt

            if handle.seek(0, 2) == 0:
                handle.write(b"0")
                handle.flush()
            handle.seek(0)
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                raise RuntimeError("Another process owns the database/scheduler lock") from None
        else:
            import fcntl

            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                raise RuntimeError("Another process owns the database/scheduler lock") from None
        yield
    finally:
        handle.close()
