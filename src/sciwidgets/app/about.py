"""About text for a sciwidgets app: name, version, links, and the libraries it is built on.

The library list is read from the installed package metadata, so it never needs updating by
hand: the app's own requirements, plus those of sciwidgets (Qt, Matplotlib, NumPy, …), each
with its installed version and its license, and the version of Qt itself. Qt-free except
:func:`qt_version` (imported lazily).
"""

from __future__ import annotations

import html
import importlib.metadata as metadata
import platform
import re
from dataclasses import dataclass
from typing import Iterable, Sequence

from . import AppInfo

__all__ = ["Library", "app_libraries", "about_html", "short_license"]

_NAME = re.compile(r"\s*([A-Za-z0-9][A-Za-z0-9._-]*)\s*(?:\[([^\]]*)\])?")
_EXTRA = re.compile(r"""extra\s*==\s*["']([^"']+)["']""")
_CLASSIFIER_NAMES = {
    "BSD License": "BSD",
    "MIT License": "MIT",
    "Apache Software License": "Apache-2.0",
    "Python Software Foundation License": "PSF",
    "GNU Lesser General Public License v3 (LGPLv3)": "LGPL-3.0",
}
_LINKS = {
    "pyside6": "https://doc.qt.io/qtforpython-6/",
    "qt": "https://www.qt.io/licensing/open-source-lgpl-obligations",
}


@dataclass(frozen=True)
class Library:
    """One library an app uses: display name, installed version, short license, home page."""

    name: str
    version: str
    license: str
    url: str = ""


def short_license(meta) -> str:
    """A short license name from a package's metadata, e.g. "BSD-3-Clause" or "LGPL-3.0".

    Uses ``License-Expression`` (or a one-line ``License``), keeping only its first term, so
    "LGPL-3.0-only OR GPL-3.0-only" becomes "LGPL-3.0"; otherwise the license classifier.
    """
    text = meta.get("License-Expression") or ""
    if not text:
        lic = (meta.get("License") or "").strip()
        text = lic if lic and "\n" not in lic and len(lic) <= 80 else ""
    if text:
        first = re.split(r"\s+(?:OR|AND|or|and)\s+|[()]", text)
        first = next((t.strip() for t in first if t.strip()), text)
        return first.removesuffix("-only").removesuffix("-or-later")
    for classifier in meta.get_all("Classifier") or []:
        if classifier.startswith("License :: "):
            name = classifier.split(" :: ")[-1]
            return _CLASSIFIER_NAMES.get(name, name)
    return "see its project page"


def _requirements(dist: str, extras: Iterable[str] = ()) -> list[tuple[str, set[str]]]:
    """Direct requirements of ``dist`` (with the given extras) as ``(name, extras)``."""
    try:
        reqs = metadata.requires(dist) or []
    except metadata.PackageNotFoundError:
        return []
    wanted, out = set(extras), []
    for req in reqs:
        spec, _, marker = req.partition(";")
        needed = _EXTRA.search(marker)
        if needed and needed.group(1) not in wanted:
            continue
        match = _NAME.match(spec)
        if match:
            out.append((match.group(1), {e.strip() for e in (match.group(2) or "").split(",") if e.strip()}))
    return out


def _home_page(meta) -> str:
    for entry in meta.get_all("Project-URL") or []:
        label, _, url = entry.partition(",")
        if label.strip().lower() in ("homepage", "home", "source", "repository", "documentation"):
            return url.strip()
    return (meta.get("Home-page") or "").strip()


def qt_version() -> str:
    """Version of the Qt libraries PySide6 runs on (may differ from PySide6's own version)."""
    try:
        from PySide6.QtCore import qVersion
    except ImportError:
        return ""
    return qVersion()


EXPAND = ("sciwidgets", "mbsolver")
"""Packages whose own requirements are listed too (they bring Qt, Matplotlib, NumPy, numba)."""


def app_libraries(info: AppInfo, *, also: Sequence[str] = (), expand: Sequence[str] = EXPAND) -> list[Library]:
    """The libraries ``info``'s app is built on, from the installed metadata.

    The app's direct requirements, plus the requirements of those named in ``expand``
    (sciwidgets brings PySide6, Matplotlib and NumPy; mbsolver brings numba), plus ``also``;
    then Qt itself after PySide6. Packages that are not installed are left out. Sorted by
    name, case-insensitive.
    """
    seen: dict[str, Library] = {}
    queue = _requirements(info.dist_name) + [(name, set()) for name in also]
    wanted = {name.lower() for name in expand}
    for name, extras in list(queue):
        if name.lower() in wanted:
            queue += _requirements(name, extras)
    for name, _ in queue:
        key = name.lower().replace("_", "-")
        if key in seen:
            continue
        try:
            meta = metadata.metadata(name)
        except metadata.PackageNotFoundError:
            continue
        seen[key] = Library(meta.get("Name") or name, meta.get("Version") or "?", short_license(meta),
                            _LINKS.get(key) or _home_page(meta))
    libs = sorted(seen.values(), key=lambda lib: lib.name.lower())
    if "pyside6" in seen and qt_version():
        index = next(i for i, lib in enumerate(libs) if lib.name.lower() == "pyside6") + 1
        libs.insert(index, Library("Qt", qt_version(), "LGPL-3.0", _LINKS["qt"]))
    return libs


def about_html(info: AppInfo, *, author: str = "", license: str = "MIT", extra_html: str = "",
               libraries: Sequence[Library] | None = None) -> str:
    """HTML for the About dialog.

    Version and ``info.comment`` (the one-line description), the repository link,
    ``license`` and ``author``, ``extra_html`` (credits for data, citations …) and a table of
    ``libraries`` (default :func:`app_libraries`) with the Python version.
    """
    libs = app_libraries(info) if libraries is None else libraries
    repo = f"https://github.com/{info.github_repo}"
    parts = [f"<p><b>Version {html.escape(info.version)}</b>"]
    if info.comment:
        parts.append(f"<br>{html.escape(info.comment)}")
    parts.append(f'</p><p><a href="{repo}">{html.escape(repo.removeprefix("https://"))}</a><br>')
    parts.append(" · ".join(html.escape(p) for p in (f"{license} License" if license else "", author) if p))
    parts.append("</p>")
    if extra_html:
        parts.append(f"<p>{extra_html}</p>")
    if libs:
        rows = "".join(
            "<tr><td>{name}</td><td>&nbsp;&nbsp;{version}</td><td>&nbsp;&nbsp;{license}</td></tr>".format(
                name=f'<a href="{lib.url}">{html.escape(lib.name)}</a>' if lib.url else html.escape(lib.name),
                version=html.escape(lib.version), license=html.escape(lib.license))
            for lib in libs)
        parts.append(f"<p><b>Built with</b> Python {platform.python_version()} and:</p>"
                     f'<table cellspacing="0" cellpadding="1">{rows}</table>')
    return "".join(parts)
