"""Make (or remove) a launcher so an app starts with a double-click.

* macOS: ``~/Applications/<name>.app`` (Launchpad, Spotlight, Dock).
* Linux: a menu entry, ``~/.local/share/applications/<linux_id>.desktop``.
* Windows: a Start-menu shortcut, ``<name>.lnk``.

The launcher only starts this installation (``<this python> -m <module>``), so it keeps
working after updates. It records the version that made it; ``refresh_if_outdated``
(call it a little after the app has started) rebuilds a launcher of this installation made
by an older version, so its icon and Finder version follow updates. No Qt is imported here.

Every function takes the app's :class:`~sciwidgets.app.AppInfo` first.
"""

from __future__ import annotations

import json
import os
import plistlib
import shlex
import shutil
import subprocess
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

from sciwidgets.app import AppInfo

LSREGISTER = ("/System/Library/Frameworks/CoreServices.framework/Frameworks/"
              "LaunchServices.framework/Support/lsregister")

PLACE = {"mac": "your Applications folder (also in Launchpad and Spotlight)",
         "linux": "the applications menu",
         "windows": "the Start menu"}
"""Where the launcher appears, for messages ("<name> is now in …")."""

Runner = Callable[[Sequence[str]], subprocess.CompletedProcess]


def current_system() -> str:
    """``"mac"``, ``"windows"`` or ``"linux"`` (any other Unix counts as Linux)."""
    if sys.platform == "darwin":
        return "mac"
    if sys.platform.startswith("win"):
        return "windows"
    return "linux"


def python_for_launcher(system: str, python: str | None = None) -> str:
    """The Python the launcher runs: this one; on Windows ``pythonw.exe`` (no console window)."""
    exe = Path(python or sys.executable)
    if system == "windows":
        windowless = exe.with_name("pythonw.exe")
        if windowless.exists():
            return str(windowless)
    return str(exe)


def launcher_path(info: AppInfo, system: str, home: Path) -> Path:
    """Where the launcher goes for ``home`` (the user's home folder)."""
    if system == "mac":
        return home / "Applications" / f"{info.name}.app"
    if system == "windows":
        appdata = Path(os.environ.get("APPDATA", home / "AppData" / "Roaming"))
        return appdata / "Microsoft" / "Windows" / "Start Menu" / "Programs" / f"{info.name}.lnk"
    data = Path(os.environ.get("XDG_DATA_HOME", home / ".local" / "share"))
    return data / "applications" / f"{info.linux_id}.desktop"


def _linux_icon_path(info: AppInfo, home: Path) -> Path:
    data = Path(os.environ.get("XDG_DATA_HOME", home / ".local" / "share"))
    return data / "icons" / "hicolor" / "256x256" / "apps" / f"{info.linux_id}.png"


def _windows_icon_path(info: AppInfo, home: Path) -> Path:
    local = Path(os.environ.get("LOCALAPPDATA", home / "AppData" / "Local"))
    return local / info.name / "app_icon.ico"


def _windows_marker_path(info: AppInfo, home: Path) -> Path:
    return _windows_icon_path(info, home).with_name("launcher.json")


def _save_icon(info: AppInfo, path: Path, fmt: str) -> None:
    """Write the app icon as ``icns``, ``ico`` or a 256 px ``png``."""
    from PIL import Image  # installed with Matplotlib

    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.open(info.icon).convert("RGBA")
    if fmt == "icns":
        image.save(path, format="ICNS")
    elif fmt == "ico":
        image.save(path, format="ICO", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64),
                                              (128, 128), (256, 256)])
    else:
        image.resize((256, 256), Image.LANCZOS).save(path, format="PNG")


# ----- macOS -----------------------------------------------------------------

def _mac_script(info: AppInfo, python: str, path_env: str) -> str:
    # Finder starts apps with a short PATH; keep the one of the installing terminal so that
    # LaTeX (and other tools) are found as when starting from the terminal.
    return (
        "#!/bin/sh\n"
        f"# Starts {info.name}; made by '{info.command} install-app'.\n"
        f"export PATH={shlex.quote(path_env)}\n"
        f"exec {shlex.quote(python)} -m {info.module} \"$@\"\n"
    )


def _install_mac(info: AppInfo, app: Path, python: str, path_env: str, run: Runner) -> list[Path]:
    if app.exists():
        shutil.rmtree(app)
    contents = app / "Contents"
    (contents / "MacOS").mkdir(parents=True)
    (contents / "Resources").mkdir()
    script = contents / "MacOS" / f"{info.command}-launcher"
    script.write_text(_mac_script(info, python, path_env), encoding="utf-8")
    script.chmod(0o755)
    _save_icon(info, contents / "Resources" / "app_icon.icns", "icns")
    plist = {
        "CFBundleName": info.name,
        "CFBundleDisplayName": info.name,
        "CFBundleIdentifier": info.bundle_id,
        "CFBundleExecutable": script.name,
        "CFBundleIconFile": "app_icon",
        "CFBundlePackageType": "APPL",
        "CFBundleShortVersionString": info.version,
        "CFBundleInfoDictionaryVersion": "6.0",
        "LSMinimumSystemVersion": "11.0",
        "NSHighResolutionCapable": True,
        f"{info.marker}Python": python,
    }
    with open(contents / "Info.plist", "wb") as fh:
        plistlib.dump(plist, fh)
    os.utime(app)  # makes Finder show the new icon
    if Path(LSREGISTER).exists():  # so Launchpad and Spotlight find it at once
        run([LSREGISTER, "-f", str(app)])
    return [app]


# ----- Linux -----------------------------------------------------------------

def _desktop_entry(info: AppInfo, python: str, icon: Path) -> str:
    exec_line = " ".join(shlex.quote(p) for p in (python, "-m", info.module)) + " %f"
    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        f"Name={info.name}\n"
        f"Comment={info.comment}\n"
        f"Exec={exec_line}\n"
        f"Icon={icon}\n"
        "Terminal=false\n"
        f"Categories={info.categories}\n"
        f"StartupWMClass={info.name}\n"
        f"X-{info.marker}-Version={info.version}\n"
        f"X-{info.marker}-Python={python}\n"
    )


def _install_linux(info: AppInfo, entry: Path, home: Path, python: str, run: Runner) -> list[Path]:
    icon = _linux_icon_path(info, home)
    _save_icon(info, icon, "png")
    entry.parent.mkdir(parents=True, exist_ok=True)
    entry.write_text(_desktop_entry(info, python, icon), encoding="utf-8")
    entry.chmod(0o755)
    if shutil.which("update-desktop-database"):
        run(["update-desktop-database", str(entry.parent)])
    return [entry, icon]


# ----- Windows ---------------------------------------------------------------

def _ps_quote(text: str) -> str:
    return "'" + text.replace("'", "''") + "'"


def windows_shortcut_command(info: AppInfo, link: Path, python: str, icon: Path, workdir: Path) -> list[str]:
    """The PowerShell command that writes the Start-menu shortcut."""
    script = (
        "$s = (New-Object -ComObject WScript.Shell).CreateShortcut(" + _ps_quote(str(link)) + "); "
        "$s.TargetPath = " + _ps_quote(python) + "; "
        f"$s.Arguments = '-m {info.module}'; "
        "$s.WorkingDirectory = " + _ps_quote(str(workdir)) + "; "
        "$s.IconLocation = " + _ps_quote(str(icon)) + "; "
        "$s.Description = " + _ps_quote(info.name) + "; "
        "$s.Save()"
    )
    return ["powershell", "-NoProfile", "-NonInteractive", "-Command", script]


def _install_windows(info: AppInfo, link: Path, home: Path, python: str, run: Runner) -> list[Path]:
    icon = _windows_icon_path(info, home)
    _save_icon(info, icon, "ico")
    link.parent.mkdir(parents=True, exist_ok=True)
    result = run(windows_shortcut_command(info, link, python, icon, home))
    if getattr(result, "returncode", 0) != 0:
        raise OSError("PowerShell could not create the shortcut")
    _windows_marker_path(info, home).write_text(json.dumps({"version": info.version, "python": python}),
                                                encoding="utf-8")
    return [link, icon]


# ----- entry points ----------------------------------------------------------

def install_app(
        info: AppInfo,
        *,
        system: str | None = None,
        home: Path | None = None,
        python: str | None = None,
        path_env: str | None = None,
        run: Runner = subprocess.run,
) -> list[Path]:
    """Create (or replace) the launcher; return the files written.

    Args:
        info: The app.
        system: ``"mac"``, ``"linux"`` or ``"windows"`` (default: this system).
        home: Home folder (default: the user's).
        python: Python to run (default: this one).
        path_env: PATH for the macOS launcher (default: the current PATH).
        run: Runs helper commands (replaced in tests).
    """
    system = system or current_system()
    home = Path(home) if home is not None else Path.home()
    exe = python_for_launcher(system, python)
    target = launcher_path(info, system, home)
    if system == "mac":
        return _install_mac(info, target, exe, path_env if path_env is not None else os.environ.get("PATH", ""),
                            run)
    if system == "windows":
        return _install_windows(info, target, home, exe, run)
    return _install_linux(info, target, home, exe, run)


def remove_app(info: AppInfo, *, system: str | None = None, home: Path | None = None) -> list[Path]:
    """Delete the launcher and its icon copy; return what was removed."""
    system = system or current_system()
    home = Path(home) if home is not None else Path.home()
    paths = [launcher_path(info, system, home)]
    if system == "linux":
        paths.append(_linux_icon_path(info, home))
    elif system == "windows":
        paths += [_windows_icon_path(info, home), _windows_marker_path(info, home)]
    removed = []
    for path in paths:
        if path.is_dir():
            shutil.rmtree(path)
            removed.append(path)
        elif path.exists():
            path.unlink()
            removed.append(path)
    if system == "windows":
        folder = _windows_icon_path(info, home).parent
        if folder.is_dir() and not any(folder.iterdir()):
            folder.rmdir()
    return removed


# ----- keeping it current ----------------------------------------------------

def launcher_info(info: AppInfo, system: str | None = None, home: Path | None = None) -> dict[str, str] | None:
    """``{"version", "python"}`` of an existing launcher, or ``None`` if there is none.

    ``version`` is the app version that made it (``""`` if not recorded), ``python`` the
    Python it starts (``""`` if unknown). Launchers that did not record the Python (Maxwell
    Bloch Studio 10.2.0) are read from their start script / Exec line.
    """
    system = system or current_system()
    home = Path(home) if home is not None else Path.home()
    target = launcher_path(info, system, home)
    try:
        if system == "mac":
            plist = target / "Contents" / "Info.plist"
            if not plist.is_file():
                return None
            data = plistlib.loads(plist.read_bytes())
            python = data.get(f"{info.marker}Python", "")
            if not python:
                script = target / "Contents" / "MacOS" / data.get("CFBundleExecutable", "")
                for line in script.read_text(encoding="utf-8").splitlines():
                    if line.startswith("exec "):
                        python = shlex.split(line)[1]
            return {"version": str(data.get("CFBundleShortVersionString", "")), "python": python}
        if system == "windows":
            if not target.exists():
                return None
            marker = _windows_marker_path(info, home)
            data = json.loads(marker.read_text(encoding="utf-8")) if marker.is_file() else {}
            return {"version": str(data.get("version", "")), "python": str(data.get("python", ""))}
        if not target.is_file():
            return None
        fields = dict(line.split("=", 1) for line in target.read_text(encoding="utf-8").splitlines() if "=" in line)
        python = fields.get(f"X-{info.marker}-Python", "")
        if not python and fields.get("Exec"):
            python = shlex.split(fields["Exec"])[0]
        return {"version": fields.get(f"X-{info.marker}-Version", ""), "python": python}
    except (OSError, ValueError, IndexError, plistlib.InvalidFileException):
        return {"version": "", "python": ""}


def _same_file(a: str, b: str) -> bool:
    """Whether two paths name the same Python (symlinks resolved)."""
    try:
        return Path(a).resolve() == Path(b).resolve()
    except OSError:
        return a == b


def refresh_if_outdated(info: AppInfo, *, system: str | None = None, home: Path | None = None,
                        python: str | None = None, path_env: str | None = None,
                        run: Runner = subprocess.run) -> bool:
    """Rebuild the launcher if it starts this installation and an older version made it.

    A launcher of another installation (e.g. a pipx copy while a source checkout runs) is
    left alone. Never raises; returns whether it rebuilt.
    """
    system = system or current_system()
    try:
        found = launcher_info(info, system, home)
        if found is None or found["version"] == info.version:
            return False
        if not found["python"] or not _same_file(found["python"], python_for_launcher(system, python)):
            return False
        install_app(info, system=system, home=home, python=python, path_env=path_env, run=run)
        return True
    except Exception:  # noqa: BLE001 - a launcher problem must never stop the app
        return False


def install_app_command(info: AppInfo, remove: bool = False, *, note: str = "") -> int:
    """The body of an ``<app> install-app [--remove]`` command: do it and print what happened.

    ``note`` is added to the line about the Python (e.g. " (your source folder)").
    """
    system = current_system()
    if remove:
        removed = remove_app(info, system=system)
        if not removed:
            print("No launcher found; nothing removed.")
        for path in removed:
            print(f"Removed {path}")
        return 0
    try:
        written = install_app(info, system=system)
    except (OSError, ValueError) as exc:
        print(f"Could not create the launcher: {exc}", file=sys.stderr)
        return 1
    print(f"Created {written[0]}")
    print(f"{info.name} is now in {PLACE[system]}.")
    print(f"It starts the installation of this Python{note}: {python_for_launcher(system)}")
    if system == "mac":
        print("Drag it to the Dock to keep it there. Run this command again if you move Python.")
    return 0
