"""Logging setup for CLI and library usage."""

import logging
import sys


def setup_logging(loglevel_str: str = "INFO") -> logging.Logger:
    """Configure and return the package logger."""
    logger = logging.getLogger("pymp3_ytdl")
    loglevel = getattr(logging, loglevel_str.upper(), logging.INFO)
    logger.setLevel(loglevel)

    handler = logging.StreamHandler(sys.stdout)
    if loglevel <= logging.INFO:
        formatter = logging.Formatter("%(message)s")
    else:
        formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s"
        )
    handler.setFormatter(formatter)

    if logger.hasHandlers():
        logger.handlers.clear()
    logger.addHandler(handler)
    logger.propagate = False

    return logger
