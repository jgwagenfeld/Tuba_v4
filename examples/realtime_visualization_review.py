"""Realtime visualization review export requiring real Code_Aster artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tuba.solver.aster import CodeAsterSolver

try:
    from examples.operating_state_clash import build_model
except ModuleNotFoundError:  # pragma: no cover - direct script execution from examples/
    from operating_state_clash import build_model


def run_example(output_dir: str | Path = ".benchmarks/realtime_visualization_review") -> dict[str, Any]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    model, _n0, _n1 = build_model()

    study_dir = output_path / "code_aster"
    study = CodeAsterSolver(work_dir=str(study_dir)).export_analysis_study(
        model,
        "Hot",
        output_dir=study_dir,
    )
    raise RuntimeError(
        "Realtime result review requires real Code_Aster result artifacts. "
        f"Exported the study to {study.work_dir}. Execute study.export with Code_Aster, "
        "then use tuba.analysis.code_aster_artifacts.import_code_aster_artifacts before writing a review scene."
    )


def main() -> int:
    run_example()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
