import pytest

from bot import keyboards
from bot.config import ConfigError, load_settings
from bot.handlers import UrlCache
from bot.links import extract_url, is_safe_url
from bot.recognizer import RecognitionError, Track, acrcloud_signature, parse_acrcloud, parse_audd
from bot.search import merge, parse_deezer, parse_itunes


def test_config_requires_token():
    with pytest.raises(ConfigError):
        load_settings({})
    with pytest.raises(ConfigError):
        load_settings({"BOT_TOKEN": "x", "RECOGNITION_PROVIDER": "none"})


def test_config_values():
    s = load_settings({"BOT_TOKEN": "1:abc", "RECOGNITION_PROVIDER": "audd", "AUDD_API_TOKEN": "k", "MAX_UPLOAD_MB": "99"})
    assert s.recognition_ready and s.max_upload_mb == 50
    assert not load_settings({"BOT_TOKEN": "1:abc", "RECOGNITION_PROVIDER": "audd"}).recognition_ready
    with pytest.raises(ConfigError):
        load_settings({"BOT_TOKEN": "1:abc", "RECOGNITION_PROVIDER": "zzz"})


def test_extract_url():
    assert extract_url("qara https://www.tiktok.com/@a/video/1?x=2, rahmat") == "https://www.tiktok.com/@a/video/1?x=2"
    assert extract_url("Shahzoda") is None


@pytest.mark.parametrize("url", [
    "http://localhost/x", "http://127.0.0.1/x", "http://169.254.169.254/latest", "http://10.0.0.5/",
    "http://[::1]/", "file:///etc/passwd", "ftp://example.com/a", "http://foo.internal/",
])
def test_unsafe_urls(url):
    assert not is_safe_url(url)


def test_safe_url():
    assert is_safe_url("https://8.8.8.8/x")
    assert is_safe_url("https://www.instagram.com/reel/abc/", resolve=False)


def test_audd_parse():
    t = parse_audd({"status": "success", "result": {"title": "T", "artist": "A", "album": "Al",
                    "song_link": "https://lis.tn/x", "spotify": {"external_urls": {"spotify": "https://sp"}}}})
    assert (t.title, t.artist, t.album) == ("T", "A", "Al") and t.links["Spotify"] == "https://sp"
    assert parse_audd({"status": "success", "result": None}) is None
    with pytest.raises(RecognitionError):
        parse_audd({"status": "error", "error": {"error_message": "bad token"}})


def test_acr_parse_and_signature():
    data = {"status": {"code": 0}, "metadata": {"music": [{"title": "T", "artists": [{"name": "A"}, {"name": "B"}],
            "album": {"name": "Al"}, "external_metadata": {"spotify": {"track": {"id": "abc"}}, "youtube": {"vid": "v1"}}}]}}
    t = parse_acrcloud(data)
    assert t.artist == "A, B" and t.links["Spotify"].endswith("/abc") and "v1" in t.links["YouTube"]
    assert parse_acrcloud({"status": {"code": 1001}}) is None
    with pytest.raises(RecognitionError):
        parse_acrcloud({"status": {"code": 3001, "msg": "invalid key"}})
    # deterministic, base64 of a 20-byte SHA1 digest
    sig = acrcloud_signature("key", "secret", "1700000000")
    assert sig == acrcloud_signature("key", "secret", "1700000000") and len(sig) == 28


def test_search_parse_and_merge():
    it = parse_itunes({"results": [{"wrapperType": "track", "trackName": "Song", "artistName": "Art", "trackViewUrl": "https://apple/1"},
                                   {"wrapperType": "artist"}]})
    dz = parse_deezer({"data": [{"title": "song", "artist": {"name": "ART"}, "link": "https://deezer/1"},
                                {"title": "Other", "artist": {"name": "X"}, "link": "https://deezer/2"}]})
    m = merge(it, dz)
    assert len(m) == 2
    assert set(m[0].links) == {"Apple Music", "Deezer", "YouTube Music"}


def test_keyboards_and_cache():
    c = UrlCache(size=2)
    toks = [c.put(f"https://a/{i}") for i in range(3)]
    assert c.get(toks[0]) is None and c.get(toks[2]) == "https://a/2"
    kb = keyboards.url_actions("tok")
    assert all(len(b.callback_data.encode()) <= 64 for row in kb.inline_keyboard for b in row)
    assert keyboards.track_links(Track("T", "A")).inline_keyboard
