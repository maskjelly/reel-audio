# reel-audio

Give it an Instagram reel and it downloads the song used in it. The file gets a random name and has no tags, so nothing reveals the song. The only output is the file path.

```
$ reel-audio https://www.instagram.com/reel/DRevbteiTt6/
/Users/you/Downloads/d7k2q9x4mz/k3j9x2m1q8zt.mp3
```

## Install

Needs [uv](https://docs.astral.sh/uv/) and ffmpeg:

```sh
brew install uv ffmpeg
uv tool install git+https://github.com/maskjelly/reel-audio
reel-audio setup
```

`setup` runs a trial download, opens a folder picker for where songs go, and optionally adds a short alias.

## Usage

```sh
reel-audio <reel url>                            # prints the saved path
reel-audio <url1> <url2>                         # one path per line
reel-audio --cookies-from-browser chrome <url>   # private reels / rate limits
```

## Alias

`setup` asks for one, or add it yourself:

```sh
echo "alias song='reel-audio'" >> ~/.zshrc && source ~/.zshrc
song <reel url>
```

## Notes

- Songs go in a random folder inside the location you picked (default `~/Downloads`). Config: `~/.config/reel-audio/config.json`.
- Reels with "Original audio" (no song name) are skipped with an error.
- The song is found by searching YouTube for "artist - title". The top result is usually right, but not always.
- If YouTube downloads start failing, `brew install deno`.
- `REEL_AUDIO_DEBUG=1` prints full errors (these can include the song name).
- Update: `uv tool upgrade reel-audio`
