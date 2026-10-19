import functools
import http.server
import subprocess
import threading
from pathlib import Path

import pytest

from bot.downloader import FileTooBig, download_audio, download_video
from bot.media import MediaError, extract_audio_clip


def _ffmpeg(*args):
    subprocess.run(["ffmpeg", "-y", "-v", "error", *args], check=True)


@pytest.fixture(scope="module")
def sample_video(tmp_path_factory) -> Path:
    d = tmp_path_factory.mktemp("srv")
    _ffmpeg("-f", "lavfi", "-i", "testsrc=size=320x240:rate=15:duration=3",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=3", "-c:v", "libx264", "-c:a", "aac",
            "-pix_fmt", "yuv420p", "-shortest", str(d / "clip.mp4"))
    return d / "clip.mp4"


@pytest.fixture(scope="module")
def server(sample_video):
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(sample_video.parent))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_port}"
    httpd.shutdown()


async def test_extract_clip(sample_video, tmp_path):
    out = await extract_audio_clip(sample_video, tmp_path / "c.mp3")
    assert out.stat().st_size > 1000


async def test_extract_clip_no_audio(tmp_path):
    silent = tmp_path / "v.mp4"
    _ffmpeg("-f", "lavfi", "-i", "testsrc=size=160x120:rate=10:duration=1", "-c:v", "libx264", str(silent))
    with pytest.raises(MediaError):
        await extract_audio_clip(silent, tmp_path / "c.mp3")


async def test_download_video_and_audio(server, tmp_path):
    v = tmp_path / "v"; v.mkdir()
    item = await download_video(f"{server}/clip.mp4", v, 49 * 1024 * 1024)
    assert item.path.suffix == ".mp4" and item.path.stat().st_size > 0
    a = tmp_path / "a"; a.mkdir()
    audio = await download_audio(f"{server}/clip.mp4", a, 49 * 1024 * 1024, to_mp3=True)
    assert audio.path.suffix == ".mp3"


async def test_download_too_big(server, tmp_path):
    with pytest.raises(FileTooBig):
        await download_video(f"{server}/clip.mp4", tmp_path, 1000)
