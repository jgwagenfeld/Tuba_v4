"""python -m tuba.search: run, inspect, export and review retained trials."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sqlite3
import sys

from .checks import render_reason
from .contracts import CheckResult
from .export import export_history, inspect_history, write_candidate_review
from .run import SearchBlocked, run_search
from .replay import write_search_replay
from .film import write_search_film, FilmCaptureError


def main(argv=None, *, solver=None) -> int:
    parser = argparse.ArgumentParser(description="Retained Code_Aster piping search with explicit constraints and evidence.")
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="Evaluate a bounded authored parameter grid")
    run.add_argument("project", type=Path)
    run.add_argument("--run-dir", required=True, type=Path)
    run.add_argument("--resume", action="store_true")
    run.add_argument("--parent-run", type=Path, help="Link a new run to an earlier run and reuse only its qualified evidence")
    inspect = commands.add_parser("inspect", help="Read recorded outcomes without a solver")
    inspect.add_argument("--run-dir", required=True, type=Path)
    inspect.add_argument("--candidate")
    inspect.add_argument("--json", action="store_true")
    for name in ("export", "review", "replay"):
        command = commands.add_parser(name)
        command.add_argument("--run-dir", required=True, type=Path)
        command.add_argument("--output", required=True, type=Path, help="New output directory; existing output is refused")
        if name == "review":
            command.add_argument("--candidate", required=True)
            command.add_argument("--attempt", help="Review an earlier retained attempt")
    film = commands.add_parser('film', help='Capture recorded replay events through the existing viewer (no new solve)')
    film.add_argument('--replay-dir', required=True, type=Path)
    film.add_argument('--output', required=True, type=Path, help='New film output directory; existing output is refused')
    film.add_argument('--ffmpeg', help='Existing FFmpeg executable with VP8 support; alternatively TUBA_FFMPEG/PATH')
    film.add_argument('--node', help='Existing Node executable; alternatively TUBA_NODE/PATH')
    film.add_argument('--start', type=int, default=1, help='First search event sequence (inclusive)')
    film.add_argument('--end', type=int, help='Last search event sequence (inclusive)')
    film.add_argument('--events', choices=['milestones', 'all', 'review', 'iterations'], default='iterations')
    film.add_argument('--fps', type=int, default=25)
    film.add_argument('--hold-seconds', type=float, default=8.0, help='Presentation hold per recorded keyframe')
    film.add_argument('--width', type=int, default=1600)
    film.add_argument('--height', type=int, default=900)
    args = parser.parse_args(argv)
    try:
        if args.command == 'film':
            path = write_search_film(args.replay_dir, args.output, ffmpeg=args.ffmpeg, node=args.node,
                                     start=args.start, end=args.end, events=args.events, fps=args.fps,
                                     hold_seconds=args.hold_seconds, width=args.width, height=args.height)
            print(path)
            print('movie: ' + str(path.parent / 'film.webm'))
            return 0
        if args.command == "run":
            summary = run_search(args.project, args.run_dir, resume=args.resume, parent_run_dir=args.parent_run, solver=solver)
            print(json.dumps(summary, indent=2, allow_nan=False))
            return 4 if summary["blocked"] else 0 if summary["selected_candidate_id"] else 3
        if args.command == "inspect":
            snapshot = inspect_history(args.run_dir, args.candidate)
            if args.json:
                print(json.dumps(snapshot, indent=2, allow_nan=False))
            else:
                print(snapshot["run"]["scope"])
                for row in snapshot["candidates"]:
                    print(f"{row['id']}  {row['outcome']}  {', '.join(row['reason_codes'])}")
                    if args.candidate:
                        print("parameters: " + json.dumps(row["parameters"], allow_nan=False))
                        print("unevaluated operations: " + ", ".join(row["unevaluated_operations"]))
                        for decision in row["decisions"]:
                            if decision["details"].get("message"):
                                print(decision["details"]["message"])
                        for record in row["evaluations"]:
                            print(f"attempt {record['attempt_id']}  {record['status']}  {record['error_kind'] or ''}")
                            for event in snapshot["events"]:
                                if event["kind"] == "evaluation.diagnostic" and event["payload"]["attempt_id"] == record["attempt_id"]:
                                    print(event["payload"]["message"])
                            for check in record["checks"]:
                                print(render_reason(CheckResult.from_dict(check)))
            return 0
        path = (write_search_replay(args.run_dir, args.output) if args.command == "replay" else
                export_history(args.run_dir, args.output) if args.command == "export" else
                write_candidate_review(args.run_dir, args.candidate, args.output, attempt_id=args.attempt))
        print(path)
        print(f"output bytes: {sum(p.stat().st_size for p in path.parent.rglob('*') if p.is_file())}")
        return 0
    except (FileNotFoundError, FileExistsError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 4 if any(word in str(exc).lower() for word in ("integrity", "history schema")) else 2
    except (SearchBlocked, FilmCaptureError, OSError, sqlite3.Error) as exc:
        print(f"blocked: {exc}", file=sys.stderr)
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
