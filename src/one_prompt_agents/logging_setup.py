# logging_setup.py
from __future__ import annotations
import logging, sys
from pathlib import Path
from datetime import datetime
from typing import Final


import io, sys, logging

class StreamToLogger(io.TextIOBase):
    """
    Proxy for sys.stdout / sys.stderr that logs every line while still
    behaving like a normal text stream.
    """
    def __init__(self, target_stream: io.TextIOBase,
                 logger: logging.Logger, level: int):
        self._stream = target_stream     # original stdout / stderr
        self._logger = logger
        self._level  = level
        self._buf    = ""

    # -------- required write/flush --------
    def write(self, s: str) -> int:
        n = self._stream.write(s)        # keep console output
        self._stream.flush()

        self._buf += s
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            if line:
                self._logger.log(self._level, line)
        return n                         # returning an int matters!

    def flush(self) -> None:
        if self._buf:
            self._logger.log(self._level, self._buf.rstrip())
            self._buf = ""
        self._stream.flush()

    # -------- proxy everything else --------
    def __getattr__(self, name):         # encoding, fileno, isatty, etc.
        return getattr(self._stream, name)



LOG_DIR: Final = Path("logs")               # ➊ where logs live
LOG_FORMAT: Final = "%(asctime)s %(levelname)-8s [%(name)s] %(message)s"
DATE_FORMAT:  Final = "%Y-%m-%d %H:%M:%S"



def setup_logging(capture_stdio: bool = False) -> Path:
    """Configure root logger and (optionally) funnel stdout / stderr into it.
    
    Returns
    -------
    Path
        The path of the log file that was created.
    """
    # ➋ build unique file name once per run
    LOG_DIR.mkdir(exist_ok=True)
    timestamp  = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path   = LOG_DIR / f"run_{timestamp}.log"

    # ➌ create handlers
    file_handler    = logging.FileHandler(log_path, mode="w", encoding="utf-8")
    console_handler = logging.StreamHandler()        # defaults to stderr

    for h in (file_handler, console_handler):
        h.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))

    # ➍ wire them into the root logger
    logging.basicConfig(
        level=logging.DEBUG,            # or INFO / WARNING, etc.
        handlers=[file_handler,console_handler],
        force=True                      # clobber any earlier basicConfig()
    )

    if capture_stdio:
        root = logging.getLogger()
        sys.stdout = StreamToLogger(sys.__stdout__, root, logging.INFO)
        sys.stderr = StreamToLogger(sys.__stderr__, root, logging.ERROR)

    return log_path
