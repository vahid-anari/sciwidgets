"""Updating an app, without Qt: versions, release notes, ``<app> update``.

By default the latest version comes from PyPI and the notes of the newer versions from the
app's GitHub Releases (optional). An app with ``AppInfo(update_source="github")`` is updated
from the GitHub Releases alone, which may belong to a private repository: each release carries
the built wheel as an asset, every request sends the access token kept in :func:`token_path`,
and the update runs :mod:`sciwidgets.app.github_install`. :mod:`sciwidgets.app.update_ui` uses
the same pieces.
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import shutil
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from importlib import metadata
from pathlib import Path

from sciwidgets.app import AppInfo
from sciwidgets.app.launcher import current_system

TIMEOUT_S = 10
RETRY_TRIES = 5
RETRY_WAIT_S = 30
"""Right after a release PyPI's download index (behind a CDN) can lag the version shown on
its JSON page for a few minutes: pip then finds nothing new. An update that left the old
version is run again after RETRY_WAIT_S seconds, RETRY_TRIES times in all."""
MAX_NOTES = 10
"""At most this many versions' notes are shown."""
GITHUB_API = "https://api.github.com"
INSTALL_MODULE = "sciwidgets.app.github_install"
"""Run as ``python -m`` to install the newest release wheel of a GitHub repository."""


def ssl_context() -> ssl.SSLContext:
    """Certificates for HTTPS: certifi's list (the one pip uses), else the system default.

    Python from python.org on macOS has no certificates of its own until its "Install
    Certificates" step has run, so without certifi every HTTPS request from the standard library
    fails there with CERTIFICATE_VERIFY_FAILED (while pip, which carries certifi, works).
    """
    try:
        import certifi
    except ImportError:
        return ssl.create_default_context()
    return ssl.create_default_context(cafile=certifi.where())


class AccessDenied(OSError):
    """GitHub refused the access token, or there is none (private repository)."""


# ----- access token (update_source="github") -----

def token_path(info: AppInfo, *, system: str | None = None, home: Path | None = None) -> Path:
    """Where the app's GitHub access token is kept.

    macOS ``~/Library/Application Support/<name>/token``, Windows ``%APPDATA%\\<name>\\token``,
    Linux ``$XDG_CONFIG_HOME/<linux_id>/token`` (default ``~/.config``).
    """
    system = system or current_system()
    home = Path(home) if home is not None else Path.home()
    if system == "mac":
        return home / "Library" / "Application Support" / info.name / "token"
    if system == "windows":
        base = os.environ.get("APPDATA")
        return (Path(base) if base else home / "AppData" / "Roaming") / info.name / "token"
    base = os.environ.get("XDG_CONFIG_HOME")
    return (Path(base) if base else home / ".config") / info.linux_id / "token"


def read_token(path: Path) -> str:
    """The token stored in ``path``, or ``""`` when there is none."""
    try:
        return Path(path).read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def save_token(path: Path, token: str) -> Path:
    """Store ``token`` in ``path`` (readable by the user only); returns the path."""
    token = token.strip()
    if not token:
        raise ValueError("The access token is empty.")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(token + "\n")
    os.chmod(path, 0o600)
    return path


def missing_token_message(info: AppInfo) -> str:
    """Said when the app has no access token."""
    return (f"{info.name} has no access token for its updates. Ask for one and enter it with "
            f"Check for Updates… or `{info.command} update --token`.")


def refused_token_message(info: AppInfo) -> str:
    """Said when GitHub refuses the token (expired, revoked, or without access to the repository)."""
    return (f"The access token for {info.name}'s updates was refused; it may have expired. Ask for a new "
            f"one and enter it with Check for Updates… or `{info.command} update --token`.")


# ----- GitHub Releases with a token (update_source="github") -----

def _github_request(url: str, token: str, accept: str, user_agent: str) -> urllib.request.Request:
    request = urllib.request.Request(url, headers={"User-Agent": user_agent, "Accept": accept,
                                                    "X-GitHub-Api-Version": "2022-11-28"})
    # Not sent on: an asset download is redirected to a signed storage URL that rejects a second credential.
    request.add_unredirected_header("Authorization", f"Bearer {token}")
    return request


def _open_github(request: urllib.request.Request):
    try:
        return urllib.request.urlopen(request, timeout=TIMEOUT_S, context=ssl_context())
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403, 404):  # a private repository answers 404 to a token without access
            raise AccessDenied(f"GitHub refused the access token (HTTP {exc.code}).") from exc
        raise


def github_releases(repo: str, token: str, *, user_agent: str = "sciwidgets") -> list:
    """The releases of ``repo`` (newest first) as GitHub's API lists them.

    Raises :class:`AccessDenied` without a token or when GitHub refuses it, ``OSError`` /
    ``ValueError`` when the list cannot be read.
    """
    if not token:
        raise AccessDenied("No access token.")
    request = _github_request(f"{GITHUB_API}/repos/{repo}/releases?per_page=30", token,
                              "application/vnd.github+json", user_agent)
    with _open_github(request) as response:
        data = json.loads(response.read().decode("utf-8"))
    if not isinstance(data, list):
        raise ValueError("GitHub's answer is not a list of releases.")
    return data


def wheel_asset(release: dict) -> dict | None:
    """The release's ``.whl`` asset, or ``None``."""
    for asset in release.get("assets") or []:
        if isinstance(asset, dict) and str(asset.get("name", "")).endswith(".whl"):
            return asset
    return None


def latest_release(releases: list) -> tuple[str, dict] | None:
    """``(version, release)`` of the newest published release with a wheel, or ``None``.

    Drafts, pre-releases, tags of another kind and releases without a ``.whl`` are skipped.
    """
    best: tuple[tuple[int, ...], str, dict] | None = None
    for rel in releases:
        if not isinstance(rel, dict) or rel.get("draft") or rel.get("prerelease"):
            continue
        tag = str(rel.get("tag_name") or "")
        if not is_version_tag(tag) or wheel_asset(rel) is None:
            continue
        ver = parse_version(tag)
        if ver and (best is None or ver > best[0]):
            best = (ver, tag.lstrip("vV"), rel)
    return None if best is None else (best[1], best[2])


def download_wheel(repo: str, release: dict, token: str, dest_dir: Path, *,
                   user_agent: str = "sciwidgets") -> Path:
    """Download the release's wheel into ``dest_dir``; returns its path."""
    asset = wheel_asset(release)
    if asset is None:
        raise ValueError(f"Release {release.get('tag_name')} has no wheel.")
    name = Path(str(asset["name"])).name
    request = _github_request(f"{GITHUB_API}/repos/{repo}/releases/assets/{asset['id']}", token,
                              "application/octet-stream", user_agent)
    target = Path(dest_dir) / name
    with _open_github(request) as response, open(target, "wb") as handle:
        shutil.copyfileobj(response, handle)
    return target


def _app_releases(info: AppInfo) -> list:
    path = token_path(info)
    token = read_token(path)
    if not token:
        raise AccessDenied(missing_token_message(info))
    try:
        return github_releases(info.github_repo, token, user_agent=f"{info.name}/{info.version}")
    except AccessDenied as exc:
        raise AccessDenied(refused_token_message(info)) from exc


def parse_version(text: str) -> tuple[int, ...]:
    """``"0.9.1"`` or ``"v0.9.1"`` -> ``(0, 9, 1)``; parsing stops at the first non-numeric part."""
    parts: list[int] = []
    for p in text.strip().lstrip("vV").split("."):
        digits = "".join(ch for ch in p if ch.isdigit())
        if not digits:
            break
        parts.append(int(digits))
    return tuple(parts)


def is_version_tag(tag: str) -> bool:
    """``"v1.2.0"`` or ``"1.2.0"``: a release of the app itself (not ``"phone-v0.3.0"``)."""
    tag = tag.strip()
    if tag[:1] in ("v", "V"):
        tag = tag[1:]
    return tag[:1].isdigit()


def version_known(version: str) -> bool:
    """False for an app not installed as a package (``0.0.0``, ``0+unknown``, ``""``)."""
    return any(parse_version(version)) and not version.startswith("0+")


def newer_release_notes(releases: list, current: str, latest: str, limit: int = MAX_NOTES) -> list[tuple[str, str]]:
    """``(version, notes)`` of the GitHub releases after ``current`` up to ``latest``, newest first.

    Drafts, pre-releases and releases without notes are left out, and so are tags of another
    kind in the same repository (``phone-v0.3.0``: only ``v1.2.0`` or ``1.2.0`` are the app's).
    """
    cur, top = parse_version(current), parse_version(latest)
    picked: list[tuple[tuple[int, ...], str, str]] = []
    for rel in releases:
        if not isinstance(rel, dict) or rel.get("draft") or rel.get("prerelease"):
            continue
        tag = str(rel.get("tag_name") or "")
        if not is_version_tag(tag):
            continue
        ver = parse_version(tag)
        body = str(rel.get("body") or "").strip()
        if ver and cur < ver <= top and body:
            picked.append((ver, tag.lstrip("vV"), body))
    picked.sort(reverse=True)
    return [(v, b) for _, v, b in picked[:limit]]


def _get_json(info: AppInfo, url: str):
    request = urllib.request.Request(url, headers={"User-Agent": f"{info.name}/{info.version}"})
    with urllib.request.urlopen(request, timeout=TIMEOUT_S, context=ssl_context()) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_latest_version(info: AppInfo) -> str:
    """Latest version (PyPI, or the GitHub Releases for ``update_source="github"``).

    Raises ``OSError`` (:class:`AccessDenied` for a missing or refused token), ``ValueError`` or
    ``KeyError`` when it cannot be read.
    """
    if info.from_github:
        found = latest_release(_app_releases(info))
        if found is None:
            raise ValueError(f"{info.github_repo} has no release with a wheel yet.")
        return found[0]
    return str(_get_json(info, info.pypi_json_url)["info"]["version"])


def fetch_release_notes(info: AppInfo, current: str, latest: str) -> list[tuple[str, str]]:
    """Notes of the versions after ``current`` up to ``latest``; empty if GitHub can't be read."""
    try:
        data = _app_releases(info) if info.from_github else _get_json(info, info.releases_api_url)
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
    """The command that updates an installation of the given kind, or ``None``.

    ``--no-cache-dir``: pip keeps PyPI's list of versions for a few minutes, so right after a
    release it would otherwise not see the new version, and finish without changing anything.
    For ``update_source="github"`` it is :mod:`sciwidgets.app.github_install` in this Python.
    """
    if info.from_github:
        if kind not in ("pip", "pipx"):
            return None
        return [sys.executable, "-m", INSTALL_MODULE, "--repo", info.github_repo,
                "--token-file", str(token_path(info))]
    if kind == "pipx":
        return [shutil.which("pipx") or "pipx", "upgrade", info.dist_name, "--pip-args=--no-cache-dir"]
    if kind == "pip":
        return [sys.executable, "-m", "pip", "install", "--upgrade", "--no-cache-dir", info.dist_name]
    return None


def installed_version(info: AppInfo) -> str:
    """The version now installed for this Python (asked in a fresh process), or ``""``."""
    code = "import importlib.metadata as m, sys; print(m.version(sys.argv[1]))"
    try:
        done = subprocess.run([sys.executable, "-c", code, info.dist_name],
                              capture_output=True, text=True, timeout=TIMEOUT_S)
    except (OSError, subprocess.SubprocessError):
        return ""
    return done.stdout.strip() if done.returncode == 0 else ""


def retry_message(latest: str, attempt: int, tries: int, wait_s: int) -> str:
    """Said before running the update again (``attempt`` is the next one)."""
    return (f"PyPI is still publishing {latest}: trying again in {wait_s} s "
            f"(attempt {attempt} of {tries}).")


def not_updated_message(info: AppInfo, installed: str, latest: str) -> str:
    """Why an update that ran without errors still left the old version."""
    still = f"The update ran, but {info.name} {installed or '(unknown version)'} is still installed"
    if info.from_github:
        return f"{still}: the newest release on GitHub did not install {latest}."
    return f"{still}: PyPI may not offer {latest} yet. Try again in a few minutes."


def update_tries(info: AppInfo, tries: int = RETRY_TRIES) -> int:
    """How often an update that left the old version is run: only PyPI lags behind a release."""
    return 1 if info.from_github else tries


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
    installed: Callable[[], str] | None = None,
    sleep: Callable[[float], None] = time.sleep,
    tries: int = RETRY_TRIES,
    wait_s: int = RETRY_WAIT_S,
    get_token: Callable[[str], str] = getpass.getpass,
) -> int:
    """The body of an ``<app> update [--check] [--yes] [--token]`` command; returns the exit code.

    ``args`` needs ``check`` and ``yes``; with ``token`` true (an app updated from GitHub) it
    first asks for a new access token (hidden input) and stores it. The other arguments
    replace the network and pip in tests. An update counts as done only when the new version is
    really installed afterwards; one that left the old version is tried again (``tries``
    times, ``wait_s`` apart; once for an app updated from GitHub).
    """
    if getattr(args, "token", False):
        if not info.from_github:
            print(f"{info.name} is updated from PyPI and needs no access token.", file=sys.stderr)
            return 1
        try:
            path = save_token(token_path(info), get_token("Access token: "))
        except (ValueError, OSError, EOFError, KeyboardInterrupt) as exc:
            print(f"No token saved: {exc or 'cancelled'}", file=sys.stderr)
            return 1
        print(f"Access token saved in {path}.")
    tries = update_tries(info, tries)
    installed = installed or (lambda: installed_version(info))
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
        if info.from_github:
            print(f"Cannot tell how {info.dist_name} was installed; install it again with its install script.",
                  file=sys.stderr)
        else:
            print(f"Cannot tell how {info.dist_name} was installed; update it with "
                  f"pipx upgrade {info.dist_name} or pip install -U {info.dist_name}.", file=sys.stderr)
        return 1

    shown = " ".join(command)
    if not args.yes:
        answer = ask(f"Run: {shown}  [y/N] ").strip().lower()
        if answer not in ("y", "yes"):
            print("Nothing changed.")
            return 0
    for attempt in range(1, tries + 1):
        if attempt > 1:
            print(retry_message(latest, attempt, tries, wait_s))
            sleep(wait_s)
        print(f"Running: {shown}")
        code = run(command).returncode
        if code != 0:
            return code
        now = installed()
        if version_known(now) and parse_version(now) >= parse_version(latest):
            print(f"{info.name} is now at {now}.")
            return 0
    print(not_updated_message(info, now, latest), file=sys.stderr)
    return 1
