"""CLI entrypoint for ``python -m tuba.visualization.preview``."""

from __future__ import annotations

import argparse
import json
import time

from tuba.visualization.preview.server import PatchPreviewServer, PreviewServer


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m tuba.visualization.preview")
    subparsers = parser.add_subparsers(dest="command", required=True)
    watch = subparsers.add_parser("watch", help="watch a trusted local Python script")
    watch.add_argument("script")
    watch.add_argument("--out", required=True)
    watch.add_argument("--port", type=int, default=8765)
    watch.add_argument("--host", default="127.0.0.1")
    watch.add_argument("--timeout", type=float, default=10.0)
    watch.add_argument("--poll-interval", type=float, default=0.25)
    watch.add_argument("--debounce", type=float, default=0.2)
    watch_patch = subparsers.add_parser("watch-patch", help="watch a JSON ModelPatch against a committed model snapshot")
    watch_patch.add_argument("model")
    watch_patch.add_argument("patch")
    watch_patch.add_argument("--out", required=True)
    watch_patch.add_argument("--port", type=int, default=8765)
    watch_patch.add_argument("--host", default="127.0.0.1")
    watch_patch.add_argument("--timeout", type=float, default=10.0)
    watch_patch.add_argument("--poll-interval", type=float, default=0.25)
    watch_patch.add_argument("--debounce", type=float, default=0.2)

    args = parser.parse_args(argv)
    if args.command == "watch-patch":
        server = PatchPreviewServer(
            args.model,
            args.patch,
            args.out,
            host=args.host,
            port=args.port,
            timeout_s=args.timeout,
            poll_interval_s=args.poll_interval,
            debounce_s=args.debounce,
        ).start(run_initial=True)
    else:
        server = PreviewServer(
            args.script,
            args.out,
            host=args.host,
            port=args.port,
            timeout_s=args.timeout,
            poll_interval_s=args.poll_interval,
            debounce_s=args.debounce,
        ).start(run_initial=True)
    print(json.dumps({"type": "preview_server_ready", "base_url": server.base_url, "ws_url": server.ws_url}), flush=True)
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        server.stop()
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
