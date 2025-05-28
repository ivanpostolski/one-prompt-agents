# logging_setup.py
from __future__ import annotations
import logging, sys
from pathlib import Path
from datetime import datetime
from typing import Final, Optional


import io, sys, logging

class StreamToLogger(io.TextIOBase):
    """A proxy class that redirects `sys.stdout` or `sys.stderr` to a logger.

    This allows capturing all standard output and standard error streams into
    the logging system, while still allowing the original streams to function
    (e.g., print to console).

    Each line written to the stream is logged at the specified logging level.

    Attributes:
        _stream (io.TextIOBase): The original stream (e.g., `sys.__stdout__`).
        _logger (logging.Logger): The logger instance to which messages are sent.
        _level (int): The logging level for messages (e.g., `logging.INFO`).
        _buf (str): A buffer to accumulate partial lines before logging.
    """
    def __init__(self, target_stream: io.TextIOBase,
                 logger: logging.Logger, level: int):
        """Initializes the StreamToLogger.

        Args:
            target_stream (io.TextIOBase): The original stream to wrap (e.g., `sys.stdout`).
            logger (logging.Logger): The logger to redirect output to.
            level (int): The logging level to use for the redirected output.
        """
        self._stream = target_stream     # original stdout / stderr
        self._logger = logger
        self._level  = level
        self._buf    = ""

    # -------- required write/flush --------
    def write(self, s: str) -> int:
        """Writes a string to the original stream and logs it.

        The string `s` is written to the `_stream`. It is also buffered, and
        complete lines (ending with a newline) are logged using `_logger` at `_level`.

        Args:
            s (str): The string to write.

        Returns:
            int: The number of characters written (from `_stream.write`).
        """
        n = self._stream.write(s)        # keep console output
        self._stream.flush()

        self._buf += s
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            if line:
                self._logger.log(self._level, line)
        return n                         # returning an int matters!

    def flush(self) -> None:
        """Flushes the buffer and the original stream.

        Any content remaining in the internal buffer `_buf` is logged.
        Then, the original `_stream` is flushed.
        """
        if self._buf:
            self._logger.log(self._level, self._buf.rstrip())
            self._buf = ""
        self._stream.flush()

    # -------- proxy everything else --------
    def __getattr__(self, name):
        """Proxies attribute access to the original stream.

        This allows the `StreamToLogger` instance to behave like the original
        stream for attributes like `encoding`, `fileno`, `isatty`, etc.

        Args:
            name (str): The name of the attribute to access.

        Returns:
            Any: The attribute from the `_stream`.
        """
        return getattr(self._stream, name)



LOG_DIR: Final = Path("logs")               # ➊ where logs live
LOG_FORMAT: Final = "%(asctime)s %(levelname)-8s [%(name)s] %(message)s"
DATE_FORMAT:  Final = "%Y-%m-%d %H:%M:%S"



def setup_logging(log_to_file: bool = True, level: int = logging.INFO, capture_stdio: bool = False) -> Optional[Path]:
    """Configures the root logger and optionally redirects `stdout`/`stderr` to it.

    This function sets up logging with a console handler (writing to `stderr`).
    If `log_to_file` is True (default), it also sets up a file handler writing to a 
    timestamped log file in the `LOG_DIR`.
    It uses a predefined `LOG_FORMAT` and `DATE_FORMAT`.
    The overall logging level is set by the `level` argument.

    If `capture_stdio` is True, it replaces `sys.stdout` and `sys.stderr` with
    `StreamToLogger` instances, causing their output to be logged by the root logger
    at INFO and ERROR levels, respectively.

    Args:
        log_to_file (bool, optional): Whether to create and use a file handler for logging.
                                      Defaults to True.
        level (int, optional): The logging level for the root logger and console handler.
                               Defaults to `logging.INFO`.
        capture_stdio (bool, optional): Whether to redirect `stdout` and `stderr`
                                        to the logging system. Defaults to False.

    Returns:
        Optional[Path]: The path to the created log file if `log_to_file` is True, otherwise None.
    """
    handlers = []
    log_path: Optional[Path] = None

    if log_to_file:
        LOG_DIR.mkdir(exist_ok=True)
        timestamp  = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_path   = LOG_DIR / f"run_{timestamp}.log"
        file_handler = logging.FileHandler(log_path, mode="w", encoding="utf-8")
        file_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))
        handlers.append(file_handler)

    console_handler = logging.StreamHandler() # defaults to stderr
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))
    # Set console handler level to the general level, so it respects verbosity. 
    # The root logger level will be the ultimate gatekeeper.
    console_handler.setLevel(level) 
    handlers.append(console_handler)

    logging.basicConfig(
        level=level, # Use the passed level
        handlers=handlers,
        force=True # clobber any earlier basicConfig()
    )

    if capture_stdio:
        root = logging.getLogger()
        sys.stdout = StreamToLogger(sys.__stdout__, root, logging.INFO) # Or use level?
        sys.stderr = StreamToLogger(sys.__stderr__, root, logging.ERROR) # Or use level?

    return log_path
