"""URL extraction and safety checks for user-supplied links."""
from __future__ import annotations

import ipaddress
import re
import socket
from urllib.parse import urlparse

_URL_RE = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)


def extract_url(text: str) -> str | None:
    m = _URL_RE.search(text or "")
    return m.group(0).rstrip(".,);]") if m else None


def is_safe_url(url: str, resolve: bool = True) -> bool:
    """Allow only http(s) URLs that point to public internet hosts (SSRF guard)."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return False
    host = parsed.hostname
    if host.lower() in ("localhost",) or host.lower().endswith((".local", ".internal")):
        return False
    try:
        addrs = [ipaddress.ip_address(host)]
    except ValueError:
        if not resolve:
            return "." in host
        try:
            infos = socket.getaddrinfo(host, None)
        except OSError:
            return False
        addrs = [ipaddress.ip_address(i[4][0].split("%")[0]) for i in infos]
    return bool(addrs) and all(a.is_global for a in addrs)
