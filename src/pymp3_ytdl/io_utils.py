"""Input/output helpers."""

import logging
import os
from typing import List, Optional


def read_url_list(file_path: str, logger: logging.Logger) -> Optional[List[str]]:
    """Read non-empty URL lines from a UTF-8 text file."""
    if not os.path.isfile(file_path):
        logger.error("URL file not found: %s", file_path)
        return None

    try:
        with open(file_path, "r", encoding="utf-8") as handle:
            urls = [line.strip() for line in handle if line.strip()]
    except OSError as exc:
        logger.error("Failed to read URL file '%s': %s", file_path, exc)
        return None

    if not urls:
        logger.error(
            "The URL file '%s' is empty or contains only blank lines.", file_path
        )
        return None

    return urls
