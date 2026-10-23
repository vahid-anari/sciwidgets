# Changelog

Each version is a Git tag (`vX.Y.Z`) and is on [PyPI](https://pypi.org/project/sciwidgets/).
From 0.10.4 on, pushing a tag also publishes a GitHub Release with that version's notes.

## 0.15.1 — 2026-10-23

- `FloatSlider`, `IntSlider`, `ArraySlider` and `MultiVariableSlider` have `set_unit(unit)` and
  `get_unit()`: the unit after the value can change while the app runs (e.g. seconds → days);
  `""` hides it, and a slider made without a unit can get one.

## 0.15.0 — 2026-10-23

- Apps can be updated from the GitHub Releases of a private repository instead of PyPI:
  `AppInfo(update_source="github")`. Each release carries the built wheel; the version, the notes
  and the wheel are read with a GitHub access token kept in the user's app-data folder
  (`token_path`, `read_token`, `save_token`). "Update Now" and `<app> update` run the new
  `python -m sciwidgets.app.github_install`, which downloads the newest wheel with the token and
  installs it with pip (no git, and no token in URLs or pip's records). A missing or refused token
  is asked for again from Check for Updates… (a refused one also at start-up), or with
  `<app> update --token`. PyPI stays the default, so existing apps are unchanged.

## 0.14.3 — 2026-10-23

- devtools: an animation keeps its colours when they change on the way (e.g. a switch to dark mode);
  the GIF palette is made from frames spread over the whole animation, not from the middle one.

## 0.14.2 — 2026-10-23

- Line edits and spin boxes have a visible edge in dark mode (Fusion's edge is a shade darker than
  the window); a field with focus keeps its highlight edge.
- Disabled values and field text are easier to read in dark mode.

## 0.14.1 — 2026-10-22

- Menu separators are visible in dark mode (Fusion drew them a shade darker than the menu).

## 0.14.0 — 2026-10-22

- `sciwidgets.devtools`: take an app's documentation pictures and animated GIFs with scripts. An app
  lists `Shot`s and `Gif`s in a small tool file and calls `main`; each item runs in a fresh process with
  empty settings, a script (`Player`: drag sliders, right-click, choose menu items, type into dialogs,
  press buttons, wait for a result) brings the app into the state to show, and the window is captured
  (on macOS with title bar and shadow) or recorded. `--dark` takes a picture in dark mode.
- The repo's `tools/screenshots.py` and `tools/gifs.py` became one `tools/figures.py` built on it.

## 0.13.1 — 2026-10-22

- The widgets' own colors can be changed: `set_sci_colors(app, value=..., range_label=..., marker=...,
  invalid=...)` with a (light, dark) pair, one color for both modes, `"accent"` (the system accent
  color) or `None` for the default; also `apply_sci_style(app, rules, colors={...})`. `sci_color(name)`
  and `DEFAULT_SCI_COLORS` are public.
- Slider default markers are a lighter red in dark mode (`#ff6b6b`).
- `QDoubleSpinBox` (and the date and time editors) get the value color like `QSpinBox` and `QLineEdit`
  (the rule is now on `QAbstractSpinBox`).
- The style sheet is also applied again when the accent color changes.

## 0.13.0 — 2026-10-22

- Dark mode for the parameter widgets (sliders, line edits, combo boxes, toggles) and math labels:
  - `MathLabel` text follows the palette's text color by default (`text_color=None`; it was black)
    and is drawn again when the palette changes. An explicit `text_color` is kept.
  - The style sheet uses a lighter blue for values and light grey range labels on a dark palette,
    and `apply_sci_style` applies it again by itself when the palette switches between light and dark.
  - A disabled slider groove is dark grey on a dark palette (it was a bright bar); the current row
    in a multi-slider's value list is dark blue.
  - New in `sciwidgets.style`: `set_color_scheme(app, "light" | "dark" | "system")`, `color_scheme()`,
    `is_dark()` and `dark_palette()`. The params and sliders demos have a Dark theme check box.
- Plots in dark mode (`sciwidgets.plot`):
  - `PlotCanvas` follows the application palette (`scheme="auto"`, new argument; `set_scheme`,
    `scheme()`, `shows_dark()`). In dark mode the frame (backgrounds, text, ticks, legend box) takes
    the colours of `axes_style["dark"]`; the figure background can be set with
    `figure.dark_facecolor`.
  - Colours too dark for the dark background are drawn lighter with their hue kept (black → light
    grey, blue → lighter blue); readable colours stay as they are. `dark_variant(color)` is public.
  - A curve, line marker or span can have its own dark colour: `dark_color` (curves, lines),
    `dark_facecolor`, `dark_edgecolor`, `dark_center_color` (spans), in the description, through
    `set_curve_style`/`set_span_style`, and in the style dialogs (Dark: Automatic / Own colour).
    They are saved in the config next to the light colours.
  - `export()` saves the light colours by default, also from a dark screen (`scheme="current"`
    for what is shown). `curve_color(id)` gives the colour drawn now; selectors and menu swatches
    use it.
  - `get_curve_style` and `get_span_style` also return the dark keys (`None` = automatic).
- Tables in dark mode (`sciwidgets.table`): `DataFrameView` follows the application palette. Light
  backgrounds (column, row and user colours) are shown darkened with their hue kept, too-dark text
  colours lighter; `DataFrameModel(dark_backgrounds=..., dark=...)`, `set_dark()`, `dark()`. A cell
  with a background and no text colour of its own gets black or white text, whichever reads better
  (in light mode too: white text on a dark background a user chose). The colour dialog starts from
  white / black, since stored colours are light-mode colours.
- New module `sciwidgets.colors`: `dark_variant`, `dark_fill`, `readable_text`, `contrast_ratio`
  (`dark_variant` is also in `sciwidgets.plot`).
- Light mode looks exactly as before.
- `python -m sciwidgets`: a showcase that uses the pieces together (a parameter panel from JSON driving a
  plot, a line-list table, menus, status bar, About, dark mode). It is the README's new top picture;
  the slider picture and animation moved to `docs/sliders.md`.
- `tools/gifs.py` (repo only) records the animations from scripted demo sessions: `showcase.gif` (new,
  under the README's top picture) and `sliders_demo.gif`.
- `tools/screenshots.py` (repo only) retakes the documentation pictures from the demos, with window
  frame and shadow on macOS (`pyobjc-framework-Quartz` in the `dev` extra there). New pictures:
  `table_demo.png`, and `theme_demo.png` (light and dark) in `docs/style.md`.

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
