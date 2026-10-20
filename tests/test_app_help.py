"""Tests for sciwidgets.app.help (the shared Help menu) and sciwidgets.app.about."""

from pathlib import Path

import pytest
from PySide6.QtWidgets import QMainWindow, QMenu

from sciwidgets.app import AppInfo
from sciwidgets.app import about, help as app_help
from sciwidgets.app.about import Library, short_license
from sciwidgets.app.help import AppHelp, Document, DocumentMenu
from sciwidgets.window import MenuBarController


@pytest.fixture
def info(tmp_path):
    return AppInfo(name="Demo App", version="1.2.0", dist_name="sciwidgets", module="demoapp", command="demoapp",
                   github_repo="someone/demo-app", icon=tmp_path / "icon.png", bundle_id="io.github.someone.demoapp",
                   linux_id="demo-app", marker="DemoApp", comment="A demo app")


@pytest.fixture
def window(qapp):
    w = QMainWindow()
    yield w
    w.close()
    w.deleteLater()


class FakeMeta(dict):
    def get_all(self, key):
        value = self.get(key)
        return value if isinstance(value, list) else None


@pytest.mark.parametrize("meta, expected", [
    (FakeMeta({"License-Expression": "LGPL-3.0-only OR GPL-3.0-only"}), "LGPL-3.0"),
    (FakeMeta({"License-Expression": "BSD-3-Clause AND MIT"}), "BSD-3-Clause"),
    (FakeMeta({"License": "MIT"}), "MIT"),
    (FakeMeta({"License": "a very long\nlicense text", "Classifier": ["License :: OSI Approved :: BSD License"]}),
     "BSD"),
    (FakeMeta({"Classifier": ["License :: OSI Approved :: Python Software Foundation License"]}), "PSF"),
    (FakeMeta({}), "see its project page"),
])
def test_short_license(meta, expected):
    assert short_license(meta) == expected


def test_libraries_come_from_the_installed_metadata(info):
    """sciwidgets' own requirements: PySide6 (followed by Qt), Matplotlib, NumPy, psutil."""
    libs = about.app_libraries(info)
    names = [lib.name.lower() for lib in libs]
    assert {"pyside6", "qt", "matplotlib", "numpy", "psutil"} <= set(names)
    assert names.index("qt") == names.index("pyside6") + 1
    qt = libs[names.index("qt")]
    assert qt.license == "LGPL-3.0" and qt.version == about.qt_version()
    assert all(lib.version for lib in libs)


def test_about_text(info):
    text = about.about_html(info, author="Someone", extra_html="Data: <i>somewhere</i>",
                            libraries=[Library("NumPy", "2.0", "BSD-3-Clause", "https://numpy.org")])
    for part in ("Version 1.2.0", "A demo app", "github.com/someone/demo-app", "MIT License · Someone",
                 "Data: <i>somewhere</i>", '<a href="https://numpy.org">NumPy</a>', "BSD-3-Clause", "Built with"):
        assert part in text
    assert "Built with" not in about.about_html(info, libraries=[])
    assert "Citing" not in text


def test_about_asks_for_a_citation(info, window):
    ref = 'Someone (2026). <a href="https://doi.org/10.1/x">doi:10.1/x</a>'
    text = AppHelp(window, info, citation=ref, libraries=[]).about_html()
    assert "<b>Citing</b>" in text and "If you use Demo App in published work" in text and ref in text


def test_menu_items_order_and_shortcuts(window, info, tmp_path):
    docs = DocumentMenu("CDMS Documentation", [Document("CDMS", tmp_path / "a.pdf"), Document("B", tmp_path / "b.pdf")])
    helper = AppHelp(window, info, user_guide=tmp_path / "guide.pdf", documents=[docs])
    items = helper.menu_items()
    assert items[0]["text"] == "User Guide" and "shortcut" in items[0]
    assert items[1]["submenu"] == "CDMS Documentation" and len(items[1]["items"]) == 2
    texts = [i.get("text", i.get("id")) for i in items]
    assert texts[2:] == ["sep", "Check for Updates…", "sep", "About Demo App"]
    assert items[3]["shortcut"] == app_help.UPDATES_SHORTCUT == "Ctrl+U"
    ids = [i["id"] for i in items if "id" in i and i["id"] != "sep"] + [i["id"] for i in items[1]["items"]]
    assert all(i.startswith("help_") for i in ids) and len(set(ids)) == len(ids)


def test_without_documents_the_menu_starts_with_updates(window, info):
    items = AppHelp(window, info).menu_items()
    assert [i.get("text", i.get("id")) for i in items] == ["Check for Updates…", "sep", "About Demo App"]


def test_handle_dispatches(window, info, tmp_path, monkeypatch):
    guide = tmp_path / "guide.pdf"
    guide.write_bytes(b"%PDF")
    helper = AppHelp(window, info, user_guide=guide)
    opened, calls = [], []
    monkeypatch.setattr(app_help.QDesktopServices, "openUrl", lambda url: opened.append(url.toLocalFile()))
    monkeypatch.setattr(helper, "show_about", lambda: calls.append("about"))
    monkeypatch.setattr(helper, "check_for_updates", lambda: calls.append("updates"))
    assert helper.handle("help_doc_0") and opened == [str(guide)]
    assert helper.handle("help_about") and helper.handle("help_updates")
    assert calls == ["about", "updates"]
    assert not helper.handle("open_file") and not helper.handle("help_doc_9")


def test_missing_document_warns(window, info, tmp_path, monkeypatch):
    warnings = []
    monkeypatch.setattr(app_help, "show_warning", lambda *a, **k: warnings.append(a))
    helper = AppHelp(window, info, user_guide=tmp_path / "missing.pdf", missing_hint="Build it first.")
    helper.handle("help_doc_0")
    assert warnings and "User Guide" in warnings[0][0] and "Build it first." in warnings[0][2]


def test_same_menu_through_the_controller_and_a_plain_menu(window, info, tmp_path):
    helper = AppHelp(window, info, user_guide=tmp_path / "guide.pdf",
                     documents=[Document("Equations", tmp_path / "eq.pdf")])
    controller = MenuBarController(window, {"Help": helper.menu_items()}, native_menubar=False)
    assert controller.action("help_updates").shortcut().toString() == "Ctrl+U"
    plain = QMenu()
    helper.add_to(plain)
    texts = [a.text() for a in plain.actions() if not a.isSeparator()]
    assert texts == ["User Guide", "Equations", "Check for Updates…", "About Demo App"]
    plain.deleteLater()
