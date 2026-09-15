import json
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.request import urlopen

_BUILDER_SCRIPT = """from tuba import Model

model = Model("ScriptLink")
model.add_material("Steel", E=2.1e11, nu=0.3, rho=7850.0, alpha=1.2e-5)
model.add_pipe_section("DN100", OD=0.1143, WT=0.00602)
model.define_load_case("Operating", gravity=True, pressure=1.5e6, temperature=150.0)
with model.pipe(section="DN100", material="Steel") as builder:
    builder.start([0.0, 0.0, 0.0], support="anchor")
    builder.run(4.0)
    builder.bend(radius=0.3, angle=90.0, plane="XY")
    builder.add_support(type="guide")
    builder.run(2.0)
    builder.end(support="anchor")
"""

_SMALL_SCRIPT = """from tuba import Model

model = Model("StudioStart")
model.add_material("Steel", E=2.1e11, nu=0.3, rho=7850.0, alpha=1.2e-5)
model.add_pipe_section("DN100", OD=0.1143, WT=0.00602)
model.define_load_case("Operating", gravity=True, pressure=1.0e6)
with model.pipe(section="DN100", material="Steel") as builder:
    builder.start([0.0, 0.0, 0.0], support="anchor")
    builder.run(2.0)
    builder.end(support="anchor")
"""

_PROPERTY_SCRIPT = """from tuba import Model

model = Model("PropertyLines")
model.add_material("Steel", E=2.1e11, nu=0.3, rho=7850.0, alpha=1.2e-5)
model.add_pipe_section("DN100", OD=0.1143, WT=0.00602)
model.add_ibeam_section("IPE100", "IPE100")
start = model.add_node([0.0, 0.0, 0.0])
end = model.add_node([2.0, 0.0, 0.0])
model.add_element(id="pipe", type="pipe_straight", n1=start, n2=end, section="DN100", material="Steel")
model.add_support(node=start, type="anchor")
model.assign_attribute("element:pipe", "paint", "epoxy")
operating = model.define_load_case("Operating", gravity=True)
operating.add_nodal_force(end, [0.0, 0.0, -500.0])
hot = model.define_operation("Hot", temperature=150.0)
hot.add_nodal_force(end, [0.0, 0.0, -250.0])
"""


def _line_of(script: str, text: str) -> int:
    return next(number for number, line in enumerate(script.splitlines(), 1) if text in line)


class TestStudioServer(unittest.TestCase):
    def test_studio_server_serves_and_saves_model_py(self):
        tmpdir = self.enterContext(TemporaryDirectory())
        server = self._start_studio(Path(tmpdir))

        with urlopen(server.base_url + "api/script", timeout=10) as response:
            self.assertEqual(json.loads(response.read().decode("utf-8")), {"ok": True, "code": _SMALL_SCRIPT})

        status, payload = self._post_script(server, _BUILDER_SCRIPT)
        self.assertEqual(status, 200, payload)
        self.assertEqual(payload["elements"], 3)
        self.assertEqual(server.script_path.read_text(encoding="utf-8"), _BUILDER_SCRIPT)

    def _start_studio(self, root: Path, script: str = _SMALL_SCRIPT, **kwargs):
        from tuba.visualization.preview.server import ProjectStudioServer

        project = root / "project"
        project.mkdir()
        (project / "model.py").write_text(script, encoding="utf-8")
        server = ProjectStudioServer(project, root / "out", port=0, **kwargs).start()
        self.addCleanup(server.stop)
        return server

    def _post_script(self, server, code: str, **headers):
        from urllib.error import HTTPError
        from urllib.request import Request

        request = Request(
            server.base_url + "api/script",
            data=json.dumps({"code": code}).encode("utf-8"),
            headers={"Content-Type": "application/json", **headers},
            method="POST",
        )
        try:
            with urlopen(request, timeout=10) as response:
                return response.status, json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            return exc.code, json.loads(exc.read().decode("utf-8"))

    def _scene_objects(self, server) -> dict:
        scene = json.loads((server.out_dir / "build" / "scene.json").read_text(encoding="utf-8"))
        return {obj["name"]: obj for obj in scene["objects"]}

    def _wait_for(self, condition, message: str) -> None:
        deadline = time.time() + 5
        while time.time() < deadline:
            try:
                if condition():
                    return
            except (json.JSONDecodeError, FileNotFoundError, PermissionError):
                pass  # Windows can refuse a read mid-rename even though the write is atomic.
            time.sleep(0.05)
        self.fail(message)

    def test_studio_server_refuses_cross_origin_posts(self):
        # Without this, any web page could POST a script here and run Python on this machine.
        tmpdir = self.enterContext(TemporaryDirectory())
        server = self._start_studio(Path(tmpdir))

        status, payload = self._post_script(server, _BUILDER_SCRIPT, Origin="http://evil.example")
        self.assertEqual((status, payload), (403, {"ok": False, "error": "cross-origin request refused"}))
        # DNS rebinding: the page is "same-origin", but on a foreign host name.
        rebound = f"evil.example:{server.port}"
        status, _payload = self._post_script(server, _BUILDER_SCRIPT, Host=rebound, Origin=f"http://{rebound}")
        self.assertEqual(status, 403)
        self.assertEqual(server.script_path.read_text(encoding="utf-8"), _SMALL_SCRIPT)

        status, payload = self._post_script(server, _BUILDER_SCRIPT, Origin=f"http://127.0.0.1:{server.port}")
        self.assertEqual(status, 200, payload)
        self.assertEqual(server.script_path.read_text(encoding="utf-8"), _BUILDER_SCRIPT)

    def test_studio_refuses_reads_from_foreign_pages_and_hosts(self):
        # A wildcard CORS header let any web page open in the browser read model.py.
        from urllib.error import HTTPError
        from urllib.request import Request

        root = Path(self.enterContext(TemporaryDirectory()))
        server = self._start_studio(root)

        def request(path: str, method: str = "GET", **headers):
            try:
                with urlopen(Request(server.base_url + path, headers=headers, method=method), timeout=10) as response:
                    return response.status, response.headers, response.read()
            except HTTPError as exc:
                return exc.code, exc.headers, exc.read()

        refused = {"ok": False, "error": "cross-origin request refused"}
        status, _headers, body = request("api/script", Origin="http://evil.example")
        self.assertEqual((status, json.loads(body)), (403, refused))
        # DNS rebinding: a foreign host name that resolves to 127.0.0.1.
        self.assertEqual(request("api/script", Host=f"evil.example:{server.port}")[0], 403)
        self.assertEqual(request("api/script", "OPTIONS", Origin="http://evil.example")[0], 403)
        # Only a whole loopback origin counts: not a look-alike host name, not an opaque origin.
        self.assertEqual(request("api/script", Origin="http://localhost.evil.example")[0], 403)
        self.assertEqual(request("api/script", Origin="null")[0], 403)

        status, headers, body = request("api/script")
        self.assertEqual((status, json.loads(body)["code"]), (200, _SMALL_SCRIPT))
        self.assertIsNone(headers["Access-Control-Allow-Origin"])

        # A loopback dev page (the Vite dev server) may read, bundles included.
        status, headers, _body = request("api/script", Origin="http://localhost:5173")
        self.assertEqual((status, headers["Access-Control-Allow-Origin"]), (200, "http://localhost:5173"))
        status, headers, _body = request("build/scene.json", Origin="http://127.0.0.1:5173")
        self.assertEqual((status, headers["Access-Control-Allow-Origin"]), (200, "http://127.0.0.1:5173"))

    def test_studio_websocket_refuses_foreign_pages(self):
        import socket

        root = Path(self.enterContext(TemporaryDirectory()))
        server = self._start_studio(root)

        def status_line(*lines: str) -> bytes:
            with socket.create_connection(("127.0.0.1", server.port), timeout=5) as sock:
                sock.sendall(("\r\n".join(lines) + "\r\n\r\n").encode("ascii"))
                return sock.recv(4096).split(b"\r\n", 1)[0]

        upgrade = (
            "GET /preview/ws HTTP/1.1",
            "Upgrade: websocket",
            "Connection: Upgrade",
            "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==",
            "Sec-WebSocket-Version: 13",
        )
        local = f"Host: 127.0.0.1:{server.port}"
        self.assertIn(b" 403 ", status_line(*upgrade, local, "Origin: http://evil.example"))
        self.assertIn(b" 101 ", status_line(*upgrade, local, "Origin: http://localhost:5173"))
        # DNS rebinding: a loopback Origin does not excuse a foreign Host on the upgrade.
        self.assertIn(b" 403 ", status_line(*upgrade, f"Host: evil.example:{server.port}", "Origin: http://localhost:5173"))
        # A refusal still answers when Content-Length will not parse.
        self.assertIn(b" 403 ", status_line("GET /api/script HTTP/1.1", local, "Origin: http://evil.example", "Content-Length: abc"))

    def _raw_request(self, server, request_line: str, *headers: str) -> tuple[bytes, bytes]:
        """Send a hand-written request to the studio's host and return the answer's status line and
        body. The server closes the connection after every answer, so this reads to the end."""
        import socket

        request = "\r\n".join((request_line, f"Host: 127.0.0.1:{server.port}", *headers)) + "\r\n\r\n"
        with socket.create_connection(("127.0.0.1", server.port), timeout=5) as sock:
            sock.sendall(request.encode("ascii"))
            response = b""
            while chunk := sock.recv(65536):
                response += chunk
        head, _, body = response.partition(b"\r\n\r\n")
        return head.split(b"\r\n", 1)[0], body

    def test_studio_answers_a_post_whose_content_length_will_not_parse(self):
        # int() raised on the header in do_POST, and the connection dropped without an answer.
        root = Path(self.enterContext(TemporaryDirectory()))
        server = self._start_studio(root)
        origin = f"Origin: http://127.0.0.1:{server.port}"

        for path in ("/api/script", "/api/solve"):
            status, body = self._raw_request(server, f"POST {path} HTTP/1.1", origin, "Content-Length: abc")
            self.assertIn(b" 400 ", status, path)
            # Refused before any handler runs: without a study, /api/solve's own answer is a 400 too.
            self.assertEqual(json.loads(body), {"ok": False, "error": "invalid Content-Length"}, path)
        self.assertEqual(server.script_path.read_text(encoding="utf-8"), _SMALL_SCRIPT)

    def test_studio_answers_a_content_length_too_large_to_read(self):
        # Past sys.maxsize, reading the body raised OverflowError and dropped the connection; below
        # it, a refusal read a body of any size into memory before its 403.
        root = Path(self.enterContext(TemporaryDirectory()))
        server = self._start_studio(root)
        huge = "Content-Length: 99999999999999999999999"

        status, body = self._raw_request(server, "POST /api/script HTTP/1.1", f"Origin: http://127.0.0.1:{server.port}", huge)
        self.assertIn(b" 400 ", status)
        self.assertEqual(json.loads(body), {"ok": False, "error": "invalid Content-Length"})
        self.assertEqual(server.script_path.read_text(encoding="utf-8"), _SMALL_SCRIPT)
        refusal = ("GET /api/script HTTP/1.1", "Origin: http://evil.example")
        self.assertIn(b" 403 ", self._raw_request(server, *refusal, huge)[0])
        # Just past the 16 MiB cap, the 403 does not wait for the body (none is sent here).
        self.assertIn(b" 403 ", self._raw_request(server, *refusal, f"Content-Length: {16 * 1024 * 1024 + 1}")[0])

    def test_studio_refuses_a_script_save_without_string_code(self):
        # A POST without "code", an empty body included, saved an empty model.py.
        root = Path(self.enterContext(TemporaryDirectory()))
        server = self._start_studio(root)
        refused = {"ok": False, "error": 'a script save needs a string "code"'}

        status, body = self._raw_request(server, "POST /api/script HTTP/1.1", f"Origin: http://127.0.0.1:{server.port}", "Content-Length: 0")
        self.assertEqual(server.script_path.read_text(encoding="utf-8"), _SMALL_SCRIPT)
        self.assertIn(b" 400 ", status)
        self.assertEqual(json.loads(body), refused)
        self.assertEqual(self._post_script(server, 5), (400, refused))
        self.assertEqual(server.script_path.read_text(encoding="utf-8"), _SMALL_SCRIPT)
        # An explicit empty script is still a save.
        self._post_script(server, "")
        self.assertEqual(server.script_path.read_text(encoding="utf-8"), "")

    def test_studio_responses_forbid_framing_and_cross_site_embedding(self):
        # Another site must not frame the studio to trick a click on Solve or a script save,
        # nor embed its responses through <img>, <script> or <link>.
        from urllib.error import HTTPError
        from urllib.request import Request

        root = Path(self.enterContext(TemporaryDirectory()))
        server = self._start_studio(root)

        def response_to(path: str, **headers):
            try:
                with urlopen(Request(server.base_url + path, headers=headers), timeout=10) as response:
                    return response.status, response.headers
            except HTTPError as exc:
                exc.close()
                return exc.code, exc.headers

        responses = {
            "model.py": response_to("api/script"),
            "viewer page": response_to(""),
            "refusal": response_to("api/script", Origin="http://evil.example"),
        }
        self.assertEqual([status for status, _headers in responses.values()], [200, 200, 403])
        expected = {
            "Cross-Origin-Resource-Policy": ["same-site"],
            "X-Frame-Options": ["SAMEORIGIN"],
            "Content-Security-Policy": ["frame-ancestors 'self' http://localhost:* http://127.0.0.1:* vscode-webview: vscode-file:"],
        }
        for name, (_status, headers) in responses.items():
            self.assertEqual({header: headers.get_all(header) for header in expected}, expected, name)

    def test_studio_server_script_errors_point_at_the_script_line(self):
        broken = (
            "from tuba import Model\n"
            "\n"
            'model = Model("Broken")\n'
            'with model.pipe(section="DN100", material="Steel") as builder:\n'
            "    builder.rn(4.0)\n"
        )
        tmpdir = self.enterContext(TemporaryDirectory())
        server = self._start_studio(Path(tmpdir))

        status, payload = self._post_script(server, broken)
        self.assertEqual(status, 400)
        self.assertEqual(set(payload), {"ok", "error", "line", "traceback"})
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["line"], 5)
        self.assertTrue(payload["error"].startswith("AttributeError"), payload["error"])

        # sys.exit() fails the run instead of killing the request.
        status, payload = self._post_script(server, "import sys\nsys.exit(3)\n")
        self.assertEqual((status, payload["error"], payload["line"]), (400, "SystemExit: 3", 2))

        # A syntax error has no model.py frame in its traceback; it carries its own line.
        status, payload = self._post_script(server, "x = 1\ndef broken(:\n")
        self.assertEqual((status, payload["line"]), (400, 2))
        self.assertTrue(payload["error"].startswith("SyntaxError"), payload["error"])

    def test_studio_server_links_scene_objects_to_script_lines(self):
        tmpdir = self.enterContext(TemporaryDirectory())
        server = self._start_studio(Path(tmpdir))

        status, payload = self._post_script(server, _BUILDER_SCRIPT)
        self.assertEqual(status, 200, payload)

        lines = {name: obj.get("metadata", {}).get("source_line") for name, obj in self._scene_objects(server).items()}
        self.assertEqual(lines["pipe_str_0"], _line_of(_BUILDER_SCRIPT, "builder.run(4.0)"))
        self.assertEqual(lines["pipe_bend_0"], _line_of(_BUILDER_SCRIPT, "builder.bend("))
        self.assertEqual(lines["support_0"], _line_of(_BUILDER_SCRIPT, "builder.start("))
        self.assertEqual(lines["support_1"], _line_of(_BUILDER_SCRIPT, "builder.add_support("))

    def test_studio_server_reruns_model_py_saved_by_another_editor(self):
        tmpdir = self.enterContext(TemporaryDirectory())
        server = self._start_studio(Path(tmpdir), _BUILDER_SCRIPT, poll_interval_s=0.05, debounce_s=0.05)
        script_path = server.script_path
        self.assertIn("pipe_str_1", self._scene_objects(server))  # the initial run executes model.py

        longer = _BUILDER_SCRIPT.replace("builder.run(2.0)", "builder.run(2.0)\n    builder.run(1.0)")
        script_path.write_text(longer, encoding="utf-8")
        self._wait_for(lambda: "pipe_str_2" in self._scene_objects(server), "a saved model.py did not reach the scene")

        broken = longer.replace("builder.run(1.0)", "builder.rn(1.0)")
        script_path.write_text(broken, encoding="utf-8")

        def script_errors():
            # A poll can land on the truncated file; that run fails without a line.
            return [event for event in server.broker.events if event.get("type") == "script_error" and event.get("line")]

        self._wait_for(script_errors, "a failing model.py did not broadcast script_error")
        event = script_errors()[0]
        self.assertEqual(set(event), {"type", "error", "line"})
        self.assertEqual(event["line"], _line_of(broken, "builder.rn("))
        self.assertTrue(event["error"].startswith("AttributeError"), event["error"])
        self._wait_for(lambda: "pipe_str_2" in self._scene_objects(server), "a failing model.py replaced the last good scene")

    def test_studio_server_websocket_survives_an_idle_viewer(self):
        # The handler used to read with a 0.5 s timeout, which poisons the buffered
        # socket file: every viewer was dropped half a second after connecting.
        import socket

        tmpdir = self.enterContext(TemporaryDirectory())
        server = self._start_studio(Path(tmpdir))
        handshake = (
            f"GET /preview/ws HTTP/1.1\r\nHost: 127.0.0.1:{server.port}\r\n"
            "Upgrade: websocket\r\nConnection: Upgrade\r\n"
            "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\nSec-WebSocket-Version: 13\r\n\r\n"
        ).encode("ascii")
        with socket.create_connection(("127.0.0.1", server.port), timeout=5) as sock:
            sock.sendall(handshake)
            self.assertIn(b"101", sock.recv(4096))
            time.sleep(1.5)
            server.broker.broadcast({"type": "idle_probe"})
            received = b""
            while b"idle_probe" not in received:
                chunk = sock.recv(65536)
                self.assertTrue(chunk, "the server hung up on an idle viewer")
                received += chunk

    def test_studio_transport_refuses_a_port_another_server_is_serving(self):
        # Windows let a second server share a port an older studio still served
        # (SO_REUSEADDR), and the browser kept talking to the old one.
        from tuba.visualization.preview.server import PreviewServer

        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            script = root / "model.py"
            script.write_text("", encoding="utf-8")
            first = PreviewServer(script, root / "first", port=0).start()
            try:
                with self.assertRaises(OSError):
                    PreviewServer(script, root / "second", port=first.port).start()
            finally:
                first.stop()

    def test_builder_links_lines_only_for_the_running_script(self):
        # model.py runs as __main__; any other caller (the MCP server, a test) gets no
        # line rather than one from a file the viewer does not show.
        linked: dict = {"__name__": "__main__"}
        exec(compile(_BUILDER_SCRIPT, "model.py", "exec"), linked)
        other: dict = {"__name__": "somewhere_else"}
        exec(compile(_BUILDER_SCRIPT, "model.py", "exec"), other)

        self.assertEqual(linked["model"].elements[0].source_line, _line_of(_BUILDER_SCRIPT, "builder.run(4.0)"))
        self.assertEqual({element.source_line for element in other["model"].elements}, {None})

    def test_property_records_link_to_the_lines_that_define_them(self):
        linked: dict = {"__name__": "__main__"}
        exec(compile(_PROPERTY_SCRIPT, "model.py", "exec"), linked)
        other: dict = {"__name__": "somewhere_else"}
        exec(compile(_PROPERTY_SCRIPT, "model.py", "exec"), other)
        model = linked["model"]

        def line(text: str) -> int:
            return _line_of(_PROPERTY_SCRIPT, text)

        self.assertEqual(model.materials["Steel"].source_line, line("model.add_material("))
        self.assertEqual(model.sections["DN100"].source_line, line("model.add_pipe_section("))
        self.assertEqual(model.sections["IPE100"].source_line, line("model.add_ibeam_section("))
        self.assertEqual(
            [node.source_line for node in model.nodes.values()],
            [line("start = model.add_node("), line("end = model.add_node(")],
        )
        self.assertEqual(model.attributes[0].source_line, line("model.assign_attribute("))
        self.assertEqual(model.load_cases["Operating"].source_line, line("model.define_load_case("))
        self.assertEqual(model.load_cases["Operating"].nodal_forces[0].source_line, line("operating.add_nodal_force("))
        self.assertEqual(model.operations["Hot"].source_line, line("model.define_operation("))
        self.assertEqual(model.operations["Hot"].nodal_forces[0].source_line, line("hot.add_nodal_force("))

        def records(built) -> list:
            return [
                *built.materials.values(), *built.sections.values(), *built.nodes.values(), *built.attributes,
                *built.load_cases.values(), *built.operations.values(),
                *built.load_cases["Operating"].nodal_forces, *built.operations["Hot"].nodal_forces,
            ]

        self.assertEqual({record.source_line for record in records(other["model"])}, {None})
        # A line says where a record came from, not what it is: records still compare equal.
        self.assertEqual(model.materials, other["model"].materials)
        self.assertEqual(model.attributes, other["model"].attributes)

    def test_a_helper_called_twice_links_each_copy_to_its_own_call(self):
        # The friction example builds two copies with one helper in model.py: the
        # helper's line is shared, the call line tells the copies apart.
        script = (
            "from tuba import Model\n"
            "\n"
            'model = Model("Copies")\n'
            'model.add_material("Steel", E=2.1e11, nu=0.3, rho=7850.0, alpha=1.2e-5)\n'
            'model.add_pipe_section("DN100", OD=0.1143, WT=0.00602)\n'
            "\n"
            "def add_copy(prefix, y):\n"
            "    a = model.add_node([0.0, y, 0.0])\n"
            "    b = model.add_node([1.0, y, 0.0])\n"
            '    model.add_element(id=f"{prefix}_pipe", type="pipe_straight", n1=a, n2=b, section="DN100", material="Steel")\n'
            '    model.add_support(node=a, type="anchor", id=f"{prefix}_anchor")\n'
            "\n"
            'add_copy("NF", 0.0)\n'
            'add_copy("F", 5.0)\n'
            'model.add_element(id="direct", type="pipe_straight", n1="N0", n2="N2", section="DN100", material="Steel")\n'
        )
        namespace: dict = {"__name__": "__main__"}
        exec(compile(script, "model.py", "exec"), namespace)
        elements = {element.id: element for element in namespace["model"].elements}
        supports = {support.id: support for support in namespace["model"].supports}

        lines = lambda item: (item.source_line, item.source_call_line)
        self.assertEqual(lines(elements["NF_pipe"]), (10, 13))
        self.assertEqual(lines(elements["F_pipe"]), (10, 14))
        self.assertEqual(lines(supports["F_anchor"]), (11, 14))
        self.assertEqual(lines(elements["direct"]), (15, None))

    def test_blank_line_moves_source_lines_but_not_the_solver_fingerprint(self):
        from tuba.analysis.provenance import build_solver_input_identity

        models = []
        for code in (_BUILDER_SCRIPT, _BUILDER_SCRIPT.replace("model.add_material", "\nmodel.add_material")):
            namespace: dict = {"__name__": "__main__"}  # how the studio runs model.py
            exec(compile(code, "model.py", "exec"), namespace)
            models.append(namespace["model"])
        lines = [
            [
                item.source_line
                for item in [*model.elements, *model.supports, *model.nodes.values(), *model.materials.values()]
            ]
            for model in models
        ]

        self.assertEqual([line + 1 for line in lines[0]], lines[1])
        self.assertEqual(
            build_solver_input_identity(models[0], "Operating").fingerprint,
            build_solver_input_identity(models[1], "Operating").fingerprint,
        )


if __name__ == "__main__":
    unittest.main()


