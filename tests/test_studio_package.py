"""The browser handoff uses the shared package owner and keeps local HTTP boundaries."""
import io
import json
import tarfile
from urllib.error import HTTPError
from urllib.parse import quote
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
                "Content-Type": "application/octet-stream", "X-Project-Destination": quote(str(destination)), **(headers or {})})
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
        with urlopen(studio_url + "api/package/preview?results=0", timeout=20) as response:
            assert json.loads(response.read())["file_count"] == 2
        with urlopen(studio_url + "api/package/export?results=0&format=" + archive_format, timeout=20) as response:
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
                                        ("export?format=unknown", None, 400), ("export?format=tgz&format=zip", None, 400)]:
            try:
                response = urlopen(Request(studio_url + "api/package/" + route, headers={"Origin": origin} if origin else {}), timeout=20)
            except HTTPError as exc:
                response = exc
            with response:
                assert response.status == expected
        (destination / "model.py").write_text("model = None\n")
        try:
            response = urlopen(studio_url + "api/package/preview?results=1", timeout=20)
        except HTTPError as exc:
            response = exc
        with response:
            assert response.status == 400
            assert "TubaModel" in json.loads(response.read())["error"]
    finally:
        launcher.stop()
