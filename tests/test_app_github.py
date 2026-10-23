"""Updates from a (private) GitHub repository: token, releases with wheels, install, UI flow."""

import argparse
import http.server
import json
import os
import stat
import subprocess
import sys
import threading

import pytest
from PySide6.QtWidgets import QMainWindow

from sciwidgets.app import AppInfo, github_install, update, update_ui


@pytest.fixture
def info(tmp_path):
    return AppInfo(name="Demo App", version="1.2.0", dist_name="demo-app", module="demoapp", command="demoapp",
                   github_repo="someone/demo-app", icon=tmp_path / "icon.png", bundle_id="io.github.someone.demoapp",
                   linux_id="demo-app", marker="DemoApp", update_source="github")


@pytest.fixture
def token_file(tmp_path, monkeypatch):
    """The app's token lives in tmp_path, never in the real home folder."""
    path = tmp_path / "config" / "token"
    monkeypatch.setattr(update, "token_path", lambda info, **k: path)
    monkeypatch.setattr(update_ui, "token_path", lambda info, **k: path)
    return path


def release(tag, *, wheel=True, draft=False, prerelease=False, body="- news"):
    assets = [{"id": 7, "name": f"demo_app-{tag.lstrip('v')}-py3-none-any.whl"}] if wheel else []
    return {"tag_name": tag, "draft": draft, "prerelease": prerelease, "body": body, "assets": assets}


RELEASES = [release("v2.0.0", draft=True), release("v1.9.0", prerelease=True), release("v1.5.0", wheel=False),
            release("v1.4.0", body="- four"), release("phone-v9.0.0"), release("v1.3.0", body="- three")]


def test_update_source_is_checked(info):
    assert info.from_github and not AppInfo(**{**info.__dict__, "update_source": "pypi"}).from_github
    with pytest.raises(ValueError, match="update_source"):
        AppInfo(**{**info.__dict__, "update_source": "ftp"})


def test_token_path(info, tmp_path, monkeypatch):
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.delenv("APPDATA", raising=False)
    assert update.token_path(info, system="mac", home=tmp_path) == (
        tmp_path / "Library" / "Application Support" / "Demo App" / "token")
    assert update.token_path(info, system="linux", home=tmp_path) == tmp_path / ".config" / "demo-app" / "token"
    assert update.token_path(info, system="windows", home=tmp_path) == (
        tmp_path / "AppData" / "Roaming" / "Demo App" / "token")


def test_save_and_read_token(tmp_path):
    path = tmp_path / "a" / "token"
    assert update.read_token(path) == ""
    update.save_token(path, "  github_pat_abc \n")
    assert update.read_token(path) == "github_pat_abc"
    if os.name == "posix":
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
    with pytest.raises(ValueError):
        update.save_token(path, "  ")


def test_latest_release():
    version, rel = update.latest_release(RELEASES)
    assert version == "1.4.0" and rel["body"] == "- four"     # no draft, pre-release, wheel-less or other tag
    assert update.latest_release([release("v1.0", wheel=False)]) is None
    assert update.wheel_asset(rel)["name"].endswith(".whl")


def test_update_command_and_tries(info, token_file):
    command = update.update_command(info, "pipx")
    assert command == [sys.executable, "-m", "sciwidgets.app.github_install", "--repo", "someone/demo-app",
                       "--token-file", str(token_file)]
    assert update.update_command(info, "pip") == command
    assert update.update_command(info, "editable") is None and update.update_command(info, "unknown") is None
    assert update.update_tries(info) == 1
    assert "did not install 9.0" in update.not_updated_message(info, "1.2.0", "9.0")


# ----- a fake GitHub API on localhost -----

class FakeGitHub(http.server.BaseHTTPRequestHandler):
    seen: list = []
    token = "good-token"

    def log_message(self, *args):
        pass

    def do_GET(self):
        FakeGitHub.seen.append((self.path, self.headers.get("Authorization")))
        if self.path.startswith("/storage/"):              # the signed download URL: no second credential
            if self.headers.get("Authorization"):
                self.send_error(400, "Only one auth mechanism allowed")
                return
            body = b"wheel bytes"
        elif self.headers.get("Authorization") != f"Bearer {FakeGitHub.token}":
            self.send_error(404)
            return
        elif self.path.startswith("/repos/someone/demo-app/releases/assets/7"):
            assert self.headers.get("Accept") == "application/octet-stream"
            self.send_response(302)
            self.send_header("Location", "/storage/demo_app.whl?signature=x")
            self.end_headers()
            return
        elif self.path.startswith("/repos/someone/demo-app/releases"):
            body = json.dumps(RELEASES).encode()
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


@pytest.fixture
def fake_github(monkeypatch):
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), FakeGitHub)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    FakeGitHub.seen = []
    monkeypatch.setattr(update, "GITHUB_API", f"http://127.0.0.1:{server.server_address[1]}")
    yield FakeGitHub
    server.shutdown()


def test_releases_and_download_with_token(fake_github, tmp_path):
    with pytest.raises(update.AccessDenied):
        update.github_releases("someone/demo-app", "")
    with pytest.raises(update.AccessDenied, match="404"):
        update.github_releases("someone/demo-app", "old-token")
    releases = update.github_releases("someone/demo-app", "good-token")
    _, rel = update.latest_release(releases)
    wheel = update.download_wheel("someone/demo-app", rel, "good-token", tmp_path)
    assert wheel.name == "demo_app-1.4.0-py3-none-any.whl" and wheel.read_bytes() == b"wheel bytes"
    storage = [auth for path, auth in fake_github.seen if path.startswith("/storage/")]
    assert storage == [None]                                  # the token is not sent on after the redirect


def test_fetch_for_an_app(info, token_file, fake_github):
    with pytest.raises(update.AccessDenied, match="no access token"):
        update.fetch_latest_version(info)
    update.save_token(token_file, "old-token")
    with pytest.raises(update.AccessDenied, match="refused"):
        update.fetch_latest_version(info)
    assert update.fetch_release_notes(info, "1.2.0", "1.4.0") == []
    update.save_token(token_file, "good-token")
    assert update.fetch_latest_version(info) == "1.4.0"
    assert update.fetch_release_notes(info, "1.2.0", "1.4.0") == [("1.4.0", "- four"), ("1.3.0", "- three")]


def test_install_latest(capsys):
    calls = []

    def run(command):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0)

    def download(repo, rel, token, dest):
        wheel = dest / update.wheel_asset(rel)["name"]
        wheel.write_bytes(b"x")
        return wheel

    code = github_install.install_latest("someone/demo-app", "t", python="/env/python", run=run,
                                         releases=lambda repo, token: RELEASES, download=download)
    assert code == 0 and calls[0][:5] == ["/env/python", "-m", "pip", "install", "--upgrade"]
    assert calls[0][5].endswith("demo_app-1.4.0-py3-none-any.whl")
    assert "Downloading version 1.4.0" in capsys.readouterr().out

    def refused(repo, token):
        raise update.AccessDenied("GitHub refused the access token (HTTP 401).")
    assert github_install.install_latest("someone/demo-app", "t", run=run, releases=refused) == 3
    assert github_install.install_latest("someone/demo-app", "t", run=run, releases=lambda r, t: []) == 1


def test_install_main_without_token(tmp_path, capsys):
    assert github_install.main(["--repo", "a/b", "--token-file", str(tmp_path / "none")]) == 2
    assert "No access token" in capsys.readouterr().err


def test_run_update_token_option(info, token_file, capsys):
    args = argparse.Namespace(check=True, yes=False, token=True)
    code = update.run_update(info, args, get_token=lambda prompt: "new-token\n",
                             latest_version=lambda: "1.2.0", release_notes=lambda current, latest: [])
    assert code == 0 and update.read_token(token_file) == "new-token"
    assert "Access token saved" in capsys.readouterr().out
    assert update.run_update(info, args, get_token=lambda prompt: " ", latest_version=lambda: "1.2.0") == 1
    pypi = AppInfo(**{**info.__dict__, "update_source": "pypi"})
    assert update.run_update(pypi, args, latest_version=lambda: "1.2.0") == 1


def test_run_update_runs_once(info, token_file, capsys):
    calls = []

    def run(command):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0)
    code = update.run_update(info, argparse.Namespace(check=False, yes=True), latest_version=lambda: "1.4.0",
                             release_notes=lambda current, latest: [], kind=lambda: "pipx", run=run,
                             installed=lambda: "1.2.0", sleep=lambda s: None)
    assert code == 1 and len(calls) == 1 and calls[0][2] == "sciwidgets.app.github_install"
    assert "did not install 1.4.0" in capsys.readouterr().err


# ----- in the window -----

def test_checker_handles_releases(info, spy):
    checker = update_ui.UpdateChecker(info)
    available, up, failed = spy(checker.updateAvailable), spy(checker.upToDate), spy(checker.checkFailed)
    checker.handle_releases(RELEASES)
    assert available.calls == [("1.4.0", [("1.4.0", "- four"), ("1.3.0", "- three")])]
    newer = update_ui.UpdateChecker(AppInfo(**{**info.__dict__, "version": "1.4.0"}))
    up = spy(newer.upToDate)
    newer.handle_releases(RELEASES)
    checker.handle_releases([])
    assert len(up) == 1 and "no release with a wheel" in failed.calls[0][0]


def test_checker_without_token(info, token_file, spy):
    checker = update_ui.UpdateChecker(info)
    denied = spy(checker.accessDenied)
    checker.check()
    assert denied.calls[0][1] is False and "no access token" in denied.calls[0][0]


def test_dialog_without_pypi_buttons(info):
    dialog = update_ui.UpdateDialog(info, "1.4.0", "python -m sciwidgets.app.github_install", [("1.4.0", "- four")],
                                    can_update=True)
    texts = {b.text(): b.isVisibleTo(dialog) for b in dialog.findChildren(update_ui.QPushButton)}
    assert texts["Open PyPI Page"] is False and texts["Open Release Notes"] is False and texts["Update Now"]
    dialog.deleteLater()


def test_app_updates_asks_for_a_token(info, token_file, monkeypatch):
    window = QMainWindow()
    asked, requests = [], []
    answers = iter(["", "fresh-token"])
    monkeypatch.setattr(update_ui, "ask_token", lambda parent, inf, message: asked.append(message) or next(answers))
    updates = update_ui.AppUpdates(window, info)
    monkeypatch.setattr(updates.checker, "check", lambda: requests.append(1))

    updates.checker.accessDenied.emit("no token", False)       # quiet start-up check, no token yet: silent
    assert asked == [] and not updates.busy
    updates.check(manual=True)
    updates.checker.accessDenied.emit("no token", False)       # menu: asked, cancelled
    assert asked == ["no token"] and update.read_token(token_file) == "" and not updates.busy
    updates.check()
    updates.checker.accessDenied.emit("refused", True)         # quiet check, expired token: asked
    assert asked[-1] == "refused" and update.read_token(token_file) == "fresh-token"
    assert len(requests) == 3 and updates.busy                 # checked again with the new token
    window.deleteLater()


def test_checker_over_the_network(info, token_file, fake_github, monkeypatch, spy):
    """The Qt check sends the token and tells a refused token from other failures."""
    from PySide6.QtTest import QTest
    monkeypatch.setattr(AppInfo, "releases_api_url",
                        property(lambda self: f"{update.GITHUB_API}/repos/{self.github_repo}/releases?per_page=30"))
    checker = update_ui.UpdateChecker(info)
    available, denied = spy(checker.updateAvailable), spy(checker.accessDenied)
    update.save_token(token_file, "old-token")
    checker.check()
    for _ in range(100):
        if denied.calls:
            break
        QTest.qWait(20)
    assert denied.calls[0][1] is True and "refused" in denied.calls[0][0]
    update.save_token(token_file, "good-token")
    checker.check()
    for _ in range(100):
        if available.calls:
            break
        QTest.qWait(20)
    assert available.calls[0][0] == "1.4.0"
    assert fake_github.seen[-1][1] == "Bearer good-token"


def test_dialog_stays_narrow(info, qapp):
    """The GitHub update command is long (paths to the app's Python and token); it must not widen the notice."""
    from PySide6.QtWidgets import QLabel

    long_command = "/Users/someone/Library/Application Support/Demo App/venv/bin/python -m " \
                   "sciwidgets.app.github_install --repo someone/demo-app --token-file " \
                   "/Users/someone/Library/Application Support/Demo App/token"
    github = update_ui.UpdateDialog(info, "1.4.0", long_command, [("1.4.0", "- four")], can_update=True)
    texts = " ".join(label.text() for label in github.findChildren(QLabel))
    assert "github_install" not in texts and "GitHub releases" in texts
    pypi = AppInfo(**{**info.__dict__, "update_source": "pypi"})
    for dialog in (github, update_ui.UpdateDialog(pypi, "1.4.0", long_command, [], can_update=True)):
        assert dialog.minimumSizeHint().width() < 700
        dialog.deleteLater()


def test_https_uses_certifi(monkeypatch):
    """python.org's macOS Python has no CA certificates of its own; certifi's list is used instead."""
    import certifi

    seen = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self):
            return b"[]"

    def fake_urlopen(request, timeout=None, context=None):
        seen.append(context)
        return Response()

    monkeypatch.setattr(update.urllib.request, "urlopen", fake_urlopen)
    assert update.github_releases("someone/demo-app", "t") == []
    ctx = seen[0]
    assert ctx is not None and ctx.verify_mode.name == "CERT_REQUIRED"
    loaded = ctx.cert_store_stats()["x509_ca"]
    assert loaded == update.ssl.create_default_context(cafile=certifi.where()).cert_store_stats()["x509_ca"] > 0
