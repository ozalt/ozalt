#!/usr/bin/env python3
"""Build the profile work-log data, page, and animated preview.

The page is intentionally profile-first: current role, focus areas, credentials,
and a curated selected-work list. Repository metadata is used only for project
ordering.

Usage:
    python scripts/build.py --render          # fetch GitHub, build, render GIF
    python scripts/build.py --render --force  # force a fresh GIF
    python scripts/build.py --cached --render # reuse docs/data.json (no API calls)

Set GITHUB_TOKEN to raise the API rate limit. The GitHub Actions workflow does
this automatically.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import time
from datetime import datetime, timezone
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path
from threading import Thread
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
ASSETS = ROOT / "assets"
CONFIG_FILE = ROOT / "scripts" / "profile.json"
TEMPLATE = ROOT / "scripts" / "template.html"
OUT_GIF = ASSETS / "project-monitor.gif"
API = "https://api.github.com"
USER_AGENT = "ozalt-profile-monitor"


def load_config() -> dict:
    return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))


def api(path: str, token: str | None = None, params: dict | None = None):
    url = API + path
    if params:
        url += "?" + urlencode(params)
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": USER_AGENT,
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(url, headers=headers)
    for attempt in range(3):
        try:
            with urlopen(request, timeout=35) as response:
                raw = response.read()
                return (json.loads(raw) if raw else None), response.headers
        except HTTPError as error:
            if error.code in (403, 429) and attempt < 2:
                reset = error.headers.get("X-RateLimit-Reset")
                wait = 8 * (attempt + 1)
                if reset:
                    wait = min(60, max(wait, int(reset) - int(time.time()) + 1))
                print(f"  GitHub API {error.code}; waiting {wait}s", file=sys.stderr)
                time.sleep(wait)
                continue
            body = error.read().decode("utf-8", "replace")[:300]
            raise RuntimeError(f"GitHub API {error.code} for {path}: {body}") from error


def title_from_slug(slug: str) -> str:
    words = re.split(r"[-_]+", slug)
    return " ".join(word.capitalize() for word in words if word)


def iso_timestamp(value: str | None) -> float:
    if not value:
        return 0
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0


def cached_repos() -> list[dict]:
    """Reuse the project rows already in docs/data.json for offline builds."""
    path = DOCS / "data.json"
    if not path.is_file():
        raise RuntimeError("No docs/data.json to reuse; run without --cached first.")
    old = json.loads(path.read_text(encoding="utf-8"))
    repos = []
    for project in old.get("projects", []):
        repo = project.get("repo")
        if not repo:
            continue
        repos.append(
            {
                "full_name": repo,
                "name": repo.split("/", 1)[-1],
                "html_url": project.get("url", f"https://github.com/{repo}"),
                "description": project.get("description", ""),
                "created_at": project.get("created"),
                "pushed_at": project.get("pushed"),
                "fork": False,
                "private": False,
            }
        )
    return repos


def compose_data(config: dict, repos: list[dict]) -> dict:
    username = config["username"]
    excluded = {name.lower() for name in config.get("exclude_repos", [])}
    repos = [
        repo for repo in repos
        if not repo.get("fork")
        and not repo.get("private")
        and repo.get("name", "").lower() not in excluded
    ]

    configured = config.get("projects", {})
    projects = []
    for repo in repos:
        slug = repo["name"]
        meta = configured.get(slug, {})
        projects.append(
            {
                "repo": repo["full_name"],
                "name": meta.get("title") or title_from_slug(slug),
                "description": meta.get("summary") or repo.get("description") or "A public project — open the repository for details.",
                "category": (meta.get("category") or "PROJECT").upper(),
                "url": repo.get("html_url", f"https://github.com/{repo['full_name']}"),
                "demo": meta.get("demo", ""),
                "demo_label": meta.get("demo_label", "Live demo"),
                "order": int(meta.get("order", 999)),
                "created": repo.get("created_at"),
                "pushed": repo.get("pushed_at"),
            }
        )

    projects.sort(key=lambda p: (p["order"], -iso_timestamp(p["pushed"])))
    for index, project in enumerate(projects, start=1):
        project["index"] = index

    years = []
    for project in projects:
        for key in ("created", "pushed"):
            if project.get(key):
                try:
                    years.append(datetime.fromisoformat(project[key].replace("Z", "+00:00")).year)
                except ValueError:
                    pass
    window = config.get("window") or (f"{min(years)}→{str(max(years))[-2:]}" if years else "")
    for project in projects:
        project.pop("created", None)
        project.pop("pushed", None)

    user = config["user"]
    data = {
        "user": {
            "name": user["name"],
            "headline": user["headline"],
            "tagline": user["tagline"],
            "location": user.get("location", ""),
            "current": user.get("current", {}),
            "focus": user.get("focus", []),
            "credentials": user.get("credentials", []),
            "links": user.get("links", {}),
        },
        "metrics": {
            "projects": len(projects),
            "focus": len(user.get("focus", [])),
            "credentials": len(user.get("credentials", [])),
            "window": window,
        },
        "projects": projects,
        "meta": {},
    }
    print(
        f"Built {data['metrics']['projects']} selected projects, "
        f"{data['metrics']['focus']} focus areas, {data['metrics']['credentials']} credentials.",
        flush=True,
    )
    return data


def signature(data: dict) -> str:
    payload = dict(data)
    payload["meta"] = {}
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8"))
    for path in (TEMPLATE, ROOT / "assets/fonts/JetBrainsMono-Regular.ttf", ROOT / "assets/fonts/JetBrainsMono-Bold.ttf"):
        digest.update(path.read_bytes())
    return digest.hexdigest()


def copy_assets() -> None:
    (DOCS / "fonts").mkdir(parents=True, exist_ok=True)
    for name in ("JetBrainsMono-Regular.ttf", "JetBrainsMono-Bold.ttf"):
        shutil.copy2(ASSETS / "fonts" / name, DOCS / "fonts" / name)
    (DOCS / ".nojekyll").touch()


def write_site(data: dict) -> None:
    DOCS.mkdir(exist_ok=True)
    copy_assets()
    (DOCS / "data.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    template = TEMPLATE.read_text(encoding="utf-8")
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    (DOCS / "index.html").write_text(template.replace("__DATA__", payload), encoding="utf-8")


def gif_signature() -> str:
    try:
        from PIL import Image

        with Image.open(OUT_GIF) as image:
            return image.info.get("comment", b"").decode("utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def launch_browser(playwright):
    args = ["--no-sandbox", "--disable-dev-shm-usage"]
    candidates = [
        os.environ.get("CHROME_PATH"),
        shutil.which("google-chrome"),
        shutil.which("chromium"),
        shutil.which("chromium-browser"),
    ]
    last_error = None
    for candidate in [c for c in candidates if c]:
        try:
            return playwright.chromium.launch(headless=True, executable_path=candidate, args=args)
        except Exception as error:  # noqa: BLE001 - fall through to bundled browser
            last_error = error
    try:
        return playwright.chromium.launch(headless=True, args=args)
    except Exception as error:  # noqa: BLE001
        raise RuntimeError(
            "Could not launch Chromium. Install it with `python -m playwright install chromium` "
            "or set CHROME_PATH to a Chrome/Chromium binary."
        ) from (last_error or error)


def render_panel(sig: str, force: bool = False) -> None:
    if not force and OUT_GIF.is_file() and gif_signature() == sig:
        print("Panel unchanged; keeping the existing GIF.", flush=True)
        return
    from PIL import Image
    from playwright.sync_api import TimeoutError as BrowserTimeout
    from playwright.sync_api import sync_playwright

    handler = partial(SimpleHTTPRequestHandler, directory=str(DOCS))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    Thread(target=server.serve_forever, daemon=True).start()
    try:
        with sync_playwright() as playwright:
            browser = launch_browser(playwright)
            page = browser.new_page(viewport={"width": 1280, "height": 1200}, device_scale_factor=1)
            page.goto(f"http://127.0.0.1:{server.server_port}/", wait_until="networkidle")
            page.evaluate("() => document.fonts.ready")
            page.wait_for_function("() => document.querySelectorAll('#projects .project').length > 0", timeout=15000)
            page.wait_for_function("() => document.querySelectorAll('#focus .focus-item').length > 0", timeout=5000)
            page.evaluate("() => document.querySelectorAll('img').forEach((image) => { image.loading = 'eager'; })")
            try:
                page.wait_for_function("() => [...document.images].every((image) => image.complete)", timeout=15000)
            except BrowserTimeout:
                pass
            page.add_style_tag(
                content=".topbar{position:static!important}.cursor{animation:none!important;opacity:1!important}"
                ".dot,.live i{animation:none!important;opacity:1!important}html{scroll-behavior:auto!important}"
            )
            panel = page.locator(".monitor")
            first = panel.screenshot()

            page.add_style_tag(content=".cursor{opacity:0!important}")
            second = panel.screenshot()
            browser.close()
    finally:
        server.shutdown()
        server.server_close()

    frame = Image.open(BytesIO(first)).convert("RGB")
    frame = frame.quantize(colors=128, method=Image.Quantize.MEDIANCUT)
    other = Image.open(BytesIO(second)).convert("RGB").quantize(palette=frame)
    OUT_GIF.parent.mkdir(parents=True, exist_ok=True)
    frame.save(
        OUT_GIF,
        format="GIF",
        save_all=True,
        append_images=[other],
        duration=[2600, 700],
        loop=0,
        optimize=True,
        disposal=1,
        comment=sig.encode("utf-8"),
    )
    print(f"Rendered {frame.width}x{frame.height} panel to {OUT_GIF.relative_to(ROOT)} ({OUT_GIF.stat().st_size // 1024} KB)", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--render", action="store_true", help="render the animated panel after building")
    parser.add_argument("--force", action="store_true", help="force a fresh render")
    parser.add_argument("--cached", action="store_true", help="reuse docs/data.json instead of calling GitHub")
    args = parser.parse_args()

    config = load_config()
    if args.cached:
        repos = cached_repos()
    else:
        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        repos, _ = api(
            f"/users/{config['username']}/repos",
            token,
            {"per_page": 100, "sort": "pushed", "direction": "desc", "type": "owner"},
        )
        if not isinstance(repos, list):
            raise RuntimeError("GitHub returned an unexpected repository response.")
    data = compose_data(config, repos)
    sig = signature(data)
    data["meta"]["generated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    data["meta"]["signature"] = sig
    write_site(data)
    print(f"Wrote {DOCS / 'index.html'} and {DOCS / 'data.json'}", flush=True)
    if args.render:
        render_panel(sig, force=args.force)


if __name__ == "__main__":
    main()
