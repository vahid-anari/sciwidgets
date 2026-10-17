"""sciwidgets.app: launcher, update check and the update dialogs, for a made-up app."""

import argparse
import os
import plistlib
import subprocess
import sys

import pytest
from PIL import Image
from PySide6.QtWidgets import QApplication, QMainWindow

from sciwidgets.app import AppInfo, launcher, update, update_ui


@pytest.fixture
def info(tmp_path):
    icon = tmp_path / "icon.png"
    Image.new("RGBA", (512, 512), (40, 30, 120, 255)).save(icon)
    return AppInfo(name="Demo App", version="1.2.0", dist_name="demo-app", module="demoapp", command="demoapp",
                   github_repo="someone/demo-app", icon=icon, bundle_id="io.github.someone.demoapp",
                   linux_id="demo-app", marker="DemoApp", comment="A demo", categories="Science;")


@pytest.fixture(autouse=True)
def no_xdg(monkeypatch):
    for name in ("XDG_DATA_HOME", "APPDATA", "LOCALAPPDATA"):
        monkeypatch.delenv(name, raising=False)


def recorder():
    calls = []

    def run(command):
        calls.append(list(command))
        return subprocess.CompletedProcess(command, 0)
    return calls, run


def test_urls(info):
    assert info.pypi_json_url == "https://pypi.org/pypi/demo-app/json"
    assert info.releases_api_url.startswith("https://api.github.com/repos/someone/demo-app/releases")


# ----- launcher -----

def test_mac_app(info, tmp_path):
    _, run = recorder()
    home = tmp_path / "home"
    written = launcher.install_app(info, system="mac", home=home, python="/env/bin/python",
                                   path_env="/usr/bin:/Library/TeX/texbin", run=run)
    app = home / "Applications" / "Demo App.app"
    assert written == [app]
    plist = plistlib.loads((app / "Contents" / "Info.plist").read_bytes())
    assert plist["CFBundleName"] == "Demo App" and plist["CFBundleIdentifier"] == "io.github.someone.demoapp"
    assert plist["DemoAppPython"] == "/env/bin/python" and plist["CFBundleShortVersionString"] == "1.2.0"
    script = app / "Contents" / "MacOS" / plist["CFBundleExecutable"]
    text = script.read_text()
    assert 'exec /env/bin/python -m demoapp "$@"' in text and "export PATH=/usr/bin:/Library/TeX/texbin" in text
    assert os.access(script, os.X_OK)
    assert Image.open(app / "Contents" / "Resources" / "app_icon.icns").format == "ICNS"
    assert launcher.remove_app(info, system="mac", home=home) == [app] and not app.exists()
    assert launcher.remove_app(info, system="mac", home=home) == []


def test_mac_quotes_paths_with_spaces(info, tmp_path):
    _, run = recorder()
    launcher.install_app(info, system="mac", home=tmp_path, python="/Users/me/my envs/bin/python",
                         path_env="/a b:/c", run=run)
    text = next((tmp_path / "Applications").glob("*.app/Contents/MacOS/*")).read_text()
    assert "exec '/Users/me/my envs/bin/python' -m demoapp" in text and "export PATH='/a b:/c'" in text


def test_linux_entry(info, tmp_path):
    _, run = recorder()
    entry, icon = launcher.install_app(info, system="linux", home=tmp_path, python="/env/bin/python", run=run)
    assert entry == tmp_path / ".local/share/applications/demo-app.desktop"
    text = entry.read_text()
    assert "Exec=/env/bin/python -m demoapp %f" in text and "Name=Demo App" in text and "Comment=A demo" in text
    assert "X-DemoApp-Version=1.2.0" in text and Image.open(icon).size == (256, 256)
    assert sorted(launcher.remove_app(info, system="linux", home=tmp_path)) == sorted([entry, icon])


def test_windows_shortcut(info, tmp_path):
    calls, run = recorder()
    pythonw = tmp_path / "env" / "pythonw.exe"
    pythonw.parent.mkdir()
    pythonw.write_text("")
    link, icon = launcher.install_app(info, system="windows", home=tmp_path,
                                      python=str(tmp_path / "env" / "python.exe"), run=run)
    assert link.name == "Demo App.lnk" and Image.open(icon).format == "ICO"
    (command,) = calls
    assert f"TargetPath = '{pythonw}'" in command[-1] and "Arguments = '-m demoapp'" in command[-1]

    def failing(cmd):
        return subprocess.CompletedProcess(cmd, 1)
    with pytest.raises(OSError):
        launcher.install_app(info, system="windows", home=tmp_path, python="python.exe", run=failing)


@pytest.mark.parametrize("system", ["mac", "linux", "windows"])
def test_info_and_refresh(info, tmp_path, system):
    _, run = recorder()
    python = str(tmp_path / "env" / "python")
    assert launcher.launcher_info(info, system, tmp_path) is None
    assert not launcher.refresh_if_outdated(info, system=system, home=tmp_path, python=python, run=run)
    launcher.install_app(info, system=system, home=tmp_path, python=python, path_env="", run=run)
    if system == "windows":
        launcher.launcher_path(info, system, tmp_path).write_text("")
    assert launcher.launcher_info(info, system, tmp_path) == {"version": "1.2.0", "python": python}
    assert not launcher.refresh_if_outdated(info, system=system, home=tmp_path, python=python, run=run)
    newer = AppInfo(**{**info.__dict__, "version": "9.0.0"})
    other = str(tmp_path / "other" / "python")
    assert not launcher.refresh_if_outdated(newer, system=system, home=tmp_path, python=other, run=run)
    assert launcher.refresh_if_outdated(newer, system=system, home=tmp_path, python=python, run=run)
    if system == "windows":
        launcher.launcher_path(info, system, tmp_path).write_text("")
    assert launcher.launcher_info(info, system, tmp_path)["version"] == "9.0.0"


def test_launcher_without_recorded_python(info, tmp_path):
    """Older launchers (Maxwell Bloch Studio 10.2.0) did not record the Python; it is read from the script."""
    _, run = recorder()
    python = str(tmp_path / "py env" / "python")
    launcher.install_app(info, system="mac", home=tmp_path, python=python, path_env="", run=run)
    plist_path = launcher.launcher_path(info, "mac", tmp_path) / "Contents" / "Info.plist"
    plist = plistlib.loads(plist_path.read_bytes())
    del plist["DemoAppPython"]
    plist_path.write_bytes(plistlib.dumps(plist))
    assert launcher.launcher_info(info, "mac", tmp_path)["python"] == python


def test_refresh_never_raises(info, tmp_path, monkeypatch):
    monkeypatch.setattr(launcher, "launcher_info", lambda *a, **k: 1 / 0)
    assert launcher.refresh_if_outdated(info, system="linux", home=tmp_path) is False


def test_install_app_command(info, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(launcher, "current_system", lambda: "linux")
    monkeypatch.setattr(launcher.Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setattr(launcher.shutil, "which", lambda name: None)
    assert launcher.install_app_command(info) == 0
    out = capsys.readouterr().out
    assert "Demo App is now in the applications menu" in out and sys.executable in out
    assert launcher.install_app_command(info, remove=True) == 0 and "Removed" in capsys.readouterr().out
    assert launcher.install_app_command(info, remove=True) == 0
    assert "nothing removed" in capsys.readouterr().out


# ----- update (no Qt) -----

@pytest.mark.parametrize("text, expected", [("10.0.4", (10, 0, 4)), ("v0.9.1", (0, 9, 1)), ("0+unknown", (0,)),
                                            ("", ())])
def test_parse_version(text, expected):
    assert update.parse_version(text) == expected


def test_version_known():
    assert update.version_known("0.9.0") and not update.version_known("0.0.0")
    assert not update.version_known("0+unknown") and not update.version_known("")


def test_newer_release_notes():
    releases = ["junk", {"tag_name": "v1.4.0", "body": "- four", "draft": True}, {"tag_name": "v1.3.0", "body": "- 3"},
                {"tag_name": "v1.2.1", "body": "\n- 2.1\n"}, {"tag_name": "v1.2.0", "body": "- 2"},
                {"tag_name": "v1.1.0", "body": " "}]
    assert update.newer_release_notes(releases, "1.2.0", "1.3.0") == [("1.3.0", "- 3"), ("1.2.1", "- 2.1")]
    many = [{"tag_name": f"v2.0.{i}", "body": f"- {i}"} for i in range(1, 30)]
    assert len(update.newer_release_notes(many, "2.0.0", "2.0.29")) == update.MAX_NOTES


def do_update(info, check=False, yes=False, latest="9.0.0", notes=(), kind="pip", answer="n"):
    calls = []

    def run(command):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0)

    code = update.run_update(info, argparse.Namespace(check=check, yes=yes), latest_version=lambda: latest,
                             release_notes=lambda current, newest: list(notes), kind=lambda: kind,
                             ask=lambda prompt: answer, run=run)
    return code, calls


def test_run_update(info, capsys):
    assert do_update(info, latest="1.2.0") == (0, [])
    assert "Demo App 1.2.0 is the latest version" in capsys.readouterr().out
    assert do_update(info, check=True, notes=[("9.0.0", "- big news")]) == (0, [])
    assert "- big news" in capsys.readouterr().out
    assert do_update(info, answer="n") == (0, [])
    assert do_update(info, answer="y") == (0, [[sys.executable, "-m", "pip", "install", "--upgrade", "demo-app"]])
    code, calls = do_update(info, yes=True, kind="pipx")
    assert code == 0 and calls[0][1:] == ["upgrade", "demo-app"]
    assert do_update(info, yes=True, kind="editable") == (1, [])
    assert "git pull" in capsys.readouterr().err
    assert do_update(info, yes=True, kind="unknown") == (1, [])

    def offline():
        raise OSError("no network")
    assert update.run_update(info, argparse.Namespace(check=True, yes=False), latest_version=offline) == 1


def test_install_kind_of_an_unknown_package(info):
    assert update.install_kind(info) == "unknown" and update.update_command(info, "unknown") is None


# ----- update UI -----

def test_checker_without_network(info):
    seen = []
    unknown = AppInfo(**{**info.__dict__, "version": "0+unknown"})
    checker = update_ui.UpdateChecker(unknown)
    checker.checkFailed.connect(lambda msg: seen.append("failed"))
    checker.check()
    checker = update_ui.UpdateChecker(info)
    checker.upToDate.connect(lambda: seen.append("up to date"))
    checker.handle_latest("1.2.0")
    assert seen == ["failed", "up to date"]


def run_progress(info, code):
    dialog = update_ui.UpdateProgressDialog([sys.executable, "-c", code], info, "9.0", "Run it by hand.",
                                            success_note="Unsaved work is asked about.")
    dialog.start()
    assert dialog.wait()
    QApplication.processEvents()
    return dialog


def test_progress_success_and_failure(info):
    ok = run_progress(info, "print('Successfully upgraded')")
    assert ok.succeeded and "Successfully upgraded" in ok._output.toPlainText()
    assert "Updated to 9.0" in ok._status.text() and "Unsaved work is asked about." in ok._status.text()
    ok._choose_restart()
    assert ok.restart_requested
    bad = run_progress(info, "import sys; print('No network'); sys.exit(1)")
    assert not bad.succeeded and "Run it by hand." in bad._status.text() and not bad._restart.isVisibleTo(bad)
    for dialog in (ok, bad):
        dialog.deleteLater()


def test_restart(info):
    started = []
    assert update_ui.restart_app(info, lambda: True, lambda program, args: started.append([program, *args]))
    assert started == [[sys.executable, "-m", "demoapp"]]
    assert not update_ui.restart_app(info, lambda: False, lambda program, args: started.append(program))


@pytest.mark.parametrize("can_update, hint", [(True, ""), (False, "Use git pull."), (False, "")])
def test_update_dialog(info, can_update, hint):
    dialog = update_ui.UpdateDialog(info, "9.0", "pipx upgrade demo-app", [("9.0", "- news")],
                                    can_update=can_update, hint=hint)
    assert dialog.update_btn.isEnabled() is can_update
    if can_update:
        dialog.update_btn.click()
        assert dialog.result() == update_ui.UpdateDialog.UPDATE_NOW
    dialog.deleteLater()


def test_app_updates_flow(info, monkeypatch):
    window = QMainWindow()
    messages, dialogs = [], []
    monkeypatch.setattr(update_ui, "show_information", lambda title, text, **k: messages.append(text))
    monkeypatch.setattr(update_ui, "show_warning", lambda title, text, *a, **k: messages.append(text))
    monkeypatch.setattr(update_ui.UpdateDialog, "exec", lambda self: dialogs.append(self) or 0)
    updates = update_ui.AppUpdates(window, info)
    monkeypatch.setattr(updates.checker, "check", lambda: updates.checker.upToDate.emit())
    updates.check()                                                     # quiet at start-up
    assert messages == []
    updates.check(manual=True)
    assert messages == ["Demo App 1.2.0 is the latest version."]
    monkeypatch.setattr(updates.checker, "check", lambda: updates.checker.checkFailed.emit("offline"))
    updates.check()
    updates.check(manual=True)
    assert messages[-1] == "Could not check for updates." and len(messages) == 2
    updates.checker.updateAvailable.emit("9.0.0", [("9.0.0", "- news")])
    assert len(dialogs) == 1 and not dialogs[0].update_btn.isEnabled()  # not installed: no Update Now
    window.deleteLater()
