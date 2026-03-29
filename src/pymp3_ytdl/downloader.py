"""Core download orchestration built on yt-dlp."""

import logging
import os
import shutil
from dataclasses import dataclass
from typing import Any, Dict, Optional, Sequence

import imageio_ffmpeg
import yt_dlp
from yt_dlp.utils import sanitize_filename as ydlp_sanitize_filename

from .config import DEFAULT_OUTPUT_DIRECTORY, RenameOptions
from .metadata import apply_metadata_and_cover, extract_song_metadata


@dataclass(frozen=True)
class DownloadSummary:
    """Result of a multi-URL download run."""

    total_urls: int
    successful_downloads: int
    output_dir: str


def download_mp3_from_urls(
    urls: Sequence[str],
    logger: logging.Logger,
    output_dir: str = DEFAULT_OUTPUT_DIRECTORY,
    rename_options: Optional[RenameOptions] = None,
) -> DownloadSummary:
    """Download MP3s from URLs, apply metadata, and optionally rename files."""
    if rename_options is None:
        rename_options = RenameOptions()

    _ensure_output_dir(output_dir)
    ffmpeg_executable = imageio_ffmpeg.get_ffmpeg_exe()

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
        "ignoreerrors": "only_download",
        "writethumbnail": False,
        "quiet": not logger.isEnabledFor(logging.DEBUG),
        "logger": logger if logger.isEnabledFor(logging.DEBUG) else None,
        "ffmpeg_location": ffmpeg_executable,
    }

    total_urls = len(urls)
    successful_downloads = 0

    logger.info("Starting download process for %s URL(s)...", total_urls)
    logger.info("Output directory: %s", os.path.abspath(output_dir))
    logger.debug(
        "Using bundled FFmpeg binary from imageio-ffmpeg: %s", ffmpeg_executable
    )

    for index, url in enumerate(urls, 1):
        logger.info("[%s/%s] Processing URL: %s", index, total_urls, url)

        try:
            with yt_dlp.YoutubeDL(ydl_opts_base.copy()) as ydl:
                info = ydl.extract_info(url, download=True)
        except yt_dlp.utils.DownloadError as exc:
            logger.error("  DownloadError during processing %s: %s", url, exc)
            continue
        except Exception as exc:  # pylint: disable=broad-except
            logger.error("  Unexpected error while processing %s: %s", url, exc)
            continue

        if not info:
            logger.warning("  yt-dlp did not return metadata for %s.", url)
            continue

        downloaded_mp3_path = _resolve_downloaded_mp3_path(info)
        if not downloaded_mp3_path or not os.path.exists(downloaded_mp3_path):
            logger.error("  Could not locate final MP3 output for URL: %s", url)
            continue

        logger.info(
            "  Download and conversion successful. Final file: '%s'",
            os.path.basename(downloaded_mp3_path),
        )
        successful_downloads += 1

        title, artist = extract_song_metadata(info, logger)
        thumbnail_url = info.get("thumbnail")

        final_path = _rename_if_enabled(
            downloaded_mp3_path,
            title,
            rename_options,
            logger,
        )

        apply_metadata_and_cover(
            mp3_filepath=final_path,
            title=title,
            artist=artist,
            thumbnail_url=thumbnail_url,
            logger=logger,
        )

    logger.info("\n--- Download Process Finished ---")
    if successful_downloads > 0:
        logger.info(
            "Successfully processed %s out of %s item(s).",
            successful_downloads,
            total_urls,
        )
    else:
        logger.info("No items were successfully downloaded or processed.")
    logger.info("Files are located in: %s", os.path.abspath(output_dir))

    return DownloadSummary(
        total_urls=total_urls,
        successful_downloads=successful_downloads,
        output_dir=os.path.abspath(output_dir),
    )


def _ensure_output_dir(output_dir: str) -> None:
    """Create output directory if needed."""
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)


def _resolve_downloaded_mp3_path(info: Dict[str, Any]) -> Optional[str]:
    """Find best MP3 filepath candidate from yt-dlp result payload."""
    path = info.get("filepath")
    if path and str(path).lower().endswith(".mp3"):
        return path

    requested_downloads = info.get("requested_downloads") or []
    for item in requested_downloads:
        candidate = item.get("filepath")
        if candidate and str(candidate).lower().endswith(".mp3"):
            return candidate

    return None


def _rename_if_enabled(
    downloaded_mp3_path: str,
    title_for_filename: str,
    options: RenameOptions,
    logger: logging.Logger,
) -> str:
    """Optionally rename the MP3 using sanitized title metadata."""
    if not options.enabled:
        return downloaded_mp3_path

    desired_basename = ydlp_sanitize_filename(
        title_for_filename,
        restricted=options.restricted_filenames,
    )
    desired_filename = "{0}.mp3".format(desired_basename)
    desired_path = os.path.join(os.path.dirname(downloaded_mp3_path), desired_filename)

    if desired_path == downloaded_mp3_path:
        return downloaded_mp3_path

    if os.path.exists(desired_path):
        logger.warning(
            "  (Rename): Target file '%s' already exists. Keeping original filename.",
            desired_filename,
        )
        return downloaded_mp3_path

    try:
        logger.info(
            "  Renaming '%s' to '%s'",
            os.path.basename(downloaded_mp3_path),
            desired_filename,
        )
        shutil.move(downloaded_mp3_path, desired_path)
        return desired_path
    except OSError as exc:
        logger.error("  (Rename): Could not rename file: %s", exc)
        return downloaded_mp3_path
