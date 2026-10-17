# App launcher and updates

Plumbing for a sciwidgets app that is installed from PyPI: a launcher so it starts
with a double-click, and an update check with "Update Now". Import it from
`sciwidgets.app`. Maxwell Bloch Studio and linecat (Line Catalog Explorer) use it.

## Describe the app once

```python
from pathlib import Path
from sciwidgets.app import AppInfo

APP = AppInfo(
    name="Line Catalog Explorer",          # shown to the user
    version=__version__,                   # of your package
    dist_name="linecat",                   # name on PyPI
    module="linecat",                      # python -m linecat starts the app
    command="linecat",                     # the terminal command, for messages
    github_repo="vahid-anari/linecat",     # its Releases hold the release notes
    icon=Path(__file__).parent / "data" / "icons" / "app_icon.png",
    bundle_id="io.github.vahid-anari.linecat",
    linux_id="linecat",
    marker="Linecat",                      # keys recorded in the launcher; never change once released
    comment="Filter spectral line catalogs and draw energy-level diagrams",
    categories="Science;Astronomy;Physics;",
)
```

The app needs a `__main__.py`, so that `python -m <module>` starts it.

## Launcher (`sciwidgets.app.launcher`, no Qt)

```python
from sciwidgets.app.launcher import install_app_command, refresh_if_outdated

install_app_command(APP)                 # body of "<app> install-app"; prints what it did
install_app_command(APP, remove=True)    # "<app> install-app --remove"
refresh_if_outdated(APP)                 # a few seconds after start-up
```

- macOS: `~/Applications/<name>.app` (Launchpad, Spotlight, Dock). It keeps the PATH of the
  installing terminal, so LaTeX is found as from the terminal.
- Windows: a Start-menu shortcut (`pythonw.exe`, no console window).
- Linux: a menu entry with the icon.

The launcher starts this installation's Python with `-m <module>` and records the version
that made it; `refresh_if_outdated` rebuilds it after an update (only a launcher of this
installation). `install_app`, `remove_app` and `launcher_info` are the lower-level calls.

## Updates without Qt (`sciwidgets.app.update`)

```python
from sciwidgets.app.update import run_update

run_update(APP, args)                    # body of "<app> update [--check] [--yes]"
```

It reads the latest version from PyPI and the notes of the newer versions from the GitHub
Releases, shows them, and runs `pipx upgrade` or `pip install -U` (whichever matches the
installation) after asking. A copy installed with `pip install -e` is told to `git pull`.
Also: `parse_version`, `newer_release_notes`, `install_kind`, `update_command`.

## Updates in the window (`sciwidgets.app.update_ui`)

```python
from PySide6.QtCore import QTimer
from sciwidgets.app.update_ui import AppUpdates

updates = AppUpdates(window, APP)
QTimer.singleShot(2000, updates.check)                   # quiet: only a newer version is shown
check_action.triggered.connect(lambda: updates.check(manual=True))   # Help > Check for Updates…
```

A newer version opens the update notice with the release notes; **Update Now** runs the update
in a progress window and then offers a restart (`python -m <module>` in the same Python). A
manual check also reports "up to date" and failures. `success_note` adds a sentence after the
restart question, e.g. about unsaved work. The pieces — `UpdateChecker`, `UpdateDialog`,
`UpdateProgressDialog`, `restart_app` — can be used on their own.
