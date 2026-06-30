import os
import shutil
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from tests.test_mixed_code_aster_export import build_mixed_fixture
from tuba.solver.aster import CodeAsterSolver
from tuba.solver.code_aster_runtime import CodeAsterRuntimeConfig, discover_code_aster_runtimes


class TestMixedCodeAsterRuntime(unittest.TestCase):
    def test_mixed_export_runtime_gate_is_explicit(self):
        model = build_mixed_fixture()
        with TemporaryDirectory() as tmpdir:
            study = CodeAsterSolver(work_dir=tmpdir).export_mixed_analysis_study(model, "Hot", tmpdir)
            self.assertTrue(Path(study.input_files["comm"]).exists())
            self.assertTrue(Path(study.input_files["med"]).exists())

    def test_mixed_study_runs_when_code_aster_is_configured(self):
        if not os.environ.get("TUBA_RUN_CODE_ASTER_INTEGRATION"):
            self.skipTest("Set TUBA_RUN_CODE_ASTER_INTEGRATION=1 to run real Code_Aster mixed studies.")
        skip_reason = _configured_runtime_skip_reason()
        if skip_reason:
            self.skipTest(skip_reason)

        model = build_mixed_fixture()
        with TemporaryDirectory() as tmpdir:
            solver = CodeAsterSolver(work_dir=tmpdir)
            study = solver.export_mixed_analysis_study(model, "Hot", tmpdir)
            results = solver.solve_exported_study(model, study)

        self.assertEqual(results.solver_name, "Code_Aster")
        self.assertTrue(results.node_results or results.element_results or results.analysis_node_results)


def _configured_runtime_skip_reason() -> str | None:
    configured = any(
        os.environ.get(name)
        for name in (
            "TUBA_CODE_ASTER_PYTHON",
            "TUBA_CODE_ASTER_RUNNER_COMMAND",
            "TUBA_CODE_ASTER_RUNNER",
            "TUBA_CODE_ASTER_EXEC_METHOD",
        )
    )
    if not configured:
        return (
            "No Code_Aster runtime configured. Set TUBA_CODE_ASTER_PYTHON, "
            "TUBA_CODE_ASTER_RUNNER_COMMAND, TUBA_CODE_ASTER_RUNNER, or "
            "TUBA_CODE_ASTER_EXEC_METHOD."
        )

    config = CodeAsterRuntimeConfig(
        exec_method=os.environ.get("TUBA_CODE_ASTER_EXEC_METHOD", "auto"),
        docker_image=os.environ.get("TUBA_CODE_ASTER_DOCKER_IMAGE", "simvia/code_aster:stable"),
        wsl_distro=os.environ.get("TUBA_CODE_ASTER_WSL_DISTRO"),
        runner_command=os.environ.get("TUBA_CODE_ASTER_RUNNER_COMMAND") or os.environ.get("TUBA_CODE_ASTER_RUNNER"),
        bridge_python=os.environ.get("TUBA_CODE_ASTER_PYTHON"),
    )
    for candidate in discover_code_aster_runtimes(config):
        if not candidate.available:
            continue
        reason = _candidate_skip_reason(candidate.kind, candidate.command)
        if reason is None:
            return None
        last_reason = reason
    return locals().get("last_reason", "No Code_Aster runtime candidate was available.")


def _candidate_skip_reason(kind: str, command: tuple[str, ...]) -> str | None:
    if not command:
        return "Code_Aster runtime candidate has no command."
    executable = command[0]
    if kind == "python_bridge":
        if Path(executable).exists() or shutil.which(executable):
            return None
        return f"Configured Code_Aster python bridge not found: {executable}"
    if kind == "command":
        if shutil.which(executable) or Path(executable).exists():
            return None
        return f"Configured Code_Aster command not found: {executable}"
    if kind == "wsl":
        if shutil.which("wsl"):
            return None
        return "WSL executable not found for Code_Aster runtime."
    if kind == "docker":
        if shutil.which("docker"):
            return None
        return "Docker executable not found for Code_Aster runtime."
    return f"Unsupported Code_Aster runtime kind: {kind}"


if __name__ == "__main__":
    unittest.main()
