"""Install the newest release wheel of a GitHub repository into this Python (no Qt).

Used by apps with ``AppInfo(update_source="github")``, whose releases each carry the built
wheel as an asset, possibly in a private repository::

    python -m sciwidgets.app.github_install --repo owner/name --token-file PATH

"Update Now" and ``<app> update`` run it in the app's own Python; an install script runs it
once in a new environment (after ``pip install sciwidgets``). The wheel is downloaded with the
token into a temporary folder and installed with ``pip install --upgrade``; its dependencies
come from PyPI. The token never appears in a URL or in pip's records.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from collections.abc import Callable, Sequence
from pathlib import Path

from sciwidgets.app.update import (
    AccessDenied,
    download_wheel,
    github_releases,
    latest_release,
    read_token,
)


def install_latest(
    repo: str,
    token: str,
    *,
    python: str = sys.executable,
    run: Callable[..., subprocess.CompletedProcess] = subprocess.run,
    releases: Callable[[str, str], list] | None = None,
    download: Callable[[str, dict, str, Path], Path] | None = None,
) -> int:
    """Download the newest release wheel of ``repo`` and ``pip install --upgrade`` it; returns the exit code.

    ``releases``, ``download`` and ``run`` replace GitHub and pip in tests.
    """
    releases = releases or github_releases
    download = download or download_wheel
    try:
        found = latest_release(releases(repo, token))
    except AccessDenied as exc:
        print(f"{exc} It may have expired; ask for a new one.", file=sys.stderr, flush=True)
        return 3
    except (OSError, ValueError) as exc:
        print(f"Could not read the releases of {repo}: {exc}", file=sys.stderr, flush=True)
        return 1
    if found is None:
        print(f"{repo} has no release with a wheel.", file=sys.stderr, flush=True)
        return 1
    version, release = found
    with tempfile.TemporaryDirectory(prefix="sciwidgets-update-") as tmp:
        print(f"Downloading version {version}…", flush=True)
        try:
            wheel = download(repo, release, token, Path(tmp))
        except (OSError, ValueError) as exc:
            print(f"Could not download the wheel: {exc}", file=sys.stderr, flush=True)
            return 1
        print(f"Installing {wheel.name}…", flush=True)
        return run([python, "-m", "pip", "install", "--upgrade", str(wheel)]).returncode


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m sciwidgets.app.github_install",
                                     description="Install the newest release wheel of a GitHub repository.")
    parser.add_argument("--repo", required=True, help="owner/name")
    parser.add_argument("--token-file", required=True, type=Path, help="file holding the access token")
    args = parser.parse_args(argv)
    token = read_token(args.token_file)
    if not token:
        print(f"No access token in {args.token_file}.", file=sys.stderr)
        return 2
    return install_latest(args.repo, token)


if __name__ == "__main__":
    sys.exit(main())
