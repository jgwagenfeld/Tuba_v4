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
    def test_env_python_bridge_has_first_priority_in_auto_mode(self):
        env = {"TUBA_CODE_ASTER_PYTHON": "/opt/aster/bin/python"}
        config = CodeAsterRuntimeConfig(exec_method="auto", env=env)

        candidates = discover_code_aster_runtimes(config)

        self.assertEqual(candidates[0].kind, "python_bridge")
        self.assertEqual(candidates[0].command, ("/opt/aster/bin/python",))
        self.assertTrue(candidates[0].available)

    def test_python_bridge_command_runs_local_bridge_script(self):
        config = CodeAsterRuntimeConfig(exec_method="python_bridge", bridge_python="/opt/aster/bin/python", env={})
        candidate = select_code_aster_runtime(config)

        with TemporaryDirectory() as tmpdir:
            cmd = build_code_aster_command(candidate, Path(tmpdir) / "study.export", Path(tmpdir))

        self.assertEqual(cmd[0], "/opt/aster/bin/python")
        self.assertTrue(cmd[1].endswith("code_aster_bridge.py"))
        self.assertIn("--export", cmd)
        self.assertIn("study.export", cmd)

    def test_explicit_runner_command_builds_shell_runner(self):
        config = CodeAsterRuntimeConfig(exec_method="command", runner_command="run_aster", env={})
        candidate = select_code_aster_runtime(config)

        with TemporaryDirectory() as tmpdir:
            cmd = build_code_aster_command(candidate, Path(tmpdir) / "study.export", Path(tmpdir))

        self.assertEqual(cmd[:2], ["run_aster", "study.export"])

    def test_wsl_command_uses_posix_workdir_and_runner_detection(self):
        config = CodeAsterRuntimeConfig(exec_method="wsl", env={})
        candidate = select_code_aster_runtime(config)

        cmd = build_code_aster_command(
            candidate,
            Path("D:/Gitprojects/Tuba_v4/code_aster_study/study.export"),
            Path("D:/Gitprojects/Tuba_v4/code_aster_study"),
        )

        self.assertEqual(cmd[:3], ["wsl", "bash", "-lc"])
        self.assertIn("/mnt/d/Gitprojects/Tuba_v4/code_aster_study", cmd[3])
        self.assertIn("run_aster study.export", cmd[3])
        self.assertIn("as_run study.export", cmd[3])

    def test_wsl_command_can_target_explicit_distro(self):
        config = CodeAsterRuntimeConfig(exec_method="wsl", wsl_distro="Ubuntu", env={})
        candidate = select_code_aster_runtime(config)

        cmd = build_code_aster_command(
            candidate,
            Path("D:/Gitprojects/Tuba_v4/code_aster_study/study.export"),
            Path("D:/Gitprojects/Tuba_v4/code_aster_study"),
        )

        self.assertEqual(cmd[:5], ["wsl", "-d", "Ubuntu", "--", "bash"])
        self.assertEqual(cmd[5], "-lc")
        self.assertIn("/mnt/d/Gitprojects/Tuba_v4/code_aster_study", cmd[6])

    def test_wsl_distro_can_come_from_environment(self):
        env = {"TUBA_CODE_ASTER_WSL_DISTRO": "Ubuntu"}
        config = CodeAsterRuntimeConfig(exec_method="wsl", env=env)

        candidate = select_code_aster_runtime(config)

        self.assertEqual(candidate.command, ("wsl", "-d", "Ubuntu", "--"))

    def test_docker_command_mounts_workdir(self):
        config = CodeAsterRuntimeConfig(exec_method="docker", docker_image="local/code-aster:dev", env={})
        candidate = select_code_aster_runtime(config)

        with TemporaryDirectory() as tmpdir:
            cmd = build_code_aster_command(candidate, Path(tmpdir) / "study.export", Path(tmpdir))

        self.assertEqual(cmd[:3], ["docker", "run", "--rm"])
        self.assertIn("local/code-aster:dev", cmd)
        self.assertIn("study.export", cmd[-1])

    def test_run_code_aster_export_writes_per_runtime_logs(self):
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            export_file = root / "study.export"
            export_file.write_text("", encoding="utf-8")
            config = CodeAsterRuntimeConfig(exec_method="command", runner_command="run_aster", env={})

            def fake_run(cmd, **_kwargs):
                return subprocess.CompletedProcess(cmd, 0, stdout="solver stdout", stderr="solver stderr")

            with patch("tuba.solver.code_aster_runtime.subprocess.run", fake_run):
                execution = run_code_aster_export(export_file, root, config)

            self.assertEqual(execution.returncode, 0)
            self.assertEqual(execution.runtime.kind, "command")
            self.assertEqual((root / "stdout.command.log").read_text(encoding="utf-8"), "solver stdout")
            self.assertEqual((root / "stderr.command.log").read_text(encoding="utf-8"), "solver stderr")

    def test_run_code_aster_export_captures_output_as_utf8(self):
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            export_file = root / "study.export"
            export_file.write_text("", encoding="utf-8")
            config = CodeAsterRuntimeConfig(exec_method="command", runner_command="run_aster", env={})
            captured = {}

            def fake_run(cmd, **kwargs):
                captured["kwargs"] = kwargs
                return subprocess.CompletedProcess(cmd, 0, stdout=None, stderr=None)

            with patch("tuba.solver.code_aster_runtime.subprocess.run", fake_run):
                execution = run_code_aster_export(export_file, root, config)

            self.assertEqual(captured["kwargs"]["encoding"], "utf-8")
            self.assertEqual(captured["kwargs"]["errors"], "replace")
            self.assertEqual(execution.stdout, "")
            self.assertEqual(execution.stderr, "")

    def test_auto_mode_falls_back_from_missing_wsl_runner_to_docker(self):
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            export_file = root / "study.export"
            export_file.write_text("", encoding="utf-8")
            config = CodeAsterRuntimeConfig(exec_method="auto", docker_image="local/code-aster:dev", env={})
            calls = []

            def fake_run(cmd, **_kwargs):
                calls.append(cmd)
                if cmd[0] == "wsl":
                    return subprocess.CompletedProcess(cmd, 127, stdout="", stderr="Code_Aster runner not found")
                return subprocess.CompletedProcess(cmd, 0, stdout="docker ok", stderr="")

            with patch("tuba.solver.code_aster_runtime.subprocess.run", fake_run):
                execution = run_code_aster_export(export_file, root, config)

        self.assertEqual(execution.runtime.kind, "docker")
        self.assertEqual(len(calls), 2)

    def test_auto_mode_falls_back_when_runtime_executable_is_missing(self):
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            export_file = root / "study.export"
            export_file.write_text("", encoding="utf-8")
            config = CodeAsterRuntimeConfig(exec_method="auto", docker_image="local/code-aster:dev", env={})
            calls = []

            def fake_run(cmd, **_kwargs):
                calls.append(cmd)
                if cmd[0] == "wsl":
                    raise FileNotFoundError("wsl executable not found")
                return subprocess.CompletedProcess(cmd, 0, stdout="docker ok", stderr="")

            with patch("tuba.solver.code_aster_runtime.subprocess.run", fake_run):
                execution = run_code_aster_export(export_file, root, config)

            self.assertEqual(execution.runtime.kind, "docker")
            self.assertIn("wsl executable not found", (root / "stderr.wsl.log").read_text(encoding="utf-8"))
            self.assertEqual(len(calls), 2)


if __name__ == "__main__":
    unittest.main()
