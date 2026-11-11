"""Find the song used in an Instagram reel and download it under an obfuscated name.

Nothing here prints or stores the song's title/artist: the file and folder names are random,
audio tags are stripped, and errors are generic.
"""
from __future__ import annotations

import os
import re
import secrets
import shutil
import string
import subprocess
import tempfile
import traceback

import yt_dlp
from yt_dlp.extractor.instagram import InstagramIE

# yt-dlp drops Instagram's music fields, so keep the raw media object it parsed.
_orig_extract_product = InstagramIE._extract_product


def _patched_extract_product(self, product_info, *args, **kwargs):
    self._raw_product = product_info
    return _orig_extract_product(self, product_info, *args, **kwargs)


InstagramIE._extract_product = _patched_extract_product

REEL_RE = re.compile(r"^https?://(www\.|m\.)?instagram\.com/(reels?|p|tv)/[\w-]+", re.I)
DEBUG = os.environ.get("REEL_AUDIO_DEBUG") == "1"  # prints tracebacks (may include song names)
_ALPHABET = string.ascii_lowercase + string.digits


class ReelAudioError(Exception):
    """Generic, song-name-free error message."""


def random_name(n: int = 12) -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(n))


def _debug():
    if DEBUG:
        traceback.print_exc()


def _opts(cookies: str | None = None, browser: str | None = None) -> dict:
    opts = {"quiet": True, "no_warnings": True, "noprogress": True, "noplaylist": True,
            "socket_timeout": 30, "logger": _SilentLogger()}
    if cookies:
        opts["cookiefile"] = cookies
    if browser:
        opts["cookiesfrombrowser"] = (browser,)
    return opts


class _SilentLogger:
    def debug(self, msg): pass
    def info(self, msg): pass
    def warning(self, msg): pass
    def error(self, msg): pass


def normalize_url(url: str) -> str:
    m = REEL_RE.match(url.strip())
    if not m:
        raise ReelAudioError("not an Instagram reel URL")
    return re.sub(r"^https?://(m\.)?(www\.)?", "https://www.", m.group(0), flags=re.I) + "/"


def _song_query(raw: dict | None) -> str | None:
    clips = (raw or {}).get("clips_metadata") or {}
    asset = (clips.get("music_info") or {}).get("music_asset_info") or {}
    attribution = (raw or {}).get("clips_music_attribution_info") or {}
    if asset or (attribution and not attribution.get("uses_original_audio")):
        title = asset.get("title") or attribution.get("song_name")
        artist = asset.get("display_artist") or attribution.get("artist_name")
        if title:
            return " - ".join(x for x in (artist, title) if x)
    original = clips.get("original_sound_info") or {}
    title = (original.get("original_audio_title") or "").strip()
    # A renamed "original audio" (e.g. "Song - Artist") is usually still searchable.
    if title and title.lower() != "original audio":
        return title
    return None


def find_song_query(url: str, *, cookies: str | None = None, browser: str | None = None) -> str:
    url = normalize_url(url)
    with yt_dlp.YoutubeDL({**_opts(cookies, browser), "skip_download": True}) as ydl:
        try:
            ydl.extract_info(url, download=False)
        except Exception as e:
            _debug()
            raise ReelAudioError("could not read the reel (private, removed, or rate-limited; try --cookies-from-browser)") from e
        raw = getattr(ydl.get_info_extractor("Instagram"), "_raw_product", None)
    query = _song_query(raw)
    if not query:
        raise ReelAudioError("this reel doesn't use a named song")
    return query


def _strip_tags(src: str, dest: str) -> None:
    cmd = ["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-i", src, "-map", "0:a",
           "-map_metadata", "-1", "-map_chapters", "-1", "-c", "copy",
           "-fflags", "+bitexact", "-flags:a", "+bitexact", "-id3v2_version", "0", "-write_id3v1", "0", dest]
    if subprocess.run(cmd, capture_output=True).returncode != 0:
        raise ReelAudioError("audio processing failed (is ffmpeg installed?)")


def download_song(url: str, dest_dir, *, cookies: str | None = None, browser: str | None = None,
                  yt_cookies: str | None = None) -> str:
    """Download the reel's song as an untagged mp3 with a random name in dest_dir. Returns the path.

    dest_dir may be a callable, resolved only once the song is ready (so failures create no folder).
    """
    query = find_song_query(url, cookies=cookies, browser=browser)
    tmp = tempfile.mkdtemp(prefix="tmp")
    try:
        opts = {**_opts(yt_cookies, browser), "format": "bestaudio/best",
                "outtmpl": os.path.join(tmp, "a.%(ext)s"),
                "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "0"}]}
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.extract_info(f"ytsearch1:{query} audio", download=True)
        except Exception as e:
            _debug()
            raise ReelAudioError("song download failed (try again, or pass --yt-cookies)") from e
        src = os.path.join(tmp, "a.mp3")
        if not os.path.exists(src):
            raise ReelAudioError("song download failed")
        dest_dir = str(dest_dir() if callable(dest_dir) else dest_dir)
        os.makedirs(dest_dir, exist_ok=True)
        while True:
            dest = os.path.join(dest_dir, random_name() + ".mp3")
            if not os.path.exists(dest):
                break
        _strip_tags(src, dest)
        return os.path.abspath(dest)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
