#!/usr/bin/env python3
"""Serve docs/ locally for previewing the profile monitor."""

from __future__ import annotations

import argparse
import functools
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class Handler(SimpleHTTPRequestHandler):
    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    docs = Path(__file__).resolve().parents[1] / "docs"
    handler = functools.partial(Handler, directory=str(docs))
    server = ThreadingHTTPServer(("127.0.0.1", args.port), handler)
    print(f"Profile monitor: http://127.0.0.1:{args.port}/")
    print(f"Evidence Lab:    http://127.0.0.1:{args.port}/lab/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
