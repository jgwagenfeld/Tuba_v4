import json
import subprocess
import unittest
from pathlib import Path, PureWindowsPath
from tempfile import TemporaryDirectory
from unittest.mock import patch

from tuba.solver.code_aster_runtime import (
    CodeAsterExecution,
    CodeAsterRuntimeCandidate,
    CodeAsterRuntimeConfig,
    attested_code_aster_files,
    build_code_aster_command,
    build_code_aster_preflight_command,
    discover_code_aster_runtimes,
    run_code_aster_export,
    select_code_aster_runtime,
)
from tuba import Model
from tuba.solver.aster import CodeAsterSolver


class TestCodeAsterRuntime(unittest.TestCase):
    def test_beam_only_attestation_does_not_require_pipe_stress_table(self):
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "study_manifest.json").write_text(
                '{"study": {"metadata": {"pipe_stress_exported": false}}}',
                encoding="utf-8",
            )

            files = attested_code_aster_files(root)

        self.assertNotIn("study_sieq.csv", files)

    def test_successful_solve_writes_observed_execution_attestation(self):
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            model = Model(project_name="AttestedRun")
            model.add_material("Steel", E=2.0e11, nu=0.3, allowable_stress={20.0: 137e6})
            model.add_pipe_section("PipeSec", OD=0.1, WT=0.01)
            n0 = model.add_node([0.0, 0.0, 0.0])
            n1 = model.add_node([1.0, 0.0, 0.0])
            model.add_element(id="pipe_0", type="pipe_straight", n1=n0, n2=n1, section="PipeSec", material="Steel")
            model.add_support(node=n0, type="anchor", id="support_anchor_0")
            model.define_load_case("Hot", gravity=True, temperature=120.0, ref_temperature=20.0)
            solver = CodeAsterSolver(work_dir=root)
            identity = solver.export_analysis_study(model, "Hot", root).solver_input_identity
            (root / "study.mess").write_text("Code_Aster\nVersion 18.0.12\n", encoding="utf-8")
            for filename in ("study.rmed", "study_depl.csv", "study_effo.csv", "study_reac.csv", "study_sieq.csv"):
                (root / filename).write_text(filename, encoding="utf-8")
            execution = CodeAsterExecution(CodeAsterRuntimeCandidate("wsl", ("wsl",)), (), 0, "", "")

            with patch("tuba.solver.aster.run_code_aster_export", return_value=execution):
                with patch("tuba.analysis.code_aster_artifacts.import_code_aster_artifacts", return_value=object()):
                    solver.solve_exported_study(model, solver.export_analysis_study(model, "Hot", root))

            attestation = json.loads((root / "study_execution.json").read_text(encoding="utf-8"))
        self.assertEqual(attestation["schema_version"], "tuba.code_aster_execution.v1")
        self.assertEqual(attestation["solver_name"], "Code_Aster")
        self.assertEqual(attestation["solver_version"], "18.0.12")
        self.assertEqual(attestation["execution_method"], "wsl")
        self.assertEqual(attestation["solver_input_identity"]["fingerprint"], identity.fingerprint)
        self.assertGreater(attestation["artifacts"]["study_depl.csv"]["size_bytes"], 0)
        self.assertEqual(len(attestation["artifacts"]["study_depl.csv"]["sha256"]), 64)
        self.assertNotIn("command", attestation)

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

    def test_auto_without_wsl_env_tries_ubuntu_before_default_wsl(self):
        candidates = discover_code_aster_runtimes(CodeAsterRuntimeConfig(exec_method="auto", env={}))
        wsl_commands = [candidate.command for candidate in candidates if candidate.kind == "wsl"]

        self.assertGreaterEqual(len(wsl_commands), 2)
        self.assertEqual(wsl_commands[0], ("wsl", "-d", "Ubuntu", "--"))
        self.assertEqual(wsl_commands[1], ("wsl",))

    def test_default_preflight_timeout_allows_cold_wsl_start(self):
        self.assertGreaterEqual(CodeAsterRuntimeConfig().preflight_timeout_seconds, 30)

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

    def test_wsl_preflight_uses_real_workdir_contract_and_does_not_mask_runner_failure(self):
        root = PureWindowsPath("C:/Tuba Work")
        candidate = select_code_aster_runtime(CodeAsterRuntimeConfig(exec_method="wsl", wsl_distro="Ubuntu", env={}))

        command, cwd = build_code_aster_preflight_command(candidate, CodeAsterRuntimeConfig(exec_method="wsl", wsl_distro="Ubuntu", env={}), root)

        self.assertEqual(command[:4], ["wsl", "-d", "Ubuntu", "--"])
        self.assertIn("cd '/mnt/c/Tuba Work'", command[-1])
        self.assertIn(".tuba-preflight-probe", command[-1])
        self.assertNotIn("|| true", command[-1])
        self.assertIsNone(cwd)

    def test_docker_preflight_uses_real_mount_contract_and_probe_file(self):
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            config = CodeAsterRuntimeConfig(exec_method="docker", docker_image="local/code-aster:dev", env={})
            candidate = select_code_aster_runtime(config)

            command, cwd = build_code_aster_preflight_command(candidate, config, root)

        self.assertEqual(command[:3], ["docker", "run", "--rm"])
        self.assertIn("-v", command)
        self.assertIn(f"{root.resolve()}:/work", command)
        self.assertIn("-w", command)
        self.assertIn("/work", command)
        self.assertIn(".tuba-preflight-probe", command[-1])
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
                with self.assertRaisesRegex(RuntimeError, "fatal solver error") as raised:
                    run_code_aster_export(
                        export_file,
                        root,
                        CodeAsterRuntimeConfig(exec_method="command", runner_command="run_aster"),
                    )

            message = str(raised.exception)
            self.assertIn("command: run_aster study.export", message)
            self.assertIn(str(root / "stdout.command.log"), message)
            self.assertIn(str(root / "stderr.command.log"), message)
            self.assertIn("solver stdout", message)
            self.assertIn("solver stderr", message)
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
        self.assertEqual(len(calls), 3)

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
        self.assertEqual(len(calls), 3)
        self.assertIn("wsl executable not found", missing_wsl_log)

    def test_preflight_reports_ok_runtime(self):
        from tuba.solver.code_aster_runtime import preflight_code_aster_runtimes

        calls = []

        def fake_run(cmd, **kwargs):
            calls.append((cmd, kwargs))
            return subprocess.CompletedProcess(cmd, 0, stdout="run_aster ok", stderr="")

        with patch("tuba.solver.code_aster_runtime.subprocess.run", fake_run):
            checks = preflight_code_aster_runtimes(
                CodeAsterRuntimeConfig(
                    exec_method="command",
                    runner_command="run_aster",
                    env={},
                    preflight_timeout_seconds=3,
                )
            )

        self.assertEqual(len(checks), 1)
        self.assertTrue(checks[0].ok)
        self.assertEqual(checks[0].runtime.kind, "command")
        self.assertEqual(checks[0].stdout, "run_aster ok")
        self.assertEqual(calls[0][1]["timeout"], 3)

    def test_preflight_reports_missing_wsl_runner(self):
        from tuba.solver.code_aster_runtime import preflight_code_aster_runtimes

        def fake_run(cmd, **_kwargs):
            return subprocess.CompletedProcess(cmd, 127, stdout="", stderr="Code_Aster runner not found")

        with patch("tuba.solver.code_aster_runtime.subprocess.run", fake_run):
            checks = preflight_code_aster_runtimes(
                CodeAsterRuntimeConfig(exec_method="wsl", wsl_distro="Ubuntu", env={})
            )

        self.assertEqual(len(checks), 1)
        self.assertFalse(checks[0].ok)
        self.assertEqual(checks[0].returncode, 127)
        self.assertIn("Code_Aster runner not found", checks[0].reason)

    def test_preflight_timeout_is_reported_without_hanging(self):
        from tuba.solver.code_aster_runtime import preflight_code_aster_runtimes

        def fake_run(cmd, **kwargs):
            raise subprocess.TimeoutExpired(cmd, kwargs["timeout"], output="pulling", stderr="still pulling")

        with patch("tuba.solver.code_aster_runtime.subprocess.run", fake_run):
            checks = preflight_code_aster_runtimes(
                CodeAsterRuntimeConfig(
                    exec_method="docker",
                    docker_image="simvia/code_aster:stable",
                    env={},
                    preflight_timeout_seconds=1,
                )
            )

        self.assertEqual(len(checks), 1)
        self.assertFalse(checks[0].ok)
        self.assertIsNone(checks[0].returncode)
        self.assertIn("timed out after 1 seconds", checks[0].reason)


if __name__ == "__main__":
    unittest.main()
