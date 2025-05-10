#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Downloads MP3 audio from a list of URLs (e.g., YouTube videos),
sets metadata (title, artist), and embeds the video thumbnail as cover art.
Files are saved to a specified output directory.

This version attempts to get the final filepath directly from yt-dlp's
info_dict after download and conversion.
It also converts WebP thumbnails to JPEG for better compatibility.

Dependencies:
- yt-dlp: For downloading and extracting audio.
- mutagen: For MP3 metadata manipulation.
- requests: For downloading thumbnails.
- Pillow: For image format conversion (e.g., WebP to JPEG).
- ffmpeg: Must be installed and in the system PATH (for yt-dlp audio extraction).

Usage:
python this_script_name.py list_of_urls.txt

Where list_of_urls.txt contains one URL per line.
"""

import sys
import os
import yt_dlp
from yt_dlp.utils import sanitize_filename as ydlp_sanitize_filename
from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3, APIC, ID3NoHeaderError
from mutagen.mp3 import MP3
import requests
import shutil
from PIL import Image
import io
import time # For fallback check

# --- Configuration ---
OUTPUT_DIRECTORY_NAME = "downloaded_music"
PERFORM_CUSTOM_RENAMING = False # Defaulting to False

# --- Helper Functions (read_url_list, apply_metadata_and_cover - same as before) ---
def read_url_list(file_path: str) -> list[str]:
    if not os.path.isfile(file_path):
        print(f"Error: URL file not found: {file_path}")
        sys.exit(1)
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            urls = [line.strip() for line in f if line.strip()]
            if not urls:
                print(f"Error: The URL file '{file_path}' is empty or contains only blank lines.")
                sys.exit(1)
            return urls
    except Exception as e:
        print(f"Error: Failed to read URL file '{file_path}': {e}")
        sys.exit(1)

def apply_metadata_and_cover(mp3_filepath: str, title: str, artist: str, thumbnail_url: str | None = None) -> None:
    if not os.path.exists(mp3_filepath):
        print(f"  Error (apply_metadata): MP3 file not found at '{mp3_filepath}'. Cannot apply metadata.")
        return
    try:
        try:
            audio = EasyID3(mp3_filepath)
        except ID3NoHeaderError:
            audio_mp3 = MP3(mp3_filepath)
            if audio_mp3.tags is None:
                audio_mp3.add_tags()
                audio_mp3.save()
            audio = EasyID3(mp3_filepath)

        audio['title'] = title
        audio['artist'] = artist
        audio.save()
        print(f"  Set metadata: title='{title}', artist='{artist}' for '{os.path.basename(mp3_filepath)}'")

        if thumbnail_url:
            try:
                response = requests.get(thumbnail_url, timeout=15)
                response.raise_for_status()
                image_data = response.content
                original_mime_type = response.headers.get('Content-Type', 'image/jpeg').lower()
                
                final_image_data = image_data
                final_mime_type = original_mime_type

                if original_mime_type == 'image/webp':
                    print(f"  Attempting to convert WEBP thumbnail to JPEG...")
                    try:
                        img = Image.open(io.BytesIO(image_data))
                        if img.mode == 'RGBA' or img.mode == 'P' or img.mode == 'LA':
                            img = img.convert('RGB')
                        
                        output_buffer = io.BytesIO()
                        img.save(output_buffer, format='JPEG', quality=90)
                        final_image_data = output_buffer.getvalue()
                        final_mime_type = 'image/jpeg'
                        print(f"  WEBP successfully converted to JPEG.")
                    except Exception as e_conv:
                        print(f"  Warning: Failed to convert WEBP to JPEG: {e_conv}. Trying to embed original WebP.")

                audio_full = ID3(mp3_filepath)
                audio_full.delall('APIC')
                audio_full.add(
                    APIC(
                        encoding=3, mime=final_mime_type, type=3,
                        desc='Cover', data=final_image_data
                    )
                )
                audio_full.save(v2_version=3)
                print(f"  Embedded cover art (mime: {final_mime_type}) into '{os.path.basename(mp3_filepath)}'")
            except requests.RequestException as e_req:
                print(f"  Warning: Could not download thumbnail from {thumbnail_url}: {e_req}")
            except Exception as e_cover:
                print(f"  Warning: Could not embed cover art for '{os.path.basename(mp3_filepath)}': {e_cover}")
    except Exception as e:
        print(f"  Error: Failed to set metadata for '{os.path.basename(mp3_filepath)}': {e}")


# --- Main Download Function ---
def download_mp3_from_urls(urls: list[str], output_dir: str = OUTPUT_DIRECTORY_NAME) -> None:
    if not os.path.exists(output_dir):
        try:
            os.makedirs(output_dir)
            print(f"Created output directory: {output_dir}")
        except OSError as e:
            print(f"Error: Could not create output directory '{output_dir}': {e}")
            sys.exit(1)

    ydl_opts_base = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'outtmpl': { # This still guides yt-dlp for the initial name if needed,
                     # but we'll rely on the returned filepath.
            'default': os.path.join(output_dir, '%(title)s.%(ext)s')
        },
        'noplaylist': True,
        'quiet': False,
        'ignoreerrors': 'only_download',
        'writethumbnail': False,
        # 'keepvideo': True,
    }

    download_count = 0
    total_urls = len(urls)

    print(f"Starting download process for {total_urls} URL(s)...")
    print(f"Output directory: {os.path.abspath(output_dir)}")

    for i, url in enumerate(urls, 1):
        print(f"\n[{i}/{total_urls}] Processing URL: {url}")
        
        final_info_dict = None # To store the info_dict returned after download

        try:
            # We will use a single call to extract_info with download=True
            # This way, the returned info_dict should contain the final filepath
            # after all postprocessing (like audio extraction) is done.
            current_ydl_opts = ydl_opts_base.copy()
            with yt_dlp.YoutubeDL(current_ydl_opts) as ydl:
                print(f"  Starting download and extraction process...")
                # The extract_info with download=True will download AND run postprocessors
                # The returned info_dict should be for the final processed file.
                final_info_dict = ydl.extract_info(url, download=True)

                # Check if download was successful (this is a bit indirect here)
                # A more direct check would be `ydl.download([url])` which returns an error code,
                # but then getting the *final* filepath from info_dict is trickier.
                # Let's assume if final_info_dict is populated and contains 'filepath', it worked.

                if final_info_dict:
                    # --- Get the actual downloaded MP3 filepath from final_info_dict ---
                    # After FFmpegExtractAudio, 'filepath' should point to the .mp3
                    # If multiple files were processed (e.g. playlist items), 'entries' would be filled.
                    # For a single URL, 'filepath' or info from 'requested_downloads' should be there.
                    
                    downloaded_mp3_path = final_info_dict.get('filepath')

                    # Sometimes, for single file downloads with postprocessing,
                    # the direct 'filepath' might be for the intermediate file.
                    # The actual final path might be in 'requested_downloads'.
                    if not downloaded_mp3_path or not downloaded_mp3_path.lower().endswith('.mp3'):
                        if final_info_dict.get('requested_downloads'):
                            for dl_info in final_info_dict['requested_downloads']:
                                if dl_info.get('filepath') and dl_info['filepath'].lower().endswith('.mp3'):
                                    downloaded_mp3_path = dl_info['filepath']
                                    break
                    
                    if downloaded_mp3_path and os.path.exists(downloaded_mp3_path) and downloaded_mp3_path.lower().endswith('.mp3'):
                        print(f"  Download and conversion successful. Final file: '{os.path.basename(downloaded_mp3_path)}'")
                        download_count += 1
                        
                        # --- Prepare metadata from the final_info_dict ---
                        title_for_metadata = (final_info_dict.get('track') or final_info_dict.get('title', 'Unknown Title')).strip()
                        if not title_for_metadata: title_for_metadata = 'Unknown Title'

                        artist_for_metadata = (final_info_dict.get('artist') or final_info_dict.get('uploader', 'Unknown Artist')).strip()
                        if not artist_for_metadata: artist_for_metadata = 'Unknown Artist'
                        
                        thumbnail_url = final_info_dict.get('thumbnail')

                        # --- Renaming Logic (Optional) ---
                        final_path_for_metadata = downloaded_mp3_path
                        if PERFORM_CUSTOM_RENAMING:
                            desired_filename_base = ydlp_sanitize_filename(title_for_metadata, restricted=True)
                            desired_filename_mp3 = f"{desired_filename_base}.mp3"
                            # Ensure desired path is in the correct output_dir, as downloaded_mp3_path is absolute
                            desired_filepath_mp3 = os.path.join(os.path.dirname(downloaded_mp3_path), desired_filename_mp3)


                            if downloaded_mp3_path != desired_filepath_mp3:
                                if os.path.exists(desired_filepath_mp3):
                                    print(f"  Warning (Rename): Target file '{desired_filename_mp3}' already exists. "
                                          f"Not renaming. Using: '{os.path.basename(downloaded_mp3_path)}'")
                                else:
                                    try:
                                        print(f"  Renaming '{os.path.basename(downloaded_mp3_path)}' to '{desired_filename_mp3}'")
                                        shutil.move(downloaded_mp3_path, desired_filepath_mp3)
                                        final_path_for_metadata = desired_filepath_mp3
                                    except OSError as e_rename:
                                        print(f"  Error (Rename): Could not rename file: {e_rename}. "
                                              f"Using original name: '{os.path.basename(downloaded_mp3_path)}'")
                        else:
                            print(f"  Skipping custom renaming. Using filename from yt-dlp: '{os.path.basename(downloaded_mp3_path)}'")
                        
                        apply_metadata_and_cover(final_path_for_metadata, title_for_metadata, artist_for_metadata, thumbnail_url)
                    else:
                        print(f"  Error: Could not reliably locate the final MP3 file path from yt-dlp's output for URL {url}.")
                        if downloaded_mp3_path:
                             print(f"    Last known path: '{downloaded_mp3_path}', Exists: {os.path.exists(downloaded_mp3_path)}")
                        print(f"    Final info dict from yt-dlp was: {final_info_dict.get('filepath', 'N/A')}, "
                              f"requested_downloads: {final_info_dict.get('requested_downloads', 'N/A')}")


                else: # final_info_dict is None or empty
                    print(f"  yt-dlp's extract_info (with download) did not return sufficient information for {url}.")

        except yt_dlp.utils.DownloadError as e_dl:
            print(f"  DownloadError during processing {url}: {e_dl}")
        except Exception as e:
            print(f"  An unexpected error occurred while processing {url}: {e}")
            import traceback
            traceback.print_exc()

    # --- Summary ---
    print("\n--- Download Process Finished ---")
    if download_count > 0:
        print(f"Successfully attempted to download and process {download_count} out of {total_urls} item(s).")
    else:
        print("No items were successfully downloaded or processed.")
    print(f"Files are located in: {os.path.abspath(output_dir)}")


# --- Main Execution ---
if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: python your_script_name.py <url_list_file.txt>")
        sys.exit(1)

    url_file_path = sys.argv[1]
    urls_to_download = read_url_list(url_file_path)
    
    if urls_to_download:
        download_mp3_from_urls(urls_to_download, OUTPUT_DIRECTORY_NAME)
    else:
        print("No URLs to process from the file.")