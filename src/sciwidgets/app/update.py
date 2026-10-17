"""Updating an app from PyPI, without Qt: versions, release notes, ``<app> update``.

The latest version comes from PyPI; the notes of the newer versions come from the app's
GitHub Releases and are optional. :mod:`sciwidgets.app.update_ui` uses the same pieces.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import urllib.request
from collections.abc import Callable
from importlib import metadata
from pathlib import Path

from sciwidgets.app import AppInfo

TIMEOUT_S = 10
MAX_NOTES = 10
"""At most this many versions' notes are shown."""


def parse_version(text: str) -> tuple[int, ...]:
    """``"0.9.1"`` or ``"v0.9.1"`` -> ``(0, 9, 1)``; parsing stops at the first non-numeric part."""
    parts: list[int] = []
    for p in text.strip().lstrip("vV").split("."):
        digits = "".join(ch for ch in p if ch.isdigit())
        if not digits:
            break
        parts.append(int(digits))
    return tuple(parts)


def version_known(version: str) -> bool:
    """False for an app not installed as a package (``0.0.0``, ``0+unknown``, ``""``)."""
    return any(parse_version(version)) and not version.startswith("0+")


def newer_release_notes(releases: list, current: str, latest: str, limit: int = MAX_NOTES) -> list[tuple[str, str]]:
    """``(version, notes)`` of the GitHub releases after ``current`` up to ``latest``, newest first.

    Drafts, pre-releases and releases without notes are left out.
    """
    cur, top = parse_version(current), parse_version(latest)
    picked: list[tuple[tuple[int, ...], str, str]] = []
    for rel in releases:
        if not isinstance(rel, dict) or rel.get("draft") or rel.get("prerelease"):
            continue
        tag = str(rel.get("tag_name") or "")
        ver = parse_version(tag)
        body = str(rel.get("body") or "").strip()
        if ver and cur < ver <= top and body:
            picked.append((ver, tag.lstrip("vV"), body))
    picked.sort(reverse=True)
    return [(v, b) for _, v, b in picked[:limit]]


def _get_json(info: AppInfo, url: str):
    request = urllib.request.Request(url, headers={"User-Agent": f"{info.name}/{info.version}"})
    with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_latest_version(info: AppInfo) -> str:
    """Latest version on PyPI. Raises ``OSError``/``ValueError``/``KeyError`` when it cannot be read."""
    return str(_get_json(info, info.pypi_json_url)["info"]["version"])


def fetch_release_notes(info: AppInfo, current: str, latest: str) -> list[tuple[str, str]]:
    """Notes of the versions after ``current`` up to ``latest``; empty if GitHub can't be read."""
    try:
        data = _get_json(info, info.releases_api_url)
    except (OSError, ValueError):
        return []
    return newer_release_notes(data, current, latest) if isinstance(data, list) else []


def install_kind(info: AppInfo) -> str:
    """How this copy was installed: ``"editable"``, ``"pipx"``, ``"pip"`` or ``"unknown"``."""
    try:
        dist = metadata.distribution(info.dist_name)
    except metadata.PackageNotFoundError:
        return "unknown"
    direct = dist.read_text("direct_url.json")
    if direct:
        try:
            if json.loads(direct).get("dir_info", {}).get("editable"):
                return "editable"
        except ValueError:
            pass
    parts = Path(sys.prefix).parts
    if "pipx" in parts and "venvs" in parts:
        return "pipx"
    return "pip"


def update_command(info: AppInfo, kind: str) -> list[str] | None:
    """The command that updates an installation of the given kind, or ``None``."""
    if kind == "pipx":
        return [shutil.which("pipx") or "pipx", "upgrade", info.dist_name]
    if kind == "pip":
        return [sys.executable, "-m", "pip", "install", "--upgrade", info.dist_name]
    return None


EDITABLE_HINT = "This copy runs from a source folder (pip install -e); update it there with git pull."


def run_update(
    info: AppInfo,
    args: argparse.Namespace,
    *,
    latest_version: Callable[[], str] | None = None,
    release_notes: Callable[[str, str], list[tuple[str, str]]] | None = None,
    kind: Callable[[], str] | None = None,
    ask: Callable[[str], str] = input,
    run: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> int:
    """The body of an ``<app> update [--check] [--yes]`` command; returns the exit code.

    ``args`` needs ``check`` and ``yes``; the other arguments replace the network and pip in tests.
    """
    latest_version = latest_version or (lambda: fetch_latest_version(info))
    release_notes = release_notes or (lambda current, latest: fetch_release_notes(info, current, latest))
    kind = kind or (lambda: install_kind(info))
    try:
        latest = latest_version()
    except (OSError, ValueError, KeyError) as exc:
        print(f"Could not check for updates: {exc}", file=sys.stderr)
        return 1

    if parse_version(latest) <= parse_version(info.version):
        print(f"{info.name} {info.version} is the latest version.")
        return 0

    print(f"{info.name} {latest} is available. You have version {info.version}.")
    notes = release_notes(info.version, latest)
    if notes:
        print("\nWhat's new:")
        for version, body in notes:
            print(f"\n{version}")
            print("\n".join(f"  {line}" for line in body.splitlines()))
        print()
    if args.check:
        return 0

    how = kind()
    if how == "editable":
        print(EDITABLE_HINT, file=sys.stderr)
        return 1
    command = update_command(info, how)
    if command is None:
        print(f"Cannot tell how {info.dist_name} was installed; update it with "
              f"pipx upgrade {info.dist_name} or pip install -U {info.dist_name}.", file=sys.stderr)
        return 1

    shown = " ".join(command)
    if not args.yes:
        answer = ask(f"Run: {shown}  [y/N] ").strip().lower()
        if answer not in ("y", "yes"):
            print("Nothing changed.")
            return 0
    print(f"Running: {shown}")
    return run(command).returncode
