"""Configuration models and defaults."""

from dataclasses import dataclass

DEFAULT_OUTPUT_DIRECTORY = "downloaded_music"


@dataclass(frozen=True)
class RenameOptions:
    """Controls optional post-download file renaming behavior."""

    enabled: bool = False
    restricted_filenames: bool = False
