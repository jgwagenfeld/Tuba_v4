"""Diagnose Code_Aster runtime configuration."""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict
from typing import Any

from tuba.solver.code_aster_runtime import (
    CodeAsterRuntimeConfig,
    discover_code_aster_runtimes,
    preflight_code_aster_runtimes,
)


def main(argv: list[str] | None = None, *, return_output: bool = False) -> str | int:
    parser = argparse.ArgumentParser(prog="python -m tuba.solver.code_aster_doctor")
    parser.add_argument(
        "--exec-method",
        default=os.environ.get("TUBA_CODE_ASTER_EXEC_METHOD", "auto"),
        choices=["auto", "python_bridge", "command", "wsl", "docker"],
    )
    parser.add_argument("--wsl-distro", default=os.environ.get("TUBA_CODE_ASTER_WSL_DISTRO"))
    parser.add_argument("--check", action="store_true", help="Run bounded readiness probes for discovered runtimes.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    config = CodeAsterRuntimeConfig(
        exec_method=args.exec_method,
        wsl_distro=args.wsl_distro,
        docker_image=_resolve_docker_image(),
    )
    candidates = discover_code_aster_runtimes(config)
    checks = preflight_code_aster_runtimes(config) if args.check else []
    if args.json:
        output = json.dumps(
            {
                "candidates": [_candidate_payload(item) for item in candidates],
                "checks": [_check_payload(item) for item in checks],
            },
            indent=2,
            sort_keys=True,
        )
    else:
        output = _text_report(candidates, checks=checks, include_checks=args.check)

    if return_output:
        return output
    print(output)
    return 0


def _resolve_docker_image() -> str:
    return os.environ.get("TUBA_CODE_ASTER_DOCKER_IMAGE") or CodeAsterRuntimeConfig().docker_image


def _candidate_payload(candidate: Any) -> dict[str, Any]:
    payload = asdict(candidate)
    payload["command"] = list(candidate.command)
    return payload


def _check_payload(check: Any) -> dict[str, Any]:
    return {
        "kind": check.runtime.kind,
        "command": list(check.command),
        "returncode": check.returncode,
        "stdout": check.stdout,
        "stderr": check.stderr,
        "ok": check.ok,
        "reason": check.reason,
    }


def _text_report(candidates: list[Any], *, checks: list[Any], include_checks: bool) -> str:
    lines = ["Code_Aster runtime candidates:"]
    for candidate in candidates:
        status = "available" if candidate.available else "unavailable"
        command = " ".join(candidate.command) if candidate.command else "<not configured>"
        lines.append(f"- {candidate.kind}: {status}; command={command}")
        if candidate.reason:
            lines.append(f"  reason: {candidate.reason}")
    if include_checks:
        lines.append("")
        lines.append("Code_Aster runtime readiness:")
        for item in checks:
            status = "ready" if item.ok else "blocked"
            command = " ".join(item.command) if item.command else "<not configured>"
            lines.append(f"- {item.runtime.kind}: {status}; command={command}")
            if item.reason:
                lines.append(f"  reason: {item.reason}")
    lines.append("")
    lines.append(
        "Primary setup path: set TUBA_CODE_ASTER_PYTHON to the Python executable "
        "inside a Code_Aster environment that can import run_aster."
    )
    lines.append(
        "Fallback setup path: set TUBA_CODE_ASTER_RUNNER to a command such as "
        "'run_aster' or 'conda run -n aster run_aster'."
    )
    lines.append(
        "Windows/WSL setup path: set TUBA_CODE_ASTER_EXEC_METHOD=wsl and "
        "TUBA_CODE_ASTER_WSL_DISTRO=Ubuntu when Code_Aster is installed in a "
        "specific WSL distro."
    )
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
