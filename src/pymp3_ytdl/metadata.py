"""ID3 metadata and cover art helpers."""

import io
import logging
import os
import re
from typing import Any, Mapping, Optional, Tuple

import requests
from mutagen.easyid3 import EasyID3
from mutagen.id3 import APIC, ID3, ID3NoHeaderError
from mutagen.mp3 import MP3
from PIL import Image


def extract_song_metadata(
    info_dict: Mapping[str, Any],
    logger: logging.Logger,
) -> Tuple[str, str]:
    """Extract song metadata with a 3-tier fallback strategy.

    Tier 1: yt-dlp official fields (`track` + `artist`).
    Tier 2: try to cleaned up from video title.
    Tier 3: fallback to YouTube title + uploader.
    """
    # Tier 1: yt-dlp official music metadata.
    track = str(info_dict.get("track") or "").strip()
    artist = str(info_dict.get("artist") or "").strip()
    if track and artist:
        logger.debug("  Metadata tier 1 hit: yt-dlp track/artist fields.")
        return track, artist

    raw_title = str(info_dict.get("title") or "").strip()
    uploader = str(info_dict.get("uploader") or "").strip()

    # Tier 2: raw title cleaned up
    cleaned_title = _cleanup_title(raw_title)
    if cleaned_title:
        return cleaned_title, uploader or "Unknown Artist"

    # Tier 3: ultimate fallback to plain YouTube metadata.
    logger.debug("  Metadata tier 3 fallback: YouTube title/uploader fields.")
    return raw_title or "Unknown Title", uploader or "Unknown Artist"


def _cleanup_title(raw_title: str) -> str:
    """Remove common YouTube noise."""
    cleaned = raw_title

    cleaned = re.split(r"(?i)(\bOST\b\.?|\bO\.S\.T\.\b)", cleaned)[0]
    cleaned = re.sub(r"[\(\[\{【「].*?[\)\]\}】」]", " ", cleaned)
    cleaned = re.sub(
        r"\b(official\s*(music\s*)?(video|mv|audio)|lyrics?|lyric\s*video|live\s+(performance|session))\b",
        " ",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.split(r"[|:]", cleaned)[0]
    cleaned = re.sub(r"[^\w\s\-\u0E00-\u0E7F&,\']", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)

    return cleaned.strip()


def apply_metadata_and_cover(
    mp3_filepath: str,
    title: str,
    artist: str,
    logger: logging.Logger,
    thumbnail_url: Optional[str] = None,
) -> None:
    """Apply title/artist tags and optional thumbnail cover art to an MP3 file."""
    if not os.path.exists(mp3_filepath):
        logger.error(
            "  (apply_metadata): MP3 file not found at '%s'. Cannot apply metadata.",
            mp3_filepath,
        )
        return

    try:
        logger.debug("  Applying metadata to: %s", mp3_filepath)
        try:
            audio = EasyID3(mp3_filepath)
        except ID3NoHeaderError:
            logger.debug("  No ID3 header in %s, creating one.", mp3_filepath)
            audio_mp3 = MP3(mp3_filepath)
            if audio_mp3.tags is None:
                audio_mp3.add_tags()
                audio_mp3.save()
            audio = EasyID3(mp3_filepath)

        audio["title"] = title
        audio["artist"] = artist
        audio.save()

        if thumbnail_url:
            _embed_cover_art(mp3_filepath, thumbnail_url, logger)
    except Exception as exc:  # pylint: disable=broad-except
        logger.error(
            "  Failed to set metadata for '%s': %s", os.path.basename(mp3_filepath), exc
        )


def _embed_cover_art(
    mp3_filepath: str, thumbnail_url: str, logger: logging.Logger
) -> None:
    """Download thumbnail and embed it as APIC cover art frame."""
    try:
        response = requests.get(thumbnail_url, timeout=15)
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.warning("  Could not download thumbnail from %s: %s", thumbnail_url, exc)
        return

    image_data = response.content
    original_mime_type = response.headers.get("Content-Type", "image/jpeg").lower()
    final_image_data = image_data
    final_mime_type = original_mime_type

    if original_mime_type == "image/webp":
        try:
            img = Image.open(io.BytesIO(image_data))
            if img.mode in {"RGBA", "P", "LA"}:
                img = img.convert("RGB")
            output_buffer = io.BytesIO()
            img.save(output_buffer, format="JPEG", quality=90)
            final_image_data = output_buffer.getvalue()
            final_mime_type = "image/jpeg"
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning(
                "  Failed to convert WEBP to JPEG: %s. Embedding original WebP.",
                exc,
            )

    try:
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
            "  Embedded cover art (mime: %s) into '%s'",
            final_mime_type,
            os.path.basename(mp3_filepath),
        )
    except Exception as exc:  # pylint: disable=broad-except
        logger.warning(
            "  Could not embed cover art for '%s': %s",
            os.path.basename(mp3_filepath),
            exc,
        )
