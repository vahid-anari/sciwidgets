# Changelog

Each version is a Git tag (`vX.Y.Z`) and is on [PyPI](https://pypi.org/project/sciwidgets/).
From 0.10.4 on, pushing a tag also publishes a GitHub Release with that version's notes.

## 0.12.3 — 2026-10-21

- Updates: the notes of the newer versions only come from the app's own release tags (`v1.2.0` or
  `1.2.0`). A repository that also releases something else with tags of its own (Daftarche's
  `phone-v0.3.0`) no longer has those notes shown as the app's.

## 0.12.2 — 2026-10-19

- Updates: only one check runs at a time. Choosing Check for Updates… while the quiet start-up
  check was still running (or while its notice was open) showed the update notice twice; now the
  running check answers both.

## 0.12.1 — 2026-10-19

- About can ask to be cited: `AppHelp(..., citation=...)` (and `about_html(..., citation=...)`) adds
  a "Citing" paragraph — "If you use <app> in published work, please cite: …".

## 0.12.0 — 2026-10-19

- `sciwidgets.app.help.AppHelp`: the Help menu every app shares — User Guide (⌘?), the app's
  documents (`Document`, `DocumentMenu` for a submenu), Check for Updates… (⌘U), About — for a
  `MenuBarController` (`menu_items()` + `handle(id)`) or a plain `QMenu` (`add_to(menu)`).
- `sciwidgets.app.about`: the About text lists the libraries the app is built on, read from the
  installed metadata (the app's requirements and those of sciwidgets and mbsolver, with version
  and license, and Qt's own version), so it replaces an "About Qt" item.
- `docs/app.md`: the shortcuts the apps share, and the macOS keys to avoid.

## 0.11.4 — 2026-10-19

- `ParameterToggle`: the checkbox now starts at the left edge of its column (before, it
  was indented by half the slider names' width), and the formula label follows the
  checkbox text instead of sitting at the far right; spare width stays empty on the right.

## 0.11.3 — 2026-10-18

- Update Now right after a release: PyPI's download index can lag the new version for a
  few minutes, so pip found nothing new and the update stopped with "did not finish".
  Now the update runs again after 30 s, up to 5 times ("PyPI is still publishing …"),
  with a Stop button; `<app> update` in a terminal does the same.

## 0.11.2 — 2026-10-17

- Restart Now on macOS reopens the app's launcher (made by `install-app`), so the app
  comes back as itself instead of as "Python".

## 0.11.1 — 2026-10-17

- Update Now right after a release: pip no longer uses its cached list of PyPI versions
  (`--no-cache-dir`), so it sees the new version.
- An update counts as done only when the new version is really installed; otherwise the
  dialog (and `<app> update`) says so instead of "Updated to …".

## 0.11.0 — 2026-10-17

- New `sciwidgets.app`: an app's double-click launcher (macOS app, Windows Start menu, Linux menu entry; refreshed after updates) and its update check from PyPI (`<app> update` in the terminal; in the window a quiet check, Help ▸ Check for Updates…, the update notice with release notes, Update Now with progress and restart). The app describes itself once in an `AppInfo`. Moved here from Maxwell Bloch Studio and linecat, which had the same code. See `docs/app.md`.

## 0.10.4 — 2026-10-16

- PySide6 6.12.0 is skipped on Python < 3.12: it loses a reference to `None` every time a Python table model returns `None` from `data()`, which crashes the interpreter after enough table redraws.

## 0.10.3 — 2026-10-16

- `DataFrameModel` is about 3× faster when columns are sized: cells are read from a cached array, formatted text is cached, item roles are compared as integers.

## 0.10.2 — 2026-10-16

- Rich-text cells use the same selection colours as plain cells when the table has no focus.
- The table's window comes back to the front after the colour and font dialogs (macOS).

## 0.10.1 — 2026-10-16

- `ScrollableFigure` sizes the canvas from the figure's own dpi, so figures no longer open at half size on Retina screens.

## 0.10.0 — 2026-10-16

- `DataFrameModel(row_backgrounds=…)`: a background colour per row.

## 0.9.1 — 2026-10-16

- Table headers follow the table font; text columns that hold numbers sort numerically; per-column alignment with a header menu.

## 0.9.0 — 2026-10-16

- `sciwidgets.table`: `DataFrameModel` and `DataFrameView` (rich text, sorting, header menu with colours and font); needs `sciwidgets[table]`.
- `ScrollableFigure`, `center_on_screen`, `ParameterComboBox.set_items`.

## 0.8.1 — 2026-10-16

- Live preview in the curve and grid style dialogs.

## 0.8.0 — 2026-10-16

- Span style from the plot's right-click menu (fill, edge and centre line).

## 0.7.0 — 2026-10-15

- `sciwidgets.splash`: splash screen with the app name and version drawn on a picture, and start-up messages.

## 0.6.0 — 2026-10-14

- Test suite (pytest) and GitHub Action; `ParameterLineEdit(unit=…)`.

## 0.5.0 and earlier — 2026-10-12 to 2026-10-14

- 0.5.0: grid style dialog in the plot canvas.
- 0.4.x: `sciwidgets.plot` (`PlotCanvas` with twins, legends, markers, user styles, right-click menu, `CurveSelector`, `CurveCheckBox`).
- 0.3.0: `sciwidgets.panel` (`ParameterPage`, `ParameterTabs`, templates and defaults).
- 0.2.x: `sciwidgets.window` (`MenuBarController`, `StatusBarController`).
- 0.1.x: labels, sliders, parameter widgets, dialogs and style; 0.1.2 was the first PyPI release.
