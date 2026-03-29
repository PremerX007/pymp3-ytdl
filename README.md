# pymp3-ytdl

[![PyPI version](https://img.shields.io/pypi/v/pymp3-ytdl.svg)](https://pypi.org/project/pymp3-ytdl/)
[![Python versions](https://img.shields.io/pypi/pyversions/pymp3-ytdl.svg)](https://pypi.org/project/pymp3-ytdl/)
[![License: GPL v2](https://img.shields.io/badge/License-GPL%20v2-blue.svg)](https://github.com/PremerX007/pymp3-ytdl/blob/main/LICENSE)

pymp3-ytdl is a Python CLI and library that downloads audio from supported video URLs via yt-dlp, converts to MP3, applies ID3 metadata, and embeds cover art.

## Highlights

- Uses yt-dlp for robust extraction.
- Converts audio to MP3 automatically.
- Writes title and artist metadata (ID3).
- Embeds thumbnails as cover art (including WebP -> JPEG fallback conversion).
- Ships with FFmpeg via imageio-ffmpeg: no manual system FFmpeg install required.
- Provides both CLI usage and importable Python API.

## Installation

### Install from PyPI

```bash
pip install pymp3-ytdl
```

### Install from source (development)

```bash
git clone https://github.com/PremerX007/pymp3-ytdl.git
cd pymp3-ytdl
pip install -e .
```

## CLI Usage

After installation, the command is available as:

```bash
pymp3-ytdl urls.txt
```

Where urls.txt contains one URL per line.

### Common options

```bash
pymp3-ytdl urls.txt --output-dir downloaded_music --loglevel INFO
```

```bash
pymp3-ytdl urls.txt --custom-rename --restricted-filenames
```

Options:

- --output-dir: target directory for MP3 files.
- --loglevel: DEBUG, INFO, WARNING, ERROR, CRITICAL.
- --custom-rename: rename files based on title metadata.
- --restricted-filenames: stricter filename sanitization when renaming.

## Python Module Usage

```python
import logging

from pymp3_ytdl.config import RenameOptions
from pymp3_ytdl.downloader import download_mp3_from_urls
from pymp3_ytdl.logging_utils import setup_logging

logger = setup_logging("INFO")

summary = download_mp3_from_urls(
  urls=[
    "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "https://www.youtube.com/watch?v=3JZ_D3ELwOQ",
  ],
  logger=logger,
  output_dir="downloaded_music",
  rename_options=RenameOptions(enabled=False),
)

print(summary)
```

## FFmpeg behavior

This project does not require a manually installed system FFmpeg.

- imageio-ffmpeg provides the FFmpeg executable.
- The downloader resolves it with imageio_ffmpeg.get_ffmpeg_exe().
- That path is passed to yt-dlp using the ffmpeg_location option.

## Project Layout

```text
.
|- pyproject.toml
|- src/
|  \- pymp3_ytdl/
|     |- __init__.py
|     |- __main__.py
|     |- cli.py
|     |- config.py
|     |- downloader.py
|     |- io_utils.py
|     |- logging_utils.py
|     \- metadata.py
|- README.md
\- LICENSE
```

## License

GPL-2.0-only. See LICENSE.

## Disclaimer

Use this tool only for content you are legally allowed to access and convert.

## Contributing and Issues

Found a bug or have a feature request? Please open an issue on the [GitHub repository](https://github.com/PremerX007/pymp3-ytdl/issues). Pull requests are also welcome!
