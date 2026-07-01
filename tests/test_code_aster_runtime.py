import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from tuba.solver.code_aster_runtime import (
    CodeAsterRuntimeConfig,
    build_code_aster_command,
    discover_code_aster_runtimes,
    run_code_aster_export,
    select_code_aster_runtime,
)


class TestCodeAsterRuntime(unittest.TestCase):
    def test_wsl_command_uses_configured_distro_and_run_aster(self):
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            export_file = root / "study.export"
            export_file.write_text("", encoding="utf-8")

            command, cwd = build_code_aster_command(
                export_file,
                root,
                CodeAsterRuntimeConfig(exec_method="wsl", wsl_distro="Ubuntu"),
            )

        self.assertEqual(command[:4], ["wsl", "-d", "Ubuntu", "--"])
        self.assertIn("run_aster study.export", command[-1])
        self.assertIsNone(cwd)

    def test_command_mode_runs_configured_runner_in_work_dir(self):
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            export_file = root / "study.export"
            export_file.write_text("", encoding="utf-8")

            command, cwd = build_code_aster_command(
                export_file,
                root,
                CodeAsterRuntimeConfig(exec_method="command", runner_command="conda run -n tuba-code-aster run_aster"),
            )

        self.assertEqual(command, ["conda", "run", "-n", "tuba-code-aster", "run_aster", "study.export"])
        self.assertEqual(cwd, root)

    def test_explicit_command_mode_defaults_to_run_aster(self):
        candidate = select_code_aster_runtime(CodeAsterRuntimeConfig(exec_method="command", env={}))

        self.assertEqual(candidate.command, ("run_aster",))

    def test_python_bridge_uses_requested_python_executable(self):
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            export_file = root / "study.export"
            export_file.write_text("", encoding="utf-8")

            command, cwd = build_code_aster_command(
                export_file,
                root,
                CodeAsterRuntimeConfig(exec_method="python_bridge", bridge_python="/opt/codeaster/bin/python"),
            )

        self.assertEqual(command[0], "/opt/codeaster/bin/python")
        self.assertTrue(command[1].endswith("code_aster_bridge.py"))
        self.assertEqual(command[-1], "study.export")
        self.assertEqual(cwd, root)

    def test_discovery_uses_environment_defaults(self):
        env = {
            "TUBA_CODE_ASTER_EXEC_METHOD": "wsl",
            "TUBA_CODE_ASTER_WSL_DISTRO": "Ubuntu",
            "TUBA_CODE_ASTER_RUNNER_COMMAND": "run_aster",
        }

        candidates = discover_code_aster_runtimes(CodeAsterRuntimeConfig(env=env))
        wsl = next(candidate for candidate in candidates if candidate.method == "wsl")
        command = next(candidate for candidate in candidates if candidate.method == "command")

        self.assertEqual(wsl.command[:4], ("wsl", "-d", "Ubuntu", "--"))
        self.assertEqual(command.command, ("run_aster",))

    def test_auto_without_runner_does_not_claim_host_command_runtime(self):
        candidates = discover_code_aster_runtimes(CodeAsterRuntimeConfig(exec_method="auto", env={}))

        self.assertNotIn("command", {candidate.kind for candidate in candidates})

    def test_docker_command_mounts_workdir(self):
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            export_file = root / "study.export"
            export_file.write_text("", encoding="utf-8")

            command, cwd = build_code_aster_command(
                export_file,
                root,
                CodeAsterRuntimeConfig(exec_method="docker", docker_image="local/code-aster:dev", env={}),
            )

        self.assertEqual(command[:3], ["docker", "run", "--rm"])
        self.assertIn("local/code-aster:dev", command)
        self.assertIn("study.export", command[-1])
        self.assertIsNone(cwd)

    def test_run_writes_utf8_logs_and_raises_with_message_tail(self):
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            export_file = root / "study.export"
            export_file.write_text("", encoding="utf-8")
            (root / "study.mess").write_text("line 1\nfatal solver error\n", encoding="utf-8")

            def fake_run(cmd, **_kwargs):
                return subprocess.CompletedProcess(cmd, 2, stdout="solver stdout", stderr="solver stderr")

            with patch("tuba.solver.code_aster_runtime.subprocess.run", fake_run):
                with self.assertRaisesRegex(RuntimeError, "fatal solver error"):
                    run_code_aster_export(
                        export_file,
                        root,
                        CodeAsterRuntimeConfig(exec_method="command", runner_command="run_aster"),
                    )

            self.assertEqual((root / "stdout.log").read_text(encoding="utf-8"), "solver stdout")
            self.assertEqual((root / "stderr.log").read_text(encoding="utf-8"), "solver stderr")

    def test_run_code_aster_export_writes_per_runtime_logs(self):
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            export_file = root / "study.export"
            export_file.write_text("", encoding="utf-8")

            def fake_run(cmd, **_kwargs):
                return subprocess.CompletedProcess(cmd, 0, stdout="solver stdout", stderr="solver stderr")

            with patch("tuba.solver.code_aster_runtime.subprocess.run", fake_run):
                execution = run_code_aster_export(
                    export_file,
                    root,
                    CodeAsterRuntimeConfig(exec_method="command", runner_command="run_aster", env={}),
                )

            self.assertEqual(execution.returncode, 0)
            self.assertEqual(execution.runtime.kind, "command")
            self.assertEqual((root / "stdout.command.log").read_text(encoding="utf-8"), "solver stdout")
            self.assertEqual((root / "stderr.command.log").read_text(encoding="utf-8"), "solver stderr")

    def test_run_code_aster_export_captures_output_as_utf8(self):
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            export_file = root / "study.export"
            export_file.write_text("", encoding="utf-8")
            captured = {}

            def fake_run(cmd, **kwargs):
                captured["kwargs"] = kwargs
                return subprocess.CompletedProcess(cmd, 0, stdout=None, stderr=None)

            with patch("tuba.solver.code_aster_runtime.subprocess.run", fake_run):
                execution = run_code_aster_export(
                    export_file,
                    root,
                    CodeAsterRuntimeConfig(exec_method="command", runner_command="run_aster", env={}),
                )

            self.assertEqual(captured["kwargs"]["encoding"], "utf-8")
            self.assertEqual(captured["kwargs"]["errors"], "replace")
            self.assertEqual(execution.stdout, "")
            self.assertEqual(execution.stderr, "")

    def test_auto_mode_falls_back_from_missing_wsl_runner_to_docker(self):
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            export_file = root / "study.export"
            export_file.write_text("", encoding="utf-8")
            calls = []

            def fake_run(cmd, **_kwargs):
                calls.append(cmd)
                if cmd[0] == "wsl":
                    return subprocess.CompletedProcess(cmd, 127, stdout="", stderr="Code_Aster runner not found")
                return subprocess.CompletedProcess(cmd, 0, stdout="docker ok", stderr="")

            with patch("tuba.solver.code_aster_runtime.subprocess.run", fake_run):
                execution = run_code_aster_export(
                    export_file,
                    root,
                    CodeAsterRuntimeConfig(exec_method="auto", docker_image="local/code-aster:dev", env={}),
                )

        self.assertEqual(execution.runtime.kind, "docker")
        self.assertEqual(len(calls), 2)

    def test_auto_mode_falls_back_when_runtime_executable_is_missing(self):
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            export_file = root / "study.export"
            export_file.write_text("", encoding="utf-8")
            calls = []

            def fake_run(cmd, **_kwargs):
                calls.append(cmd)
                if cmd[0] == "wsl":
                    raise FileNotFoundError("wsl executable not found")
                return subprocess.CompletedProcess(cmd, 0, stdout="docker ok", stderr="")

            with patch("tuba.solver.code_aster_runtime.subprocess.run", fake_run):
                execution = run_code_aster_export(
                    export_file,
                    root,
                    CodeAsterRuntimeConfig(exec_method="auto", docker_image="local/code-aster:dev", env={}),
                )
            missing_wsl_log = (root / "stderr.wsl.log").read_text(encoding="utf-8")

        self.assertEqual(execution.runtime.kind, "docker")
        self.assertEqual(len(calls), 2)
        self.assertIn("wsl executable not found", missing_wsl_log)


if __name__ == "__main__":
    unittest.main()
