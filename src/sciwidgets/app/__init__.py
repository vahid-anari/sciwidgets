"""App plumbing shared by sciwidgets apps: double-click launcher and updates from PyPI or GitHub.

Describe the app once in an :class:`AppInfo` and pass it to

* :mod:`sciwidgets.app.launcher` — ``install_app`` / ``remove_app`` / ``refresh_if_outdated``
  (macOS app in ~/Applications, Windows Start-menu shortcut, Linux menu entry);
* :mod:`sciwidgets.app.update` — the Qt-free part: latest version and release notes, how the app
  was installed, the update command, ``run_update`` for an ``<app> update`` terminal command,
  and the access token of an app updated from a private GitHub repository;
* :mod:`sciwidgets.app.github_install` — installs the newest release wheel of a (private) GitHub
  repository; run as ``python -m sciwidgets.app.github_install`` by "Update Now" and install scripts;
* :mod:`sciwidgets.app.update_ui` — the background check, update notice, "Update Now" with
  progress and restart, and :class:`~sciwidgets.app.update_ui.AppUpdates` for the menu flow;
* :mod:`sciwidgets.app.help` — the Help menu every app shares (User Guide, documents, Check
  for Updates…, About) with :class:`~sciwidgets.app.help.AppHelp`;
* :mod:`sciwidgets.app.about` — the About text with the libraries the app is built on.

Only ``update_ui`` and ``help`` import Qt.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

UPDATE_SOURCES = ("pypi", "github")


@dataclass(frozen=True)
class AppInfo:
    """What the launcher and the update check need to know about an app.

    Args:
        name: Name shown to the user (launcher, dialogs), e.g. "Maxwell Bloch Studio".
        version: Running version (``__version__`` of the package).
        dist_name: Package name on PyPI, e.g. "maxwell-bloch-studio".
        module: Module started by ``python -m`` (the launcher and the restart run it).
        command: The app's terminal command, used in messages ("run ``linecat update``").
        github_repo: ``owner/name``; its GitHub Releases hold the release notes.
        icon: The app icon (a large PNG); copied to icns/ico/png for the launchers.
        bundle_id: macOS bundle identifier, e.g. "io.github.vahid-anari.mbstudio".
        linux_id: Name of the Linux .desktop file and icon, e.g. "maxwell-bloch-studio".
        marker: Prefix of the keys a launcher records (``<marker>Python`` in Info.plist,
            ``X-<marker>-Version``/``X-<marker>-Python`` in the .desktop file). Keep it once
            released, or existing launchers are no longer recognised.
        comment: One-line description for the Linux menu entry.
        categories: Linux menu categories, e.g. "Science;Physics;".
        update_source: Where new versions come from. ``"pypi"`` (default): the version from
            PyPI, the notes from the public GitHub Releases. ``"github"``: everything from the
            GitHub Releases of ``github_repo``, which may be private; each release carries the
            built wheel as an asset, and an access token (see
            :func:`sciwidgets.app.update.token_path`) is sent with every request.
    """

    name: str
    version: str
    dist_name: str
    module: str
    command: str
    github_repo: str
    icon: Path
    bundle_id: str
    linux_id: str
    marker: str
    comment: str = ""
    categories: str = "Science;"
    update_source: str = "pypi"

    def __post_init__(self) -> None:
        if self.update_source not in UPDATE_SOURCES:
            raise ValueError(f"update_source must be one of {UPDATE_SOURCES}, not {self.update_source!r}")

    @property
    def from_github(self) -> bool:
        """Whether new versions come from the GitHub Releases (``update_source="github"``)."""
        return self.update_source == "github"

    @property
    def pypi_url(self) -> str:
        """The app's page on PyPI."""
        return f"https://pypi.org/project/{self.dist_name}/"

    @property
    def pypi_json_url(self) -> str:
        """PyPI's JSON API for the package; ``info.version`` is the latest release."""
        return f"https://pypi.org/pypi/{self.dist_name}/json"

    @property
    def releases_url(self) -> str:
        """GitHub page with all release notes."""
        return f"https://github.com/{self.github_repo}/releases"

    @property
    def releases_api_url(self) -> str:
        """GitHub API listing the releases (newest first) with their notes."""
        return f"https://api.github.com/repos/{self.github_repo}/releases?per_page=30"


__all__ = ["AppInfo", "UPDATE_SOURCES"]
