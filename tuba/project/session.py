"""Full-folder identity and disposable discovery of a running local Studio."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import tempfile
from pathlib import Path
import urllib.error
import urllib.parse
import urllib.request
import uuid

from tuba.project.source import replace_source, source_lock, source_revision
from tuba.local_auth import LocalAccess, capability_url, new_access_token


def project_id(root: str | Path) -> str:
    return hashlib.sha256(os.path.normcase(str(Path(root).resolve())).encode("utf-8")).hexdigest()


def project_bundle_dir(parent: str | Path, root: str | Path) -> Path:
    folder = Path(root).resolve()
    return Path(parent).resolve() / f"{folder.name or 'project'}-{project_id(folder)[:16]}"


def _local_url(url: str) -> str:
    if not isinstance(url, str) or any(ord(char) < 33 for char in url):
        raise ValueError("Studio endpoint must be an HTTP loopback URL with its actual port.")
    parsed = urllib.parse.urlsplit(url)
    if (parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
            or parsed.username is not None or parsed.password is not None
            or parsed.port is None or not 1 <= parsed.port <= 65535
            or parsed.path not in {"", "/"} or parsed.query or parsed.fragment):
        raise ValueError("Studio endpoint must be an HTTP loopback URL with its actual port.")
    return url.rstrip("/") + "/"


def _credential_path(root: Path) -> Path:
    # Credentials stay outside the shareable project and its discovery pointer.
    directory = Path.home() / ".tuba-studio-credentials"
    directory.mkdir(mode=0o700, exist_ok=True)
    if directory.is_symlink() or (hasattr(directory, "is_junction") and directory.is_junction()):
        raise ValueError("Studio credential directory must not be a link.")
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        descriptor = wintypes.LPVOID()
        advapi = ctypes.WinDLL("advapi32", use_last_error=True)
        convert = advapi.ConvertStringSecurityDescriptorToSecurityDescriptorW
        convert.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, ctypes.POINTER(wintypes.LPVOID), wintypes.LPVOID]
        convert.restype = wintypes.BOOL
        set_security = advapi.SetFileSecurityW
        set_security.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.LPVOID]
        set_security.restype = wintypes.BOOL
        if not convert("D:P(A;OICI;FA;;;OW)", 1, ctypes.byref(descriptor), None):
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            if not set_security(str(directory), 0x80000004, descriptor):  # Protected DACL, owner only.
                raise ctypes.WinError(ctypes.get_last_error())
        finally:
            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel.LocalFree.argtypes = [wintypes.LPVOID]
            kernel.LocalFree(descriptor)
    else:
        if directory.stat().st_uid != os.getuid():
            raise ValueError("Studio credential directory belongs to another user.")
        directory.chmod(0o700)
    return directory / (project_id(root) + ".json")


def register_studio(root: str | Path, base_url: str, access_token: str | None = None) -> dict:
    folder = Path(root).resolve()
    base_url = _local_url(base_url)
    access_token = access_token or new_access_token()
    LocalAccess(access_token)
    websocket = "ws" + base_url[4:] + "preview/ws"
    record = {"project_root": str(folder), "project_id": project_id(folder),
              "base_url": base_url,
              "viewer_url": base_url + "?" + urllib.parse.urlencode({"bundle": "build", "preview_ws": websocket}),
              "session_id": uuid.uuid4().hex, "pid": os.getpid()}
    with source_lock(folder / "model.py"):
        credential = _credential_path(folder)
        descriptor, temporary = tempfile.mkstemp(dir=credential.parent)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                json.dump({**record, "access_token": access_token}, stream, ensure_ascii=False)
            os.replace(temporary, credential)
        finally:
            Path(temporary).unlink(missing_ok=True)
        path = folder / ".tuba" / "studio.json"
        replace_source(path, json.dumps(record, ensure_ascii=False), source_revision(path))
    return {**record, "access_token": access_token, "viewer_url": capability_url(record["viewer_url"], access_token)}


def _read_record(root: Path) -> dict:
    with (root / ".tuba" / "studio.json").open("rb") as stream:
        record = json.loads(stream.read(16385))
    if (not isinstance(record, dict) or record.get("project_id") != project_id(root)
            or not Path(record["project_root"]).is_absolute()
            or project_id(record["project_root"]) != project_id(root)
            or len(record["session_id"]) != 32):
        raise ValueError("Studio session belongs to another folder or is invalid.")
    uuid.UUID(hex=record["session_id"])
    base_url = _local_url(record["base_url"])
    expected_url = base_url + "?" + urllib.parse.urlencode({
        "bundle": "build", "preview_ws": "ws" + base_url[4:] + "preview/ws"})
    if record.get("viewer_url") != expected_url:
        raise ValueError("Studio viewer must use the validated local endpoint.")
    credential = _credential_path(root)
    if credential.is_symlink() or (os.name != "nt" and credential.stat().st_mode & (stat.S_IRWXG | stat.S_IRWXO)):
        raise ValueError("Studio credential file must be private to this user.")
    with credential.open("rb") as stream:
        private = json.loads(stream.read(16385))
    token = private.pop("access_token")
    LocalAccess(token)
    if private != record:
        raise ValueError("Studio discovery pointer differs from this user's registered endpoint.")
    return {**record, "access_token": token, "viewer_url": capability_url(expected_url, token)}


def unregister_studio(root: str | Path, session_id: str) -> None:
    folder = Path(root).resolve()
    try:
        with source_lock(folder / "model.py"):
            if _read_record(folder)["session_id"] == session_id:
                (folder / ".tuba" / "studio.json").unlink()
                _credential_path(folder).unlink(missing_ok=True)
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        pass  # A newer server owns the pointer, or it is already gone.


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def studio_session(root: str | Path) -> dict | None:
    """Return an endpoint only after a bounded, nonredirecting identity check."""
    folder = Path(root).resolve()
    try:
        record = _read_record(folder)
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
        request = urllib.request.Request(record["base_url"] + "api/project",
                                         headers={"Authorization": "Bearer " + record["access_token"]})
        with opener.open(request, timeout=0.5) as response:
            if response.headers.get_content_type() != "application/json":
                return None
            live = json.loads(response.read(32769))
        if (live.get("project_id") == record["project_id"]
                and live.get("session_id") == record["session_id"]
                and project_id(live["project_root"]) == project_id(folder)):
            return record
    except (OSError, urllib.error.URLError, ValueError, TypeError, KeyError, AttributeError):
        pass
    return None
