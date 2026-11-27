"""Non-blocking single-key input for the CLI."""

import os
import sys
import time


class KeyReader:
    """Non-blocking single-key reader used while the agent is working
    (so the user can press `t` or `s` without hitting Enter)."""

    def __init__(self):
        self.enabled = sys.stdin.isatty()
        self._windows = os.name == "nt"
        self._old = None
        self._fd = None

    def __enter__(self):
        if self.enabled and not self._windows:
            import termios
            import tty

            self._fd = sys.stdin.fileno()
            self._old = termios.tcgetattr(self._fd)
            tty.setcbreak(self._fd)  # Ctrl+C still works
        return self

    def __exit__(self, *exc):
        if self._old is not None:
            import termios

            termios.tcsetattr(self._fd, termios.TCSADRAIN, self._old)
        return False

    def poll(self, timeout: float = 0.1):
        if not self.enabled:
            time.sleep(timeout)
            return None
        if self._windows:
            import msvcrt

            end = time.time() + timeout
            while time.time() < end:
                if msvcrt.kbhit():
                    return msvcrt.getwch()
                time.sleep(0.02)
            return None
        import select

        ready, _, _ = select.select([self._fd], [], [], timeout)
        if ready:
            return os.read(self._fd, 1).decode(errors="ignore")
        return None
