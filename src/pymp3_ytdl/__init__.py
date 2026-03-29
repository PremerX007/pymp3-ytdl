"""pymp3_ytdl package."""

from .downloader import DownloadSummary, download_mp3_from_urls

__all__ = ["download_mp3_from_urls", "DownloadSummary"]
__version__ = "0.1.0"
