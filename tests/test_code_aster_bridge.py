import sys
import types
import unittest
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from tuba.solver import code_aster_bridge


class TestCodeAsterBridge(unittest.TestCase):
    def test_run_export_uses_run_aster_python_api_when_available(self):
        calls = {}

        class FakeExport:
            def __init__(self, filename=None, check=True):
                calls["export_filename"] = filename
                calls["export_check"] = check

        class FakeRunner:
            @classmethod
            def factory(cls, export, tee=False, output=None):
                calls["factory_tee"] = tee
                calls["factory_output"] = output
                calls["export"] = export
                return cls()

            def execute(self, workdir):
                calls["workdir"] = workdir
                return types.SimpleNamespace(exitcode=0)

        fake_run_aster = types.ModuleType("run_aster")
        fake_export_mod = types.ModuleType("run_aster.export")
        fake_export_mod.Export = FakeExport
        fake_run_mod = types.ModuleType("run_aster.run")
        fake_run_mod.RunAster = FakeRunner

        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            export_file = root / "study.export"
            export_file.write_text("", encoding="utf-8")
            with patch.dict(
                sys.modules,
                {
                    "run_aster": fake_run_aster,
                    "run_aster.export": fake_export_mod,
                    "run_aster.run": fake_run_mod,
                },
            ):
                exitcode = code_aster_bridge.run_export(export_file, root)

        self.assertEqual(exitcode, 0)
        self.assertEqual(calls["export_filename"], str(export_file.resolve()))
        self.assertTrue(calls["export_check"])
        self.assertTrue(calls["factory_tee"])
        self.assertEqual(calls["workdir"], str(root.resolve()))

    def test_run_export_falls_back_to_run_aster_cli(self):
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            export_file = root / "study.export"
            export_file.write_text("", encoding="utf-8")

            def fake_run(cmd, **kwargs):
                self.assertEqual(cmd, ["run_aster", str(export_file.resolve())])
                self.assertEqual(kwargs["cwd"], str(root.resolve()))
                return types.SimpleNamespace(returncode=0)

            with patch("tuba.solver.code_aster_bridge._run_export_with_python_api", side_effect=ImportError("missing")):
                with patch("tuba.solver.code_aster_bridge.subprocess.run", fake_run):
                    exitcode = code_aster_bridge.run_export(export_file, root)

        self.assertEqual(exitcode, 0)

    def test_main_returns_nonzero_when_export_is_missing(self):
        with patch("sys.stderr", new_callable=StringIO):
            exitcode = code_aster_bridge.main(["--export", "missing.export"])

        self.assertEqual(exitcode, 2)


if __name__ == "__main__":
    unittest.main()
