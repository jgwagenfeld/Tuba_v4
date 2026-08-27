"""Command-line benchmark entrypoints for visualization workflows."""

from __future__ import annotations

import argparse
import json
from typing import Sequence

from tuba.visualization.performance import benchmark_viewer_smoke


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m tuba.visualization.benchmarks")
    subparsers = parser.add_subparsers(dest="command", required=True)

    viewer_smoke = subparsers.add_parser("viewer-smoke", help="Run the local viewer-contract smoke benchmark.")
    viewer_smoke.add_argument("--output-dir", default=".build/benchmarks")

    args = parser.parse_args(argv)
    if args.command == "viewer-smoke":
        report = benchmark_viewer_smoke(output_dir=args.output_dir)
        if argv is None:
            print(json.dumps(report, indent=2, sort_keys=True))
        return 0

    parser.error(f"Unknown benchmark command {args.command!r}.")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
