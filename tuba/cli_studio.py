"""CLI entrypoint for Tuba Studio: a project folder's model.py live in the 3D viewer."""

from __future__ import annotations

import argparse
import sys
import webbrowser
from pathlib import Path

from tuba.visualization.preview.server import ProjectStudioServer


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Launch Tuba Studio on a project folder.")
    parser.add_argument(
        "project",
        help="A project folder holding model.py (and optionally study.py), e.g. examples/code-aster-review",
    )
    parser.add_argument(
        "--out",
        dest="out_dir",
        default=None,
        help="Directory to write scene bundles to (default: .build/studio/<project>)",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host address to bind HTTP and WebSocket server (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="Port number to bind (default: 8765, 0 for random)",
    )
    parser.add_argument(
        "--no-open",
        action="store_true",
        help="Do not open default web browser on launch",
    )
    args = parser.parse_args(argv)

    project = Path(args.project).resolve()
    if not (project / "model.py").is_file():
        parser.error(f"{project} is not a project folder: pass the folder that holds model.py.")
    out_dir = Path(args.out_dir or Path(".build") / "studio" / project.name).resolve()
    server = ProjectStudioServer(project, out_dir, host=args.host, port=args.port)
    server.start()

    # The viewer opens on the live model; Review switches to the review bundle.
    viewer_url = f"{server.base_url}?bundle=build&preview_ws={server.ws_url}"
    print("=" * 60)
    print("  TUBA PIPING STUDIO")
    print("=" * 60)
    print(f"  Project     : {project}")
    print(f"  3D Viewer   : {viewer_url}")
    print(f"  MCP Server  : python -m tuba.mcp.server")
    print("=" * 60)
    print("Studio running. Press Ctrl+C to stop.\n", flush=True)

    if not args.no_open:
        webbrowser.open(viewer_url)

    try:
        while not server._stop.wait(1.0):
            pass
    except KeyboardInterrupt:
        print("\nStopping Tuba Studio...")
    finally:
        server.stop()

    return 0


if __name__ == "__main__":
    sys.exit(main())
