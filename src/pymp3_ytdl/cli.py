"""CLI entry point for pymp3-ytdl."""

import argparse
import sys
from typing import Optional, Sequence

from .config import DEFAULT_OUTPUT_DIRECTORY, RenameOptions
from .downloader import download_mp3_from_urls
from .io_utils import read_url_list
from .logging_utils import setup_logging


def build_parser() -> argparse.ArgumentParser:
    """Create and configure the CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="Download MP3s from URLs with metadata and cover art.",
    )
    parser.add_argument(
        "url_list_file",
        help="Path to the text file containing URLs (one URL per line).",
    )
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIRECTORY,
        help="Output directory for MP3 files (default: downloaded_music).",
    )
    parser.add_argument(
        "--loglevel",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Set logging level (default: INFO).",
    )
    parser.add_argument(
        "--custom-rename",
        action="store_true",
        help="Rename files after download based on title metadata.",
    )
    parser.add_argument(
        "--restricted-filenames",
        action="store_true",
        help="Use stricter filename sanitization (mostly ASCII-safe).",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Run CLI and return process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)

    logger = setup_logging(args.loglevel)

    urls = read_url_list(args.url_list_file, logger=logger)
    if not urls:
        logger.error("No URLs to process. Exiting.")
        return 1

    rename_options = RenameOptions(
        enabled=args.custom_rename,
        restricted_filenames=args.restricted_filenames,
    )

    summary = download_mp3_from_urls(
        urls=urls,
        logger=logger,
        output_dir=args.output_dir,
        rename_options=rename_options,
    )

    return 0 if summary.successful_downloads > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
