"""Per-launch authority for local Studio; loopback and revisions are not credentials."""

from __future__ import annotations

import hmac
import re
import secrets
from urllib.parse import urlencode, urlsplit


def new_access_token() -> str:
    return secrets.token_urlsafe(32)


def capability_url(url: str, token: str) -> str:
    return url + "#" + urlencode({"tuba_token": token})


class LocalAccess:
    """Authenticate HTTP headers and WebSocket protocols, with exact browser origins."""

    def __init__(self, token: str, *, allowed_dev_origin: str | None = None):
        if not isinstance(token, str) or not re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
            raise ValueError("Studio requires a random 32-byte launch capability.")
        if allowed_dev_origin is not None:
            parsed = urlsplit(allowed_dev_origin)
            if (parsed.scheme != "http" or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}
                    or parsed.username or parsed.password or parsed.port is None
                    or parsed.path or parsed.query or parsed.fragment):
                raise ValueError("Development origin must be one exact HTTP loopback origin with a port.")
        self.token = token
        self.allowed_dev_origin = allowed_dev_origin

    def browser_request(self, headers, host: str | None, *, mutate: bool = False, bootstrap: bool = False) -> bool:
        origin = headers.get("Origin")
        dev = origin is not None and origin == self.allowed_dev_origin
        if host is None or (origin is not None and origin != f"http://{host}" and not dev):
            return False
        site = headers.get("Sec-Fetch-Site")
        if site not in {None, "none", "same-origin", "same-site", "cross-site"}:
            return False
        if site == "cross-site" and not dev:
            return False
        # Same-site is not same-origin: localhost ports share a site, not authority.
        entry_navigation = (bootstrap and origin is None and headers.get("Sec-Fetch-Mode") == "navigate"
                            and headers.get("Sec-Fetch-Dest") == "document")
        if site == "same-site" and not dev and not entry_navigation:
            return False
        if site == "same-origin" and origin is not None and origin != f"http://{host}":
            return False
        if mutate and headers.get("Sec-Fetch-Mode") in {"navigate", "no-cors"}:
            return False
        return True

    def authenticated(self, headers, *, websocket: bool = False) -> bool:
        authorization = headers.get("Authorization", "")
        candidate = authorization[7:] if authorization.startswith("Bearer ") else ""
        if websocket:
            protocols = [part.strip() for part in headers.get("Sec-WebSocket-Protocol", "").split(",")]
            candidates = [part.removeprefix("tuba-auth.") for part in protocols if part.startswith("tuba-auth.")]
            if len(candidates) == 1:
                candidate = candidates[0]
        return isinstance(candidate, str) and candidate.isascii() and hmac.compare_digest(candidate, self.token)
