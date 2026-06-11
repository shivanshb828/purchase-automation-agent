"""
Logging configuration using the Rich library for pretty, color-coded console output
that doubles as the visual narration layer during the live demo.
"""
# TODO: Implement get_logger(name: str) -> logging.Logger configured with RichHandler

import logging
from rich.logging import RichHandler
from config import APP


def get_logger(name: str) -> logging.Logger:
    logging.basicConfig(
        level=getattr(logging, APP.log_level, logging.INFO),
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(rich_tracebacks=True)],
    )
    return logging.getLogger(name)
