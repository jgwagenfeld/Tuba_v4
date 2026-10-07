"""CLI entrypoint for Tuba Studio: a project folder's model.py live in the 3D viewer."""

from __future__ import annotations

import argparse
import errno
import sys
import webbrowser
from pathlib import Path

from tuba.project import load_project
from tuba.project.package import package_suffix, unpack_project_package
from tuba.project.session import project_bundle_dir, studio_session
from tuba.studio_launcher import StudioLauncher, viewer_url
from tuba.visualization.preview.server import ProjectStudioServer


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Open a Tuba project, or launch the local project chooser.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Opening a received project:\n"
            "  Pass a .tubaproject, .zip, .tgz or .tar.gz to extract and open it,\n"
            "  or pass the local\n"
            "  folder containing model.py. Omit it to choose a folder or package.\n"
            "  Include study.py and all referenced Python helpers, CAD and data.\n\n"
            "Mesh and results:\n"
            "  Generate mesh creates diagnostic cells; Solve generates the required\n"
            "  mesh and runs Code_Aster. Complete evidence/<operation>/ folders let\n"
            "  Studio import saved results without a new solver run.\n"
            "  Share completed review bundles with python -m tuba.visualization.viewer.\n\n"
            "Guide: docs/content/project-sharing.md (Share and open a project)."
        ),
    )
    parser.add_argument(
        "project",
        nargs="?",
        help="Project folder or ZIP/TGZ package; omit for the project chooser",
    )
    parser.add_argument(
        "--out",
        dest="out_dir",
        default=None,
        help="Scene bundle directory (default: .build/studio/<full-project-id>; launcher uses its state directory)",
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
    parser.add_argument("--state-dir", type=Path, default=Path(".tuba") / "studio",
                        help="Launcher recent folders and bundles (default: .tuba/studio in the current folder)")
    parser.add_argument("--extract-to", type=Path, help="New working folder for a ZIP/TGZ package (default: beside the package, without its extension)")
    parser.add_argument("--dev-origin", help="Explicit exact HTTP loopback development origin permitted to access this Studio")
    args = parser.parse_args(argv)

    if args.host not in {"127.0.0.1", "localhost"}:
        parser.error("Studio local interaction binds to localhost or 127.0.0.1 only.")
    if not 0 <= args.port <= 65535:
        parser.error("Port must be between 0 and 65535.")
    project = Path(args.project).resolve() if args.project else None
    suffix = package_suffix(project) if project is not None else None
    if args.extract_to is not None and (suffix is None or not project.is_file()):
        parser.error("--extract-to requires a .tubaproject/.zip/.tgz/.tar.gz package.")
    if suffix is not None and project.is_file():
        try:
            project = unpack_project_package(project, args.extract_to or project.with_name(project.name[:-len(suffix)]))
        except (OSError, ValueError) as exc:
            parser.error(str(exc))
        print(f"Extracted project: {project}", flush=True)
    launcher = None
    if project is not None:
        try:
            load_project(project)
        except FileNotFoundError:
            parser.error(f"{project} is not a project folder: pass the folder that holds model.py.")
        existing = studio_session(project)
        if existing is not None:
            print(f"Project: {project}\nStudio already running: {existing['viewer_url']}", flush=True)
            if not args.no_open:
                webbrowser.open(existing["viewer_url"])
            return 0
        out_dir = Path(args.out_dir).resolve() if args.out_dir else project_bundle_dir(Path(".build") / "studio", project)
        launcher = StudioLauncher(args.state_dir, host=args.host, port=0)
        server = ProjectStudioServer(project, out_dir, host=args.host, port=args.port, allowed_dev_origin=args.dev_origin)
    else:
        server = StudioLauncher(args.state_dir, host=args.host, port=args.port,
                                out_dir=Path(args.out_dir) if args.out_dir else None)
    try:
        if launcher is not None:
            launcher.start()
            server.launcher_url = launcher.launch_url
        try:
            server.start()
        except OSError as exc:
            if exc.errno != errno.EADDRINUSE and getattr(exc, "winerror", None) != 10048:
                raise
            # A second project gets its own port, never the first project's session.
            server.port = 0
            server.start()
        if launcher is not None:
            launcher.open_project(str(project))  # Reuse the registered Studio; record Recent.
    except BaseException:
        server.stop()
        if launcher is not None:
            launcher.stop()
        raise

    try:
        # The viewer opens on the live model; Review switches to the review bundle.
        url = viewer_url(server) if project is not None else server.launch_url
        print("=" * 60)
        print("  TUBA PIPING STUDIO")
        print("=" * 60)
        print(f"  Project     : {project or 'Choose a project folder'}")
        print(f"  Studio      : {url}")
        print("=" * 60)
        print("Studio running. Press Ctrl+C to stop.\n", flush=True)
        if not args.no_open:
            webbrowser.open(url)
        while not server._stop.wait(1.0):
            pass
    except KeyboardInterrupt:
        print("\nStopping Tuba Studio...")
    finally:
        server.stop()
        if launcher is not None:
            launcher.stop()

    return 0


if __name__ == "__main__":
    sys.exit(main())
