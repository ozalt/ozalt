#!/usr/bin/env python3
"""Vendor the Evidence Lab explorer into docs/lab/.

The explorer is self-contained (data.js carries the experiment results). This
script keeps the copy minted from ozalt/evidence-lab, rewrites repository-
relative links, and adds a "back to monitor" affordance.

Run manually when the benchmark or its explorer changes. The daily workflow
also runs it before rebuilding the profile.
"""

from __future__ import annotations

import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "lab"
BASE = "https://raw.githubusercontent.com/ozalt/evidence-lab/main/web"
FILES = ("index.html", "style.css", "app.js", "data.js")
ICON = (
    '<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns=\'http://www.w3.org/2000/svg\' '
    "viewBox='0 0 64 64'%3E%3Crect width='64' height='64' fill='%2307110d'/%3E"
    "%3Cpath d='M14 20l10 12-10 12' stroke='%237bf1a8' stroke-width='5' fill='none'/%3E"
    "%3Cpath d='M32 46h18' stroke='%23ffb454' stroke-width='5'/%3E%3C/svg%3E\">"
)
BACK = """<a href="../" class="back-monitor">← BACK TO MONITOR</a>
<style>.back-monitor{position:fixed;right:18px;bottom:18px;z-index:9999;font:600 11px/1 ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.6px;text-decoration:none;color:#a4ffaf;background:#0b1f15;border:1px solid #2a5a3a;padding:12px 15px;box-shadow:0 10px 30px #0007}.back-monitor:hover{background:#123322;color:#d7ffe3}</style>
"""


def fetch(name: str) -> str:
    request = Request(f"{BASE}/{name}", headers={"User-Agent": "ozalt-profile-monitor"})
    with urlopen(request, timeout=45) as response:
        return response.read().decode("utf-8")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    try:
        files = {name: fetch(name) for name in FILES}
    except (HTTPError, URLError, TimeoutError) as error:
        print(f"Could not refresh Evidence Lab explorer ({error}); keeping the existing copy.", file=sys.stderr)
        return 0

    page = files["index.html"]
    page = page.replace(
        "../results/summary.json",
        "https://raw.githubusercontent.com/ozalt/evidence-lab/main/results/summary.json",
    )
    page = page.replace(
        "../notebooks/evidence_lab.ipynb",
        "https://github.com/ozalt/evidence-lab/blob/main/notebooks/evidence_lab.ipynb",
    )
    page = page.replace("../README.md", "https://github.com/ozalt/evidence-lab#readme")
    if 'rel="icon"' not in page:
        page = page.replace(
            '<meta name="viewport" content="width=device-width,initial-scale=1" />',
            '<meta name="viewport" content="width=device-width,initial-scale=1" />\n    ' + ICON,
            1,
        )
    if "back-monitor" not in page:
        page = page.replace("</body>", BACK + "</body>")
    files["index.html"] = page

    for name, content in files.items():
        (OUT / name).write_text(content, encoding="utf-8")
    print(f"Vendored {len(files)} files into {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
