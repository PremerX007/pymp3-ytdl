#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Downloads MP3 audio from a list of URLs (e.g., YouTube videos),
sets metadata (title, artist), and embeds the video thumbnail as cover art.
Files are saved to a specified output directory.

This version uses Python's logging module for output and attempts to get the
final filepath directly from yt-dlp's info_dict after download and conversion.
It also converts WebP thumbnails to JPEG for better compatibility.

Dependencies:
- yt-dlp: For downloading and extracting audio.
- mutagen: For MP3 metadata manipulation.
- requests: For downloading thumbnails.
- Pillow: For image format conversion (e.g., WebP to JPEG).
- ffmpeg: Must be installed and in the system PATH (for yt-dlp audio extraction).

Usage:
python this_script_name.py list_of_urls.txt [--loglevel DEBUG]

Default log level is INFO. Use --loglevel DEBUG for verbose output.
"""

import argparse
import io
import logging
import os
import shutil
import sys

import requests
import yt_dlp
from mutagen.easyid3 import EasyID3
from mutagen.id3 import APIC, ID3, ID3NoHeaderError
from mutagen.mp3 import MP3
from PIL import Image
from yt_dlp.utils import sanitize_filename as ydlp_sanitize_filename

# --- Configuration ---
OUTPUT_DIRECTORY_NAME = "downloaded_music"

# Option 1: Single flag for custom renaming
PERFORM_CUSTOM_RENAMING = (
    False  # True to enable custom renaming, False to keep yt-dlp's name
)

# Option 2: More granular control if PERFORM_CUSTOM_RENAMING is True
# This only takes effect if PERFORM_CUSTOM_RENAMING is True
# True: Use yt-dlp's strict sanitization (removes most non-ASCII)
# False: Use yt-dlp's less strict sanitization (tries to keep Unicode like Thai)
SANITIZE_WITH_RESTRICTED_MODE = (
    False  # Default to False for keep Thai character (not maximum safety)
)

# --- Setup Logging ---
# Create a logger instance
logger = logging.getLogger(__name__)  # Using __name__ is a common practice


def setup_logging(loglevel_str: str = "INFO"):
    """Sets up basic stream logging."""
    loglevel = getattr(logging, loglevel_str.upper(), logging.INFO)
    logger.setLevel(loglevel)

    # Create a handler for console output
    console_handler = logging.StreamHandler(
        sys.stdout
    )  # Use sys.stdout for normal output

    # Create a formatter
    # For INFO level, we want a simpler format. For DEBUG, more detailed.
    if loglevel <= logging.INFO:
        # Simpler format for INFO and WARNING, ERROR, CRITICAL
        # Example: [1/33] Processing URL: ...
        # Example: INFO: Created output directory: ...
        # We'll handle the [x/y] part manually in the loop for INFO.
        # Other INFO messages will just be the message.
        formatter = logging.Formatter("%(message)s")
    else:  # DEBUG level
        formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s"
        )

    console_handler.setFormatter(formatter)

    # Add the handler to the logger
    # Remove existing handlers to prevent duplicate messages if setup_logging is called multiple times
    if logger.hasHandlers():
        logger.handlers.clear()
    logger.addHandler(console_handler)

    # Integrate yt-dlp's logging with our logger if desired (optional, can be verbose)
    # This makes yt-dlp's own messages (like [youtube] Extracting URL...) use our logger settings.
    # ydlp_logger = logging.getLogger('yt_dlp')
    # ydlp_logger.setLevel(loglevel) # Match our loglevel
    # if not ydlp_logger.hasHandlers(): # Add handler only if yt-dlp hasn't configured its own
    #     ydlp_logger.addHandler(console_handler) # Use the same console handler
    # Alternatively, to silence yt-dlp's default console output if quiet=True in opts:
    # if current_ydl_opts.get('quiet'):
    #     ydlp_logger.addHandler(logging.NullHandler())


# --- Helper Functions ---
def read_url_list(file_path: str) -> list[str] | None:
    """Reads a list of URLs from a text file."""
    if not os.path.isfile(file_path):
        logger.error(f"URL file not found: {file_path}")
        return None  # Return None instead of sys.exit to allow main to handle
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            urls = [line.strip() for line in f if line.strip()]
            if not urls:
                logger.error(
                    f"The URL file '{file_path}' is empty or contains only blank lines."
                )
                return None
            return urls
    except Exception as e:
        logger.error(f"Failed to read URL file '{file_path}': {e}")
        return None


def apply_metadata_and_cover(
    mp3_filepath: str, title: str, artist: str, thumbnail_url: str | None = None
) -> None:
    """Applies title, artist, and cover art metadata to an MP3 file."""
    if not os.path.exists(mp3_filepath):
        logger.error(
            f"  (apply_metadata): MP3 file not found at '{mp3_filepath}'. Cannot apply metadata."
        )
        return
    try:
        logger.debug(f"  Attempting to apply metadata to: {mp3_filepath}")
        try:
            audio = EasyID3(mp3_filepath)
        except ID3NoHeaderError:
            logger.debug(f"  No ID3 header in {mp3_filepath}, creating one.")
            audio_mp3 = MP3(mp3_filepath)
            if audio_mp3.tags is None:
                audio_mp3.add_tags()
                audio_mp3.save()
            audio = EasyID3(mp3_filepath)

        audio["title"] = title
        audio["artist"] = artist
        audio.save()
        logger.debug(
            f"  Set metadata: title='{title}', artist='{artist}' for '{os.path.basename(mp3_filepath)}'"
        )

        if thumbnail_url:
            logger.debug(f"  Processing thumbnail from URL: {thumbnail_url}")
            try:
                response = requests.get(thumbnail_url, timeout=15)
                response.raise_for_status()
                image_data = response.content
                original_mime_type = response.headers.get(
                    "Content-Type", "image/jpeg"
                ).lower()
                logger.debug(f"  Original thumbnail MIME type: {original_mime_type}")

                final_image_data = image_data
                final_mime_type = original_mime_type

                if original_mime_type == "image/webp":
                    logger.debug("  Attempting to convert WEBP thumbnail to JPEG...")
                    try:
                        img = Image.open(io.BytesIO(image_data))
                        if img.mode == "RGBA" or img.mode == "P" or img.mode == "LA":
                            logger.debug(
                                f"  Image mode is {img.mode}, converting to RGB for JPEG."
                            )
                            img = img.convert("RGB")

                        output_buffer = io.BytesIO()
                        img.save(output_buffer, format="JPEG", quality=90)
                        final_image_data = output_buffer.getvalue()
                        final_mime_type = "image/jpeg"
                        logger.debug("  WEBP successfully converted to JPEG.")
                    except Exception as e_conv:
                        logger.warning(
                            f"  Failed to convert WEBP to JPEG: {e_conv}. Trying to embed original WebP."
                        )

                audio_full = ID3(mp3_filepath)
                audio_full.delall("APIC")
                audio_full.add(
                    APIC(
                        encoding=3,
                        mime=final_mime_type,
                        type=3,
                        desc="Cover",
                        data=final_image_data,
                    )
                )
                audio_full.save(v2_version=3)
                logger.debug(
                    f"  Embedded cover art (mime: {final_mime_type}) into '{os.path.basename(mp3_filepath)}'"
                )
            except requests.RequestException as e_req:
                logger.warning(
                    f"  Could not download thumbnail from {thumbnail_url}: {e_req}"
                )
            except Exception as e_cover:
                logger.warning(
                    f"  Could not embed cover art for '{os.path.basename(mp3_filepath)}': {e_cover}"
                )
    except Exception as e:
        logger.error(
            f"  Failed to set metadata for '{os.path.basename(mp3_filepath)}': {e}",
            exc_info=True if logger.isEnabledFor(logging.DEBUG) else False,
        )


# --- Main Download Function ---
def download_mp3_from_urls(
    urls: list[str], output_dir: str = OUTPUT_DIRECTORY_NAME
) -> None:
    """Downloads MP3s, applies metadata, using Python's logging."""
    if not os.path.exists(output_dir):
        try:
            os.makedirs(output_dir)
            logger.info(f"Created output directory: {output_dir}")
        except OSError as e:
            logger.error(f"Could not create output directory '{output_dir}': {e}")
            # No sys.exit here, main will handle based on return or an exception
            raise  # Re-raise the exception to be caught by main or stop execution

    # yt-dlp options
    # If logger is set to INFO or higher, make yt-dlp quieter.
    # If logger is DEBUG, let yt-dlp be verbose.
    ydl_quiet_mode = not logger.isEnabledFor(logging.DEBUG)

    ydl_opts_base = {
        "format": "bestaudio/best",
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],
        "outtmpl": {"default": os.path.join(output_dir, "%(title)s.%(ext)s")},
        "noplaylist": True,
        "quiet": ydl_quiet_mode,  # Control yt-dlp's verbosity based on our log level
        "ignoreerrors": "only_download",
        "writethumbnail": False,
        "logger": logger
        if logger.isEnabledFor(logging.DEBUG)
        else None,  # Pass our logger to yt-dlp for its messages IF we are in DEBUG
    }

    download_count = 0
    total_urls = len(urls)

    logger.info(f"Starting download process for {total_urls} URL(s)...")
    logger.info(f"Output directory: {os.path.abspath(output_dir)}")

    for i, url in enumerate(urls, 1):
        # Custom INFO log for progress
        logger.info(f"[{i}/{total_urls}] Processing URL: {url}")

        final_info_dict = None

        try:
            current_ydl_opts = ydl_opts_base.copy()
            with yt_dlp.YoutubeDL(current_ydl_opts) as ydl:
                logger.debug(f"  Extracting info and downloading for URL: {url}")
                final_info_dict = ydl.extract_info(url, download=True)

                if final_info_dict:
                    downloaded_mp3_path = final_info_dict.get("filepath")
                    if (
                        not downloaded_mp3_path
                        or not downloaded_mp3_path.lower().endswith(".mp3")
                    ):
                        if final_info_dict.get("requested_downloads"):
                            for dl_info in final_info_dict["requested_downloads"]:
                                if dl_info.get("filepath") and dl_info[
                                    "filepath"
                                ].lower().endswith(".mp3"):
                                    downloaded_mp3_path = dl_info["filepath"]
                                    logger.debug(
                                        f"  Found MP3 path in requested_downloads: {downloaded_mp3_path}"
                                    )
                                    break

                    if (
                        downloaded_mp3_path
                        and os.path.exists(downloaded_mp3_path)
                        and downloaded_mp3_path.lower().endswith(".mp3")
                    ):
                        logger.info(
                            f"  Download and conversion successful. Final file: '{os.path.basename(downloaded_mp3_path)}'"
                        )
                        download_count += 1

                        title_for_metadata = (
                            final_info_dict.get("track")
                            or final_info_dict.get("title", "Unknown Title")
                        ).strip() or "Unknown Title"
                        artist_for_metadata = (
                            final_info_dict.get("artist")
                            or final_info_dict.get("uploader", "Unknown Artist")
                        ).strip() or "Unknown Artist"
                        thumbnail_url = final_info_dict.get("thumbnail")
                        logger.debug(
                            f"  Metadata extracted: Title='{title_for_metadata}', Artist='{artist_for_metadata}', Thumbnail='{thumbnail_url is not None}'"
                        )

                        final_path_for_metadata = downloaded_mp3_path
                        if PERFORM_CUSTOM_RENAMING:
                            logger.debug(
                                f"  Attempting custom renaming for: {os.path.basename(downloaded_mp3_path)}"
                            )
                            # Apply sanitization based on SANITIZE_WITH_RESTRICTED_MODE
                            if SANITIZE_WITH_RESTRICTED_MODE:
                                logger.debug(
                                    "    Using sanitize_filename with restricted=True"
                                )
                                desired_filename_base = ydlp_sanitize_filename(
                                    title_for_metadata, restricted=True
                                )
                            else:
                                logger.debug(
                                    "    Using sanitize_filename with restricted=False"
                                )
                                desired_filename_base = ydlp_sanitize_filename(
                                    title_for_metadata, restricted=False
                                )

                            desired_filename_mp3 = f"{desired_filename_base}.mp3"
                            desired_filepath_mp3 = os.path.join(
                                os.path.dirname(downloaded_mp3_path),
                                desired_filename_mp3,
                            )

                            if downloaded_mp3_path != desired_filepath_mp3:
                                if os.path.exists(desired_filepath_mp3):
                                    logger.warning(
                                        f"  (Rename): Target file '{desired_filename_mp3}' already exists. Not renaming."
                                    )
                                else:
                                    try:
                                        logger.info(
                                            f"  Renaming '{os.path.basename(downloaded_mp3_path)}' to '{desired_filename_mp3}'"
                                        )
                                        shutil.move(
                                            downloaded_mp3_path, desired_filepath_mp3
                                        )
                                        final_path_for_metadata = desired_filepath_mp3
                                    except OSError as e_rename:
                                        logger.error(
                                            f"  (Rename): Could not rename file: {e_rename}."
                                        )
                        else:
                            logger.debug(
                                f"  Skipping custom renaming. Using filename from yt-dlp: '{os.path.basename(downloaded_mp3_path)}'"
                            )

                        apply_metadata_and_cover(
                            final_path_for_metadata,
                            title_for_metadata,
                            artist_for_metadata,
                            thumbnail_url,
                        )
                    else:
                        logger.error(
                            f"  Could not reliably locate the final MP3 file path from yt-dlp's output for URL {url}."
                        )
                        if downloaded_mp3_path:
                            logger.debug(
                                f"    Last known path: '{downloaded_mp3_path}', Exists: {os.path.exists(downloaded_mp3_path)}"
                            )
                        logger.debug(
                            f"    Final info dict from yt-dlp was: filepath='{final_info_dict.get('filepath', 'N/A')}', "
                            f"requested_downloads='{final_info_dict.get('requested_downloads', 'N/A')}'"
                        )
                else:
                    logger.warning(
                        f"  yt-dlp's extract_info (with download) did not return sufficient information for {url}."
                    )

        except yt_dlp.utils.DownloadError as e_dl:
            logger.error(f"  DownloadError during processing {url}: {e_dl}")
        except Exception as e:
            logger.error(
                f"  An unexpected error occurred while processing {url}: {e}",
                exc_info=True if logger.isEnabledFor(logging.DEBUG) else False,
            )

    logger.info("\n--- Download Process Finished ---")  # Add newline for separation
    if download_count > 0:
        logger.info(
            f"Successfully attempted to download and process {download_count} out of {total_urls} item(s)."
        )
    else:
        logger.info("No items were successfully downloaded or processed.")
    logger.info(f"Files are located in: {os.path.abspath(output_dir)}")


# --- Main Execution ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Download MP3s from a list of URLs with metadata and cover art."
    )
    parser.add_argument(
        "url_list_file",
        help="Path to the text file containing URLs (one URL per line).",
    )
    parser.add_argument(
        "--loglevel",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Set the logging level (default: INFO).",
    )
    args = parser.parse_args()

    # Setup logging based on command-line argument or default
    setup_logging(args.loglevel)

    logger.debug("Script started with arguments: %s", args)

    urls_to_download = read_url_list(args.url_list_file)

    if urls_to_download:
        try:
            download_mp3_from_urls(urls_to_download, OUTPUT_DIRECTORY_NAME)
        except Exception as e:
            logger.critical(
                f"A critical error occurred in download_mp3_from_urls: {e}",
                exc_info=True,
            )
            sys.exit(
                1
            )  # Exit with error code if main download function fails critically
    else:
        logger.error("No URLs to process. Exiting.")
        sys.exit(1)  # Exit with error code if no URLs

    logger.info("Script finished successfully.")
