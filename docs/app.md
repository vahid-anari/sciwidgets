# App launcher, updates, Help menu and About

Plumbing for a sciwidgets app that is installed from PyPI (or from the releases of a private
GitHub repository): a launcher so it starts with a double-click, and an update check with
"Update Now". Import it from
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

## Updates from a private GitHub repository

An app that is not on PyPI, e.g. one shared with a few colleagues before its paper is out, can
be updated from the GitHub Releases of its (private) repository instead:

```python
APP = AppInfo(..., github_repo="owner/name", update_source="github")
```

- **Each release carries the built wheel** as an asset (`python -m build`, then attach
  `dist/*.whl` to the GitHub Release, e.g. in the release workflow). The newest published
  release with a wheel is the latest version; its notes are the "What's new".
- **Access token**: every request sends a GitHub token kept in `token_path(APP)` —
  `~/Library/Application Support/<name>/token` on macOS, `%APPDATA%\<name>\token` on
  Windows, `~/.config/<linux_id>/token` on Linux (readable by the user only). Use a
  fine-grained token limited to that one repository with *Contents: read*, and give it an
  expiry date. The users need no GitHub account.
- **Update Now** and `<app> update` run `python -m sciwidgets.app.github_install --repo owner/name
  --token-file PATH` in the app's own Python: it downloads the newest wheel with the token into
  a temporary folder and runs `pip install --upgrade` on it (dependencies from PyPI). No git is
  needed, and the token never appears in a URL or in pip's records.
- **A missing or refused token**: Check for Updates… asks for a new one (hidden input) and
  checks again; the quiet start-up check asks only when a stored token was refused (expired or
  revoked). On the command line: `<app> update --token` (give the app's `update` command a
  `--token` flag; `run_update` reads `args.token`).
- **First installation** (an install script, so users need no pipx): create a venv, `pip install
  sciwidgets`, save the token with `save_token(token_path(APP), token)` or by writing the file,
  run `python -m sciwidgets.app.github_install --repo owner/name --token-file PATH`, then
  `<app> install-app`.
- The update notice has no "Open Release Notes" / "Open PyPI Page" buttons (a private
  repository's pages need a GitHub sign-in), and an update is run once (PyPI's index lag, which
  the retries are for, does not apply).

Also in `sciwidgets.app.update`: `read_token`, `save_token`, `github_releases`,
`latest_release`, `wheel_asset`, `download_wheel`, `AccessDenied`.

## Help menu and About (`sciwidgets.app.help`, `sciwidgets.app.about`)

`AppHelp` gives every app the same Help menu, in the same order and with the same shortcuts:

```
User Guide                 ⌘?
<the app's own documents>
───────────
Check for Updates…         ⌘U
───────────
About <app name>
```

```python
from sciwidgets.app.help import AppHelp, Document, DocumentMenu

help_ = AppHelp(window, APP, user_guide=GUIDE_PDF, author="Vahid Anari",
                documents=[Document("Equations Reference", EQS_PDF, "Ctrl+Alt+E")],
                about_extra="Catalog data: CDMS …",           # optional credits
                citation='Anari, V. … <a href="https://doi.org/…">doi:…</a>')
QTimer.singleShot(2000, help_.updates.check)             # the quiet check at start-up

# with a MenuBarController:
spec["Help"] = help_.menu_items()                        # ids start with "help_"
controller.actionTriggered.connect(lambda _menu, action_id, _checked: help_.handle(action_id))
# with a plain QMenu:
help_.add_to(menu_bar.addMenu("Help"))
```

Documents are opened in the system viewer; a missing one gives a message (`missing_hint` adds
e.g. how to build it). `DocumentMenu(title, [Document, …])` makes a submenu.

**About** shows the version, `APP.comment`, the repository, license and author, the optional
credits, a **Citing** request with `citation` ("If you use <app> in published work, please cite:
…"), and **Built with**: the Python version and the libraries the app is built on, read from
the installed package metadata (`about.app_libraries`): the app's own requirements and those of
sciwidgets and mbsolver, each with its version and license, plus the version of Qt itself
(LGPL-3.0). Nothing to update by hand when a dependency changes.

### Shortcuts shared by the apps

Ctrl is ⌘ on macOS. ⌘O opens (the app's main Open…), ⌘S saves, ⌘E exports, ⌘Q quits, ⌘,
opens settings, ⌘? the User Guide, ⌘U checks for updates, ⌘I shows information about what is
loaded. macOS keeps some keys for itself, so an app never receives them: ⌥⌘D (Dock), ⌘M
(minimise), ⌘H and ⌥⌘H (hide), ⌘Tab, ⌘Space, ⌃⌘F (full screen), ⌃⌘Q (lock screen).
