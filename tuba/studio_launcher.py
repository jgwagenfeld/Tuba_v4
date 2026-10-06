"""Loopback project launcher; project folders remain the source of truth."""

from __future__ import annotations

import json
import os
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlencode, urlsplit

from tuba.project import load_project
from tuba.project.study import study_scaffold


def viewer_url(server: Any) -> str:
    return f"{server.base_url}?{urlencode({'bundle': 'build', 'preview_ws': server.ws_url})}"


def local_folder(value: Any) -> Path:
    """Accept an explicit local absolute folder, including spaces and Unicode."""
    if not isinstance(value, str) or not value.strip() or len(value) > 4096 or any(ord(c) < 32 for c in value):
        raise ValueError("Enter the full local folder path.")
    path = Path(value)
    if not path.is_absolute() or ".." in path.parts or value.startswith(("\\\\", "//")):
        raise ValueError("Use a full local folder path without '..' or a network share.")
    return path.resolve()


def create_project(root: Path) -> None:
    """Create a small authored model and the existing Code_Aster study scaffold."""
    if root.exists() and (not root.is_dir() or any(root.iterdir())):
        raise ValueError("New Project requires a new or empty folder; existing files are preserved.")
    if not root.parent.is_dir():
        raise ValueError("The parent folder must already exist.")
    root.mkdir(exist_ok=True)
    model = '\n'.join([
        '"""A one metre anchored pipe; edit this Python project to define your structure."""',
        '', 'from tuba import Model', '', f'model = Model({root.name!r})',
        'model.add_material("Steel", E=210e9, nu=0.3, rho=7850.0, alpha=1.2e-5)',
        'model.add_pipe_section("DN100", OD=0.1143, WT=0.00602)',
        'model.define_load_case("Operating", gravity=True)',
        'with model.pipe(section="DN100", material="Steel") as pipe:',
        '    pipe.start([0.0, 0.0, 0.0], support="anchor")',
        '    pipe.run(1.0)', 'model.validate()', '',
    ])
    # Exclusive creation also refuses files appearing after the empty-folder check.
    with (root / "model.py").open("x", encoding="utf-8", newline="") as stream:
        stream.write(model)
    with (root / "study.py").open("x", encoding="utf-8", newline="") as stream:
        stream.write(study_scaffold(root.name, ["Operating"]))


class StudioLauncher:
    """Own the Studios this launcher starts, never another process's sessions."""

    def __init__(self, state_dir: Path, *, host: str = "127.0.0.1", port: int = 0, out_dir: Path | None = None):
        if host not in {"127.0.0.1", "localhost"}:
            raise ValueError("The project launcher binds to localhost or 127.0.0.1 only.")
        self.state_dir = state_dir.resolve()
        self.out_dir = (out_dir or self.state_dir / "bundles").resolve()
        self.default_folder = Path.cwd().resolve()
        self.host, self.port = host, port
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._studios: dict[str, Any] = {}
        self._httpd: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}/"

    def recent(self) -> list[dict[str, Any]]:
        path = self.state_dir / "recent.json"
        try:
            if path.stat().st_size > 131072:
                return []
            values = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(values, list):
                return []
        except (OSError, ValueError):
            return []
        entries = []
        for value in values[:20]:
            try:
                root = local_folder(value)
            except (ValueError, OSError):
                continue
            entries.append({"path": str(root), "name": root.name, "available": (root / "model.py").is_file()})
        return entries

    def folders(self, value: Any = None) -> dict[str, Any]:
        root = self.default_folder if value is None else local_folder(value)
        if not root.is_dir():
            raise ValueError("That folder does not exist.")
        folders = []
        for child in sorted(root.iterdir(), key=lambda p: p.name.casefold()):
            if child.is_dir():
                folders.append({"name": child.name, "path": str(child.resolve()), "is_project": (child / "model.py").is_file()})
            if len(folders) >= 256:
                break
        drives = [f"{letter}:\\" for letter in "CDEFGHIJKLMNOPQRSTUVWXYZ" if Path(f"{letter}:\\").is_dir()] if os.name == "nt" else ["/"]
        return {"ok": True, "path": str(root), "parent": str(root.parent), "folders": folders,
                "is_project": (root / "model.py").is_file(), "drives": drives}

    def open_project(self, value: Any, *, create: bool = False) -> dict[str, Any]:
        from tuba.project.session import project_bundle_dir, project_id, studio_session
        from tuba.visualization.preview.server import ProjectStudioServer

        root = local_folder(value)
        with self._lock:
            if self._stop.is_set():
                raise ValueError("This launcher is stopping; start Tuba Studio again.")
            if create:
                create_project(root)
            project = load_project(root)  # Open does not scaffold or rewrite a project.
            key = project_id(project.root)
            existing = studio_session(project.root)
            server = self._studios.get(key)
            if existing is not None:
                url, reused = existing["viewer_url"], True
            elif server is not None and not server._stop.is_set():
                url, reused = viewer_url(server), True
            else:
                server = ProjectStudioServer(project.root, project_bundle_dir(self.out_dir, project.root), host=self.host, port=0)
                server.launcher_url = self.base_url
                try:
                    server.start()
                except Exception:
                    server.stop()
                    raise
                self._studios[key] = server
                url, reused = viewer_url(server), False
            self.state_dir.mkdir(parents=True, exist_ok=True)
            from tuba.project.source import replace_source, source_lock, source_revision

            recent_path = self.state_dir / "recent.json"
            with source_lock(recent_path):
                paths = [str(project.root)] + [entry["path"] for entry in self.recent() if project_id(entry["path"]) != key]
                replace_source(recent_path, json.dumps(paths[:20], ensure_ascii=False), source_revision(recent_path))
        return {"ok": True, "project_root": str(project.root), "project_id": key, "viewer_url": url, "reused": reused}

    def start(self) -> "StudioLauncher":
        launcher = self

        class Handler(BaseHTTPRequestHandler):
            def setup(self) -> None:
                super().setup()
                self.connection.settimeout(5)

            def log_message(self, _format: str, *_args: Any) -> None:
                pass

            def local_request(self) -> bool:
                host = self.headers.get("Host", "")
                allowed = {f"127.0.0.1:{launcher.port}", f"localhost:{launcher.port}"}
                origin = self.headers.get("Origin")
                return host in allowed and (origin is None or origin == f"http://{host}") and self.headers.get("Sec-Fetch-Site") != "cross-site"

            def reply(self, status: int, data: Any, *, html: bool = False) -> None:
                raw = data.encode("utf-8") if html else json.dumps(data, ensure_ascii=False).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "text/html; charset=utf-8" if html else "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(raw)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'; base-uri 'none'")
                self.end_headers()
                self.wfile.write(raw)

            def do_GET(self) -> None:
                if not self.local_request():
                    self.reply(403, {"ok": False, "error": "Cross-origin request refused."})
                    return
                parsed = urlsplit(self.path)
                try:
                    if parsed.path == "/":
                        self.reply(200, LAUNCHER_HTML, html=True)
                    elif parsed.path == "/api/projects":
                        self.reply(200, {"ok": True, "recent": launcher.recent(), "default_folder": str(launcher.default_folder)})
                    elif parsed.path == "/api/folders":
                        values = parse_qs(parsed.query)
                        if set(values) - {"path"} or len(values.get("path", [])) > 1:
                            raise ValueError("Choose one folder path.")
                        self.reply(200, launcher.folders(values.get("path", [None])[0]))
                    else:
                        self.reply(404, {"ok": False, "error": "Unknown launcher route."})
                except (OSError, ValueError) as exc:
                    self.reply(400, {"ok": False, "error": str(exc)})

            def do_POST(self) -> None:
                if not self.local_request():
                    # Drain bounded bodies so Windows does not reset the socket before 403 is read.
                    try:
                        length = int(self.headers.get("Content-Length", "0"))
                        if 0 < length <= 8192 and not self.headers.get("Transfer-Encoding"):
                            self.rfile.read(length)
                    except (ValueError, OSError):
                        pass
                    self.reply(403, {"ok": False, "error": "Cross-origin request refused."})
                    return
                try:
                    if urlsplit(self.path).path == "/api/projects/import":
                        from tuba.project.package import MAX_ARCHIVE_BYTES, unpack_project_package
                        length = int(self.headers.get("Content-Length", "0"))
                        if (not 0 < length <= MAX_ARCHIVE_BYTES or self.headers.get("Transfer-Encoding")
                                or self.headers.get_content_type() != "application/octet-stream"):
                            self.close_connection = True
                            raise ValueError("Send a ZIP/TGZ project package of up to 2 GiB.")
                        destination = local_folder(unquote(self.headers.get("X-Project-Destination", "")))
                        if destination.exists():
                            self.close_connection = True
                            raise ValueError("Choose a new working folder; the destination already exists.")
                        self.connection.settimeout(120)
                        launcher.state_dir.mkdir(parents=True, exist_ok=True)
                        with tempfile.TemporaryDirectory(prefix="package-", dir=launcher.state_dir) as temporary:
                            archive = Path(temporary) / "upload.tubaproject"
                            with archive.open("xb") as target:
                                remaining = length
                                while remaining:
                                    chunk = self.rfile.read(min(remaining, 1024 * 1024))
                                    if not chunk:
                                        raise ValueError("Package upload was truncated.")
                                    target.write(chunk)
                                    remaining -= len(chunk)
                            root = unpack_project_package(archive, destination)
                        self.reply(200, launcher.open_project(str(root)))
                        return
                    length = int(self.headers.get("Content-Length", "0"))
                    if not 0 < length <= 8192 or self.headers.get_content_type() != "application/json" or self.headers.get("Transfer-Encoding"):
                        raise ValueError("Send a JSON folder path of at most 8 KiB.")
                    body = json.loads(self.rfile.read(length).decode("utf-8"))
                    if not isinstance(body, dict) or set(body) != {"path"}:
                        raise ValueError("Send exactly one folder path.")
                    route = urlsplit(self.path).path
                    if route not in {"/api/projects/open", "/api/projects/new"}:
                        self.reply(404, {"ok": False, "error": "Unknown launcher route."})
                        return
                    self.reply(200, launcher.open_project(body["path"], create=route.endswith("/new")))
                except (OSError, ValueError, UnicodeError) as exc:
                    self.reply(400, {"ok": False, "error": str(exc)})
                except Exception as exc:
                    self.reply(500, {"ok": False, "error": f"Project could not open: {exc}"})

        self._httpd = ThreadingHTTPServer((self.host, self.port), Handler)
        self.port = int(self._httpd.server_address[1])
        self._thread = threading.Thread(target=self._httpd.serve_forever, name="tuba-launcher", daemon=True)
        self._thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()
        if self._thread is not None:
            self._thread.join(timeout=2)
        with self._lock:
            studios = list(self._studios.values())
        for studio in studios:
            studio.stop()


LAUNCHER_HTML = r"""<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Tuba Studio — Projects</title>
<style>
:root{font:17px system-ui,sans-serif;color:#eef3f4;background:#151c22;color-scheme:dark}*{box-sizing:border-box}
body{margin:0}main{max-width:960px;margin:7vh auto;padding:28px}h1{font-size:36px;margin:8px 0}h2{font-size:21px}
.muted{color:#bac7cd;line-height:1.6}label{display:block;margin-bottom:8px}input{width:100%;font:15px ui-monospace,monospace;padding:13px;background:#202a31;border:1px solid #596972;border-radius:5px}
button,a{font:inherit;color:inherit}button{cursor:pointer;padding:11px 16px;border:1px solid #596972;border-radius:5px;background:#26323a}button:hover{background:#34444e}button:focus-visible,a:focus-visible,input:focus-visible{outline:3px solid #5ed8e5;outline-offset:3px}button:disabled{opacity:.5;cursor:default}
.actions{display:flex;gap:10px;flex-wrap:wrap;margin:14px 0 32px}.primary{background:#075b66;border-color:#5ed8e5}ul{padding:0;list-style:none}li{margin:8px 0}.recent button{width:100%;text-align:left}.path{display:block;font:13px ui-monospace,monospace;color:#bac7cd;overflow-wrap:anywhere;margin-top:4px}
#status{min-height:28px;color:#f0b429}dialog{width:min(720px,90vw);background:#202a31;border:1px solid #596972;border-radius:8px;color:inherit}dialog::backdrop{background:#0009}.dialog-head{display:flex;justify-content:space-between;align-items:center}#folders{max-height:36vh;overflow:auto}#folders button{width:100%;text-align:left}.browse-path{overflow-wrap:anywhere}select{padding:8px;font:inherit}
</style><main>
<p class="muted">TUBA · LOCAL ENGINEERING WORKSPACE</p><h1>Open a project</h1>
<p class="muted">A project is a folder with model.py, study.py and your geometry. Python defines the model; Code_Aster evaluates it; Studio displays the results.</p>
<form id="project-form"><label for="project-path">Project folder — full local path</label><input id="project-path" required autocomplete="off" spellcheck="false" placeholder="D:\Projects\My piping project">
<div class="actions"><button class="primary" id="open" type="submit">Open Folder</button><button id="browse" type="button">Browse folders</button><button id="new" type="button">New Project</button></div></form>
<h2>Open a shared project</h2>
<form id="package-form">
<label for="package-file">Project package (ZIP or TGZ)</label><input id="package-file" type="file" accept=".tubaproject,.zip,.tgz,.tar.gz" required>
<label for="package-folder">New working folder — full local path</label><input id="package-folder" required autocomplete="off" spellcheck="false">
<p class="muted">Extracts the package into this new folder, then runs its Python in Studio. Open projects from people you trust.</p>
<div class="actions"><button class="primary" id="import-package" type="submit">Open package</button></div></form>
<p id="status" role="status" aria-live="polite"></p><h2>Recent Projects</h2><ul id="recent" class="recent"></ul>
<p class="muted">Open preserves existing project files. New Project requires a new or empty folder and creates a small Python starter with a Code_Aster study.</p>
</main><dialog id="browser" aria-labelledby="browse-title"><div class="dialog-head"><h2 id="browse-title">Choose a local folder</h2><button id="close" aria-label="Close folder browser">Close</button></div>
<p class="browse-path" id="browse-path"></p><label for="drive">Drive</label><select id="drive"></select><div class="actions"><button id="up">Parent folder</button><button id="choose" class="primary">Use this folder</button></div><ul id="folders"></ul></dialog>
<script>
const $=id=>document.getElementById(id);let browsingPath='',defaultFolder='';
async function request(url,options){const response=await fetch(url,{cache:'no-store',...options});const result=await response.json();if(!response.ok||!result.ok)throw Error(result.error||`Launcher answered ${response.status}`);return result}
async function recent(){const result=await request('/api/projects');defaultFolder=result.default_folder;$('recent').replaceChildren();for(const entry of result.recent){const li=document.createElement('li'),button=document.createElement('button'),path=document.createElement('span');button.textContent=entry.name+(entry.available?'':' — unavailable');button.disabled=!entry.available;path.className='path';path.textContent=entry.path;button.append(path);button.onclick=()=>openProject('open',entry.path);li.append(button);$('recent').append(li)}if(!result.recent.length)$('recent').textContent='No projects opened yet.'}
async function openProject(action,path=$('project-path').value){$('status').textContent=action==='new'?'Creating project…':'Opening project…';$('open').disabled=$('new').disabled=true;try{const result=await request('/api/projects/'+action,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({path})});$('status').replaceChildren(document.createTextNode('Ready. '));const link=document.createElement('a');link.href=result.viewer_url;link.target='_blank';link.rel='noopener';link.textContent='Open Studio';$('status').append(link);await recent();window.open(result.viewer_url,'_blank','noopener')}catch(error){$('status').textContent=error.message}finally{$('open').disabled=$('new').disabled=false}}
function suggestPackageFolder(){const file=$('package-file').files[0];if(!file)return;const name=file.name.replace(/\.(tubaproject|zip|tgz|tar\.gz)$/i,'').replace(/[<>:"/\\|?*]/g,'_')||'project';const separator=defaultFolder.includes('\\')?'\\':'/';$('package-folder').value=defaultFolder.replace(/[\\/]+$/,'')+separator+name}
$('package-file').onchange=suggestPackageFolder;
$('package-form').onsubmit=async event=>{event.preventDefault();const file=$('package-file').files[0];if(!file)return;$('import-package').disabled=true;$('status').textContent='Extracting and opening project…';try{const result=await request('/api/projects/import',{method:'POST',headers:{'Content-Type':'application/octet-stream','X-Project-Destination':encodeURIComponent($('package-folder').value)},body:file});$('status').replaceChildren(document.createTextNode('Opened '+result.project_root+'. '));const link=document.createElement('a');link.href=result.viewer_url;link.target='_blank';link.rel='noopener';link.textContent='Open Studio';$('status').append(link);await recent();window.open(result.viewer_url,'_blank','noopener')}catch(error){$('status').textContent=error.message}finally{$('import-package').disabled=false}};
async function folders(path){try{const result=await request('/api/folders'+(path?'?path='+encodeURIComponent(path):''));browsingPath=result.path;$('browse-path').textContent=result.path;$('up').disabled=result.parent===result.path;$('up').onclick=()=>folders(result.parent);$('drive').replaceChildren(...result.drives.map(path=>new Option(path,path)));$('drive').value=result.drives.find(drive=>result.path.toLowerCase().startsWith(drive.toLowerCase()))||result.drives[0];$('folders').replaceChildren();for(const entry of result.folders){const li=document.createElement('li'),button=document.createElement('button');button.textContent=entry.name+(entry.is_project?' · Tuba project':'');button.onclick=()=>folders(entry.path);li.append(button);$('folders').append(li)}}catch(error){$('status').textContent=error.message}}
$('project-form').onsubmit=event=>{event.preventDefault();openProject('open')};$('new').onclick=()=>{if($('project-form').reportValidity())openProject('new')};$('browse').onclick=async()=>{await folders($('project-path').value||defaultFolder);$('browser').showModal()};$('close').onclick=()=>$('browser').close();$('choose').onclick=()=>{$('project-path').value=browsingPath;$('browser').close()};$('drive').onchange=()=>folders($('drive').value);recent().catch(error=>$('status').textContent=error.message);
</script></html>
"""
