from __future__ import annotations

import logging
import logging.handlers
import queue
from pathlib import Path
from typing import Optional

_LOGGER_NAME = "lanibombers"

_log_queue: queue.Queue[logging.LogRecord] = queue.Queue()
_listener: Optional[logging.handlers.QueueListener] = None


def setup_logger(
    log_path: str = "logs/server.log",
    level: int = logging.INFO,
    console: bool = False,
) -> logging.Logger:
    global _listener

    logger = logging.getLogger(_LOGGER_NAME)

    if logger.handlers:
        return logger

    logger.setLevel(level)
    logger.propagate = False

    Path(log_path).parent.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(threadName)s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)

    handlers: list[logging.Handler] = [file_handler]

    if console:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        handlers.append(console_handler)

    queue_handler = logging.handlers.QueueHandler(_log_queue)
    queue_handler.setLevel(level)

    logger.addHandler(queue_handler)

    _listener = logging.handlers.QueueListener(
        _log_queue,
        *handlers,
        respect_handler_level=True,
    )
    _listener.start()

    return logger


def get_logger() -> logging.Logger:
    return logging.getLogger(_LOGGER_NAME)


def stop_logger() -> None:
    global _listener

    if _listener is not None:
        _listener.stop()
        _listener = None
