import json
import os
import unittest
from unittest.mock import patch

from tuba.solver.code_aster_doctor import main
from tuba.solver.code_aster_runtime import CodeAsterRuntimeCandidate


class TestCodeAsterDoctor(unittest.TestCase):
    def test_json_output_lists_candidates(self):
        candidates = [CodeAsterRuntimeCandidate("python_bridge", ("/opt/aster/bin/python",), True)]

        with patch("tuba.solver.code_aster_doctor.discover_code_aster_runtimes", return_value=candidates):
            payload = main(["--json"], return_output=True)

        data = json.loads(payload)
        self.assertEqual(data["candidates"][0]["kind"], "python_bridge")
        self.assertEqual(data["candidates"][0]["command"], ["/opt/aster/bin/python"])
        self.assertTrue(data["candidates"][0]["available"])

    def test_text_output_includes_setup_guidance_when_empty(self):
        candidates = [CodeAsterRuntimeCandidate("auto", (), False, "No runtime")]

        with patch("tuba.solver.code_aster_doctor.discover_code_aster_runtimes", return_value=candidates):
            output = main([], return_output=True)

        self.assertIn("No runtime", output)
        self.assertIn("TUBA_CODE_ASTER_PYTHON", output)

    def test_environment_defaults_are_passed_to_runtime_discovery(self):
        captured = {}

        def fake_discover(config):
            captured["config"] = config
            return [CodeAsterRuntimeCandidate("wsl", ("wsl", "-d", "Ubuntu", "--"), True)]

        env = {
            "TUBA_CODE_ASTER_EXEC_METHOD": "wsl",
            "TUBA_CODE_ASTER_WSL_DISTRO": "Ubuntu",
        }
        with patch.dict(os.environ, env, clear=False):
            with patch("tuba.solver.code_aster_doctor.discover_code_aster_runtimes", fake_discover):
                output = main([], return_output=True)

        self.assertEqual(captured["config"].exec_method, "wsl")
        self.assertEqual(captured["config"].wsl_distro, "Ubuntu")
        self.assertIn("wsl -d Ubuntu --", output)

    def test_check_json_output_lists_runtime_readiness(self):
        from tuba.solver.code_aster_runtime import CodeAsterRuntimeCheck

        checks = [
            CodeAsterRuntimeCheck(
                runtime=CodeAsterRuntimeCandidate("wsl", ("wsl", "-d", "Ubuntu", "--"), True),
                command=("wsl", "-d", "Ubuntu", "--", "bash", "-lc", "probe"),
                returncode=127,
                stdout="",
                stderr="Code_Aster runner not found",
                ok=False,
                reason="Code_Aster runner not found",
            )
        ]

        with patch("tuba.solver.code_aster_doctor.preflight_code_aster_runtimes", return_value=checks):
            payload = main(["--json", "--check"], return_output=True)

        data = json.loads(payload)
        self.assertFalse(data["checks"][0]["ok"])
        self.assertEqual(data["checks"][0]["kind"], "wsl")
        self.assertIn("Code_Aster runner not found", data["checks"][0]["reason"])


if __name__ == "__main__":
    unittest.main()
