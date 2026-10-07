"""The browser handoff uses the shared package owner and keeps local HTTP boundaries."""
import io
import json
import tarfile
from urllib.error import HTTPError
from urllib.parse import parse_qs, quote, urlsplit
from urllib.request import Request, urlopen
import zipfile
import pytest

from tuba.project.package import export_project_package
from tuba.studio_launcher import StudioLauncher, create_project


@pytest.mark.parametrize("archive_format", ["zip", "tgz"])
def test_package_upload_export_and_local_request_guards(tmp_path, archive_format):
    source = tmp_path / "source"
    create_project(source)
    suffix = ".tgz" if archive_format == "tgz" else ".tubaproject"
    archive = tmp_path / ("shared" + suffix)
    export_project_package(source, archive)
    destination = tmp_path / "Opened ü"
    launcher = StudioLauncher(tmp_path / "state").start()
    try:
        def upload(headers=None):
            request = Request(launcher.base_url + "api/projects/import", data=archive.read_bytes(), headers={
                "Authorization": "Bearer " + launcher.access_token, "Content-Type": "application/octet-stream", "X-Project-Destination": quote(str(destination)), **(headers or {})})
            try:
                return urlopen(request, timeout=20)
            except HTTPError as exc:
                return exc
        with upload({"Origin": "https://foreign.invalid"}) as response:
            assert response.status == 403
        assert not destination.exists()
        with upload() as response:
            assert response.status == 200
            opened = json.loads(response.read())
        assert opened["project_root"] == str(destination)
        assert (destination / "model.py").read_bytes() == (source / "model.py").read_bytes()
        with upload() as response:
            assert response.status == 400
        studio_url = opened["viewer_url"].split("?", 1)[0]
        token = parse_qs(urlsplit(opened["viewer_url"]).fragment)["tuba_token"][0]
        def studio_request(route, *, body=None, headers=None):
            request = Request(studio_url + route, data=json.dumps(body).encode() if body is not None else None,
                              headers={"Authorization": "Bearer " + token, "Content-Type": "application/json", **(headers or {})})
            try:
                return urlopen(request, timeout=20)
            except HTTPError as exc:
                return exc
        with studio_request("api/package/preview?results=0") as response:
            preview = json.loads(response.read())
            assert preview["file_count"] == 2
        with studio_request("api/package/export", body={"operation_nonce": preview["operation_nonce"], "results": False, "format": archive_format}) as response:
            assert response.headers.get_content_type() == ("application/gzip" if archive_format == "tgz" else "application/zip")
            assert suffix in response.headers["Content-Disposition"]
            payload = io.BytesIO(response.read())
            if archive_format == "tgz":
                with tarfile.open(fileobj=payload, mode="r:gz") as bundle:
                    assert bundle.extractfile("project/model.py").read() == (source / "model.py").read_bytes()
            else:
                with zipfile.ZipFile(payload) as bundle:
                    assert bundle.read("project/model.py") == (source / "model.py").read_bytes()
        for route, origin, expected in [("preview?results=1", None, 400), ("preview?results=2", None, 400),
                                        ("export?results=0", "https://foreign.invalid", 403),
                                        ("export?format=unknown", None, 405), ("export?format=tgz&format=zip", None, 405)]:
            try:
                response = studio_request("api/package/" + route, headers={"Origin": origin} if origin else {})
            except HTTPError as exc:
                response = exc
            with response:
                assert response.status == expected
        (destination / "model.py").write_text("model = None\n")
        try:
            response = studio_request("api/package/preview?results=1")
        except HTTPError as exc:
            response = exc
        with response:
            assert response.status == 400
            assert "TubaModel" in json.loads(response.read())["error"]
    finally:
        launcher.stop()
