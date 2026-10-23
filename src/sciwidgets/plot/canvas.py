"""A Matplotlib canvas built from a plain description of panels and curves.

The description says what is plotted where; the app then only feeds data by
curve id::

    canvas = PlotCanvas({
        "layout": {"mosaic": [["flux"], ["profiles"]], "height_ratios": [5, 2],
                   "sharex": True},
        "styles": {"data": {"linestyle": "", "marker": "o", "markersize": 3, "color": "k"},
                   "model": {"linewidth": 1.25}},
        "panels": {
            "flux": {"primary": "flux", "legend": {"loc": "upper right"},
                     "curves": {"data": {"label": "data", "style": "data"},
                                "flux": {"label": "F", "unit": "Jy", "style": "model"}}},
            "profiles": {"select": "one", "curves": {...},
                         "twin": {"curves": {"w": {"label": "w", "style": "model"}}}},
        },
    })
    canvas.set_curve_data("flux", t, f)
    canvas.redraw()

Description keys:

``layout``
    ``mosaic`` (rows of panel ids, ``"."`` for an empty cell, see
    Matplotlib's ``subplot_mosaic``), optional ``height_ratios``,
    ``width_ratios``, ``hspace``, ``wspace``, and ``sharex``: ``true`` for
    all panels or a list of panel ids that share their x axis.
``figure``
    Keyword arguments of ``matplotlib.figure.Figure`` (``figsize``, ``dpi``,
    ``facecolor``, ...), ``margins`` (``left``, ``right``, ``bottom``,
    ``top`` as for ``subplots_adjust``) and ``dark_facecolor``, the figure
    background in dark mode.
``styles``
    Named line styles (Matplotlib ``Line2D`` properties).
``axes_style``
    Overrides of the shared axis styling (see ``DEFAULT_AXES_STYLE``).
``panels``
    One entry per panel id of the mosaic:

    * ``curves``: ``{id: {"label", "unit", "legend", "name", "style", "props"}}``.
      ``label`` and ``unit`` are math text (without ``$``) used for the axis
      label; ``legend`` is the legend text (default: the label); ``name`` is
      plain text for menus (default: the id); ``props`` overrides single
      properties of the style.
    * ``x``, ``y``: ``{"label", "unit", "scale", "lim"}`` for the axis.
    * ``primary``: the curve whose colour the zero line and the y grid take
      and whose label/unit name the y axis, unless ``y`` has a label.
    * ``select``: ``"one"`` shows one curve at a time (see ``select_curve``);
      the shown curve is then the primary one.
    * ``zero_line``: draw a horizontal line at y = 0 (default true).
    * ``legend``: Matplotlib legend arguments; without it, no legend.
    * ``grid``: line properties of this panel's value-axis grid lines
      (added to ``grid_value``).
    * ``twin``: a second axis sharing the panel: ``{"axis": "x"}`` (default)
      adds a y axis on the right, ``{"axis": "y"}`` an x axis on top. It
      takes ``curves``, ``x``/``y``, ``primary``, ``select``, ``zero_line``
      and ``grid`` like a panel, and is addressed as ``"<panel>.twin"``.
``markers``
    Lines and bands drawn across panels, e.g. to highlight a time window:
    ``{id: {"kind": "vline" | "hline" | "vspan" | "hspan", "panels": "all" or
    [panel ids], "at": x (or y) for a line, [lo, hi] for a span,
    "visible": bool, "name": text for menus, "props": {...}}}``. Move them
    with ``set_marker``. A span may name a line marker drawn at its centre,
    ``"center": line id``; the line then belongs to the span. The user can
    change the style of spans (fill, edge and centre line) from the
    right-click menu; see ``set_span_style``.

Light and dark mode
    The canvas follows the application palette (see ``set_scheme``). In dark
    mode the frame (backgrounds, text, ticks, legend box) takes the colours of
    ``axes_style["dark"]``, and every colour too dark for the dark background
    is drawn lighter, with its hue kept (``dark_variant``). A colour can be
    given its own dark version instead: ``"dark_color"`` in a curve's style or
    props and in a line marker's props, ``"dark_facecolor"`` and
    ``"dark_edgecolor"`` (or ``"dark_color"`` for both) in a span's props. The
    user can do the same in the style dialogs. Exports are light by default.

User changes
    Right-clicking a panel opens a menu to change curve styles (colour,
    line, marker), span styles (fill and edge), show or hide curves, grids
    and the legend. ``get_config``
    returns only what differs from the description, ``set_config`` restores
    it, and ``configChanged`` reports changes the user made.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import matplotlib as mpl
import matplotlib.colors as mcolors
from matplotlib.axes import Axes
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.ticker import AutoMinorLocator, ScalarFormatter
from PySide6.QtCore import QEvent, QTimer, Signal
from PySide6.QtGui import QAction, QCursor
from PySide6.QtWidgets import QDialog, QMenu, QWidget

from ..style import is_dark
from ..colors import dark_variant
from ._icons import color_icon
from ._style_dialog import CurveStyleDialog, GridStyleDialog, SpanStyleDialog

__all__ = ["DEFAULT_AXES_STYLE", "PlotCanvas", "axis_text", "dark_variant"]

DEFAULT_AXES_STYLE: Dict[str, Any] = {
    "zero_line": {"color": "k", "linestyle": "--", "linewidth": 0.75, "alpha": 0.6},
    "label_font": {"fontsize": 12},
    "offset_font": {"fontsize": 10},
    "ticks": {"direction": "in", "left": True, "right": True, "top": True, "bottom": True},
    "ticks_major": {"length": 3.5, "width": 0.7},
    "ticks_minor": {"length": 1.75, "width": 0.5},
    "minor_locator": [4, 4],
    "x_format": "plain",
    "y_format": "sci",
    "sci_limits": [-2, 3],
    "grid": {},
    "grid_value": {"alpha": 0.3},
    "ticks_x": {},
    "ticks_y": {},
    "label_pad": [None, None],
    "dark": {"figure": "#2a2a2a", "axes": "#1e1e1e", "text": "#d8d8d8", "edge": "#9a9a9a",
             "legend_face": "#2a2a2a", "legend_edge": "#606060"},
}
"""Shared axis styling; a description's ``axes_style`` overrides single keys.

``minor_locator`` is the number of minor intervals per major one, for x and
y; ``x_format``/``y_format`` are ``"plain"`` or ``"sci"`` (scientific with
an offset text when outside ``sci_limits``); ``ticks_x``/``ticks_y`` are
extra tick settings for one axis only (e.g. ``{"pad": 5}``); ``label_pad``
is the x and y label distance in points (``None`` = Matplotlib's default);
``grid`` styles all grid lines, ``grid_value`` additionally the lines along
the value axis (horizontal for a panel), which take the primary curve's
colour. ``dark`` holds the frame colours of dark mode: ``figure`` and
``axes`` backgrounds (a description's ``figure.dark_facecolor`` takes
precedence for the figure), ``text`` (labels, tick numbers, legend text),
``edge`` (axes edges and ticks), ``legend_face`` and ``legend_edge``.
"""

_PANEL_KEYS = frozenset({"curves", "x", "y", "primary", "select", "zero_line", "legend", "grid", "twin"})
_TWIN_KEYS = frozenset({"axis", "curves", "x", "y", "primary", "select", "zero_line", "grid"})
_CURVE_KEYS = frozenset({"label", "unit", "legend", "name", "style", "props"})
_STYLE_KEYS = ("color", "dark_color", "linestyle", "linewidth", "marker", "markersize")
_GRID_STYLE_KEYS = ("linestyle", "linewidth", "alpha")
_GRID_KEYS = {("y", "major"): "y_major", ("y", "minor"): "y_minor",
              ("x", "major"): "x_major", ("x", "minor"): "x_minor"}
_MARKER_KEYS = frozenset({"kind", "panels", "at", "visible", "name", "center", "props"})
_MARKER_KINDS = ("vline", "hline", "vspan", "hspan")
_SPAN_KINDS = ("vspan", "hspan")
_SPAN_STYLE_KEYS = ("facecolor", "dark_facecolor", "alpha", "edgecolor", "dark_edgecolor", "edge_alpha",
                    "linewidth", "linestyle")
_CENTER_STYLE_KEYS = ("center_color", "dark_center_color", "center_alpha", "center_linewidth", "center_linestyle")
_SCHEMES = ("auto", "light", "dark")
_LINESTYLE_NAMES = {"solid": "-", "dashed": "--", "dotted": ":", "dashdot": "-.",
                    "none": "None", " ": "None", "": "None"}


def _short_linestyle(style: Any) -> str:
    """Return a line style as ``"-"``, ``"--"``, ``":"``, ``"-."`` or ``"None"``."""
    if not isinstance(style, str):  # a dash tuple: show it as dashed
        return "--"
    return _LINESTYLE_NAMES.get(style.lower(), style)


def _span_style_of(patch: Any) -> Dict[str, Any]:
    """Read fill and edge style of a span patch (opacities from the RGBA colours)."""
    face = mcolors.to_rgba(patch.get_facecolor())
    edge = mcolors.to_rgba(patch.get_edgecolor())
    return {
        "facecolor": mcolors.to_hex(face),
        "alpha": round(float(face[3]), 4),
        "edgecolor": mcolors.to_hex(edge),
        "edge_alpha": round(float(edge[3]), 4),
        "linewidth": float(patch.get_linewidth()),
        "linestyle": _short_linestyle(patch.get_linestyle()),
    }


def _line_style_of(line: Any) -> Dict[str, Any]:
    """Read the style of a line marker as ``center_*`` keys of a span style."""
    rgba = mcolors.to_rgba(line.get_color())
    alpha = line.get_alpha()
    return {
        "center_color": mcolors.to_hex(rgba),
        "center_alpha": round(float(rgba[3] * (1.0 if alpha is None else alpha)), 4),
        "center_linewidth": float(line.get_linewidth()),
        "center_linestyle": _short_linestyle(line.get_linestyle()),
    }


def axis_text(label: str, unit: str = "") -> str:
    """Return the math text of an axis label, e.g. ``$F\\; (\\mathrm{Jy})$``.

    Args:
        label: Quantity in math text, without ``$``.
        unit: Unit in math text, without ``$``; empty for none.

    Returns:
        The label, or ``""`` if ``label`` is empty.
    """
    if not label:
        return ""
    if unit:
        return rf"${label}\; (\mathrm{{{unit}}})$"
    return rf"${label}$"


def _merge(base: Mapping[str, Any], override: Mapping[str, Any]) -> Dict[str, Any]:
    """Return ``base`` updated by ``override``; nested dicts merge key by key."""
    out = copy.deepcopy(dict(base))
    for key, value in override.items():
        if isinstance(value, Mapping) and isinstance(out.get(key), Mapping):
            out[key] = _merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


def _check_keys(spec: Mapping[str, Any], allowed: frozenset, where: str) -> None:
    """Raise ``ValueError`` for keys outside ``allowed`` (usually typos)."""
    unknown = set(spec) - allowed
    if unknown:
        raise ValueError(f"{where}: unknown key(s) {sorted(unknown)}")


@dataclass
class _Curve:
    """One plotted line and its description."""

    id: str
    axis_id: str
    line: Line2D
    label: str = ""
    unit: str = ""
    legend: str = ""
    name: str = ""


@dataclass
class _Marker:
    """A line or band drawn on one or more panels."""

    kind: str
    artists: List[Any]
    at: Any = None
    name: str = ""
    default_style: Dict[str, Any] = field(default_factory=dict)  # spans and lines
    center: Optional[str] = None  # spans: id of the line marker at the centre
    center_of: Optional[str] = None  # lines: id of the span the line belongs to


@dataclass
class _Axis:
    """One Matplotlib axes (a panel or a twin) and its state."""

    id: str
    ax: Axes
    panel_id: str
    curves: Dict[str, _Curve] = field(default_factory=dict)
    primary: Optional[str] = None
    select_one: bool = False
    zero_line: Optional[Line2D] = None
    x_spec: Dict[str, Any] = field(default_factory=dict)
    y_spec: Dict[str, Any] = field(default_factory=dict)
    grid_props: Dict[str, Any] = field(default_factory=dict)
    value_grid_props: Dict[str, Any] = field(default_factory=dict)
    grid: Dict[Tuple[str, str], bool] = field(default_factory=dict)  # (direction, which) -> on
    twin_of: Optional[str] = None
    twin_axis: str = ""


class PlotCanvas(FigureCanvasQTAgg):
    """A Qt widget showing panels of curves described by a mapping.

    Panels are addressed by their mosaic id, twins by ``"<panel>.twin"``,
    curves by their id (unique across the figure).

    Signals:
        configChanged (object): The user changed a style, a curve's
            visibility, a grid or a legend through the right-click menu;
            sends ``get_config()``.
        curveStyleChanged (str): A curve's style changed, by the user or by
            code; sends the curve id (used to keep colour swatches current).
        spanStyleChanged (str): A span's style changed, by the user or by
            code; sends the marker id.
    """

    configChanged = Signal(object)
    curveStyleChanged = Signal(str)
    spanStyleChanged = Signal(str)

    def __init__(
            self,
            description: Mapping[str, Any],
            parent: Optional[QWidget] = None,
            *,
            usetex: bool = False,
            context_menu: bool = True,
            scheme: str = "auto",
    ) -> None:
        """Build the figure.

        Args:
            description: Figure description (see the module docstring).
            parent: Parent widget.
            usetex: Render axis labels with the system LaTeX.
            context_menu: Offer the right-click menu for user changes.
            scheme: ``"auto"`` follows the application palette (light or
                dark); ``"light"`` or ``"dark"`` keeps the plot in one of them.

        Raises:
            ValueError: For an unknown key, a panel missing from the mosaic,
                a repeated curve id, an unknown style or primary curve.
        """
        _check_keys(description, frozenset({"layout", "figure", "styles", "axes_style", "panels", "markers"}),
                    "description")
        self._usetex = usetex
        self._styles: Dict[str, Dict[str, Any]] = dict(description.get("styles", {}))
        self._axes_style = _merge(DEFAULT_AXES_STYLE, description.get("axes_style", {}))
        self._axes: Dict[str, _Axis] = {}
        self._curves: Dict[str, _Curve] = {}
        self._legends: Dict[str, Dict[str, Any]] = {}
        self._legend_on: Dict[str, bool] = {}
        self._markers: Dict[str, _Marker] = {}
        self._grid_style: Dict[str, Any] = {}  # user's grid style; overrides the description
        # Light colour and optional own dark colour of every curve and marker colour:
        # ("curve", id), ("face", span id), ("edge", span id), ("line", line marker id)
        self._colors: Dict[Tuple[str, str], List[Optional[str]]] = {}
        if scheme not in _SCHEMES:
            raise ValueError(f"scheme must be one of {', '.join(_SCHEMES)}, got {scheme!r}")
        self._scheme = scheme
        self._dark = False  # what is shown; the description is built light, then switched
        self._scheme_check_pending = False

        fig_spec = dict(description.get("figure", {}))
        margins = fig_spec.pop("margins", None)
        dark_face = fig_spec.pop("dark_facecolor", None)
        figure = Figure(**fig_spec)
        super().__init__(figure)
        self.setParent(parent)
        if margins:
            figure.subplots_adjust(**margins)
        rc = mpl.rcParams
        self._light_frame = {
            "figure": mcolors.to_hex(figure.get_facecolor()), "axes": rc["axes.facecolor"],
            "text": rc["axes.labelcolor"], "tick": rc["xtick.color"],
            "ticklabel": rc["xtick.color"] if rc["xtick.labelcolor"] == "inherit" else rc["xtick.labelcolor"],
            "edge": rc["axes.edgecolor"],
        }
        self._dark_frame = dict(self._axes_style["dark"])
        if dark_face is not None:
            self._dark_frame["figure"] = dark_face

        mosaic_axes = self._make_mosaic(figure, description.get("layout", {}))
        panels = description.get("panels", {})
        for panel_id in panels:
            if panel_id not in mosaic_axes:
                raise ValueError(f"panel {panel_id!r} is not in the layout mosaic")
        for panel_id, ax in mosaic_axes.items():
            self._build_panel(panel_id, ax, panels.get(panel_id, {}))

        for axis in self._axes.values():
            self._refresh_axis(axis)
        for panel_id in self._legends:
            self._update_legend(panel_id)
        for marker_id, marker_spec in description.get("markers", {}).items():
            _check_keys(marker_spec, _MARKER_KEYS, f"marker {marker_id!r}")
            self.add_marker(marker_id, marker_spec.get("kind", "vline"), marker_spec.get("panels", "all"),
                            marker_spec.get("at"), visible=marker_spec.get("visible", True),
                            name=marker_spec.get("name"), **marker_spec.get("props", {}))
        for marker_id, marker_spec in description.get("markers", {}).items():
            if marker_spec.get("center") is not None:
                self.set_span_center(marker_id, marker_spec["center"])

        # What the description gives; get_config reports differences from it
        self._default_styles = {cid: self._style_of(cid) for cid in self._curves}
        self._default_visible = {cid: c.line.get_visible() for cid, c in self._curves.items()}
        if context_menu:
            self.mpl_connect("button_press_event", self._on_press)
        if self._wants_dark():
            self._apply_scheme(True)

    # ----- construction -----
    @staticmethod
    def _make_mosaic(figure: Figure, layout: Mapping[str, Any]) -> Dict[str, Axes]:
        """Create the panels from the layout description."""
        _check_keys(layout, frozenset({"mosaic", "height_ratios", "width_ratios", "hspace", "wspace",
                                       "sharex"}), "layout")
        mosaic = layout.get("mosaic", [["main"]])
        gridspec_kw = {k: layout[k] for k in ("hspace", "wspace") if k in layout}
        sharex = layout.get("sharex", False)
        axes = figure.subplot_mosaic(
            mosaic,
            height_ratios=layout.get("height_ratios"),
            width_ratios=layout.get("width_ratios"),
            gridspec_kw=gridspec_kw or None,
            sharex=sharex is True,
        )
        shared: Sequence[str] = list(axes) if sharex is True else list(sharex or [])
        for panel_id in shared:
            if panel_id not in axes:
                raise ValueError(f"layout.sharex: {panel_id!r} is not in the mosaic")
        if shared:
            first = axes[shared[0]]
            for panel_id in shared[1:]:
                if sharex is not True:
                    axes[panel_id].sharex(first)
            for panel_id in shared:  # x tick labels only on the lowest shared panel of a column
                spec = axes[panel_id].get_subplotspec()
                cols = set(spec.colspan)
                lower = [p for p in shared if p != panel_id
                         and cols & set(axes[p].get_subplotspec().colspan)
                         and axes[p].get_subplotspec().rowspan.start > spec.rowspan.start]
                if lower:
                    axes[panel_id].tick_params(axis="x", which="both", labelbottom=False)
        return axes

    def _build_panel(self, panel_id: str, ax: Axes, spec: Mapping[str, Any]) -> None:
        """Style one panel, add its curves, and its twin if any."""
        _check_keys(spec, _PANEL_KEYS, f"panel {panel_id!r}")
        self._make_axis(panel_id, ax, panel_id, spec)
        if "legend" in spec:
            self._legends[panel_id] = dict(spec["legend"] or {})

        twin_spec = spec.get("twin")
        if twin_spec is not None:
            where = f"panel {panel_id!r} twin"
            _check_keys(twin_spec, _TWIN_KEYS, where)
            direction = twin_spec.get("axis", "x")
            if direction not in ("x", "y"):
                raise ValueError(f"{where}: 'axis' must be 'x' or 'y'")
            twin_ax = ax.twinx() if direction == "x" else ax.twiny()
            twin_ax.set_zorder(ax.get_zorder() + 1)
            twin_ax.patch.set_visible(False)
            twin = self._make_axis(f"{panel_id}.twin", twin_ax, panel_id, twin_spec)
            twin.twin_of, twin.twin_axis = panel_id, direction
            for spine in twin_ax.spines.values():
                spine.set_visible(False)
            if direction == "x":  # the panel keeps the left side, the twin the right
                ax.tick_params(axis="y", which="both", right=False)
                twin_ax.tick_params(axis="y", which="both", left=False, right=True, labelright=True)
                twin_ax.xaxis.set_visible(False)
            else:  # the panel keeps the bottom, the twin the top
                ax.tick_params(axis="x", which="both", top=False)
                twin_ax.tick_params(axis="x", which="both", bottom=False, top=True, labeltop=True)
                twin_ax.yaxis.set_visible(False)

    def _make_axis(self, axis_id: str, ax: Axes, panel_id: str, spec: Mapping[str, Any]) -> _Axis:
        """Register an axes, style it and create its curves."""
        axis = _Axis(
            id=axis_id, ax=ax, panel_id=panel_id,
            select_one=spec.get("select") == "one",
            x_spec=dict(spec.get("x", {})), y_spec=dict(spec.get("y", {})),
            grid_props=dict(self._axes_style["grid"]),
            value_grid_props=_merge(_merge(self._axes_style["grid"], self._axes_style["grid_value"]),
                                    spec.get("grid", {})),
        )
        if spec.get("select") not in (None, "one"):
            raise ValueError(f"{axis_id!r}: 'select' must be \"one\"")
        self._axes[axis_id] = axis
        self._style_axes(ax)
        if spec.get("zero_line", True) and self._axes_style.get("zero_line"):
            axis.zero_line = ax.axhline(0.0, **self._axes_style["zero_line"])

        for curve_id, curve_spec in spec.get("curves", {}).items():
            self._make_curve(axis, curve_id, curve_spec)

        for name, axis_spec in (("x", axis.x_spec), ("y", axis.y_spec)):
            if "scale" in axis_spec:
                getattr(ax, f"set_{name}scale")(axis_spec["scale"])
            if "lim" in axis_spec:
                getattr(ax, f"set_{name}lim")(axis_spec["lim"])
        if axis.x_spec.get("label"):
            self._set_label_text(ax, "x", axis_text(axis.x_spec["label"], axis.x_spec.get("unit", "")))

        primary = spec.get("primary")
        if primary is not None and primary not in axis.curves:
            raise ValueError(f"{axis_id!r}: primary curve {primary!r} is not one of its curves")
        if axis.select_one:
            first = next(iter(axis.curves), None)
            axis.primary = primary or first
            for cid, curve in axis.curves.items():
                curve.line.set_visible(cid == axis.primary)
        else:
            axis.primary = primary
        return axis

    def _make_curve(self, axis: _Axis, curve_id: str, spec: Mapping[str, Any]) -> None:
        """Create one line from its description."""
        where = f"curve {curve_id!r}"
        _check_keys(spec, _CURVE_KEYS, where)
        if curve_id in self._curves:
            raise ValueError(f"{where}: id is used twice")
        style_name = spec.get("style")
        if style_name is not None and style_name not in self._styles:
            known = ", ".join(sorted(self._styles)) or "none"
            raise ValueError(f"{where}: unknown style {style_name!r}; known styles: {known}")
        props = _merge(self._styles.get(style_name, {}), spec.get("props", {}))
        dark_color = props.pop("dark_color", None)
        (line,) = axis.ax.plot([], [], **props)
        self._colors[("curve", curve_id)] = [mcolors.to_hex(line.get_color()),
                                             None if dark_color is None else mcolors.to_hex(dark_color)]
        label = spec.get("label", "")
        curve = _Curve(
            id=curve_id, axis_id=axis.id, line=line,
            label=label, unit=spec.get("unit", ""),
            legend=spec.get("legend", f"${label}$" if label else ""),
            name=spec.get("name", curve_id),
        )
        axis.curves[curve_id] = curve
        self._curves[curve_id] = curve

    def _style_axes(self, ax: Axes) -> None:
        """Apply the shared axis styling to one axes."""
        st = self._axes_style
        ax.tick_params(axis="both", which="major", **st["ticks"], **st["ticks_major"])
        ax.tick_params(axis="both", which="minor", **st["ticks"], **st["ticks_minor"])
        if st["ticks_x"]:
            ax.tick_params(axis="x", which="both", **st["ticks_x"])
        if st["ticks_y"]:
            ax.tick_params(axis="y", which="both", **st["ticks_y"])
        nx, ny = st["minor_locator"]
        if nx:
            ax.xaxis.set_minor_locator(AutoMinorLocator(nx))
        if ny:
            ax.yaxis.set_minor_locator(AutoMinorLocator(ny))
        for name, axis_obj in (("x", ax.xaxis), ("y", ax.yaxis)):
            fmt = ScalarFormatter(useOffset=st[f"{name}_format"] == "sci")
            if st[f"{name}_format"] == "sci":
                fmt.set_scientific(True)
                fmt.set_powerlimits(tuple(st["sci_limits"]))
            else:
                fmt.set_scientific(False)
            axis_obj.set_major_formatter(fmt)
            axis_obj.get_offset_text().set(**st["offset_font"])

    def _set_label_text(self, ax: Axes, which: str, text: str) -> None:
        """Set an axis label with the shared font."""
        setter = ax.set_xlabel if which == "x" else ax.set_ylabel
        pad = self._axes_style["label_pad"][0 if which == "x" else 1]
        extra = {"labelpad": pad} if pad is not None else {}
        setter(text, usetex=self._usetex, **self._axes_style["label_font"], **extra)

    # ----- light and dark mode -----
    def _dark_version(self, color: Any) -> str:
        """The automatic dark-mode version of a colour (for this canvas' dark background)."""
        return dark_variant(color, self._dark_frame["axes"])

    def _shown(self, key: Tuple[str, str]) -> str:
        """The colour drawn now for a curve or marker colour (light, own dark or automatic dark)."""
        light, dark = self._colors[key]
        if not self._dark:
            return light
        return dark if dark is not None else self._dark_version(light)

    def _wants_dark(self) -> bool:
        """Whether the plot should be dark now, from the scheme and the palette."""
        if self._scheme == "auto":  # the application's palette: Matplotlib's canvas widget keeps its own
            return is_dark()
        return self._scheme == "dark"

    def _show_marker_colors(self, marker_id: str) -> None:
        """Give a marker's artists the colours of the current mode (opacities kept)."""
        marker = self._markers[marker_id]
        if marker.kind in _SPAN_KINDS:
            face, edge = self._shown(("face", marker_id)), self._shown(("edge", marker_id))
            for artist in marker.artists:
                artist.set_facecolor(mcolors.to_rgba(face, mcolors.to_rgba(artist.get_facecolor())[3]))
                artist.set_edgecolor(mcolors.to_rgba(edge, mcolors.to_rgba(artist.get_edgecolor())[3]))
        else:
            color = self._shown(("line", marker_id))
            for artist in marker.artists:
                artist.set_color(mcolors.to_rgba(color, mcolors.to_rgba(artist.get_color())[3]))

    def _apply_scheme(self, dark: bool, notify: bool = True) -> None:
        """Draw everything in light or dark colours (does not redraw)."""
        self._dark = dark
        frame = self._dark_frame if dark else self._light_frame
        text = frame["text"]
        tick = frame["edge"] if dark else frame["tick"]
        ticklabel = text if dark else frame["ticklabel"]
        self.figure.set_facecolor(frame["figure"])
        for axis in self._axes.values():
            ax = axis.ax
            if axis.twin_of is None:
                ax.set_facecolor(frame["axes"])
                for spine in ax.spines.values():
                    spine.set_edgecolor(frame["edge"])
            ax.tick_params(axis="both", which="both", color=tick, labelcolor=ticklabel)
            for label_axis in (ax.xaxis, ax.yaxis):
                label_axis.label.set_color(text)
                label_axis.get_offset_text().set_color(ticklabel)
        for cid, curve in self._curves.items():
            curve.line.set_color(self._shown(("curve", cid)))
        for mid in self._markers:
            self._show_marker_colors(mid)
        for axis in self._axes.values():
            self._refresh_axis(axis)
        for panel_id in self._legends:
            self._update_legend(panel_id)
        if notify:  # colour swatches in menus and selectors follow
            for cid in self._curves:
                self.curveStyleChanged.emit(cid)
            for mid in self.span_ids():
                self.spanStyleChanged.emit(mid)

    def set_scheme(self, scheme: str) -> None:
        """Follow the application palette (``"auto"``) or keep the plot ``"light"`` or ``"dark"``.

        Raises:
            ValueError: For any other value.
        """
        if scheme not in _SCHEMES:
            raise ValueError(f"scheme must be one of {', '.join(_SCHEMES)}, got {scheme!r}")
        self._scheme = scheme
        self._check_scheme()

    def scheme(self) -> str:
        """Return the scheme setting: ``"auto"``, ``"light"`` or ``"dark"``."""
        return self._scheme

    def shows_dark(self) -> bool:
        """Return whether the plot is drawn in dark colours now."""
        return self._dark

    def _check_scheme(self) -> None:
        """Switch between light and dark colours if needed, and redraw."""
        self._scheme_check_pending = False
        dark = self._wants_dark()
        if dark != self._dark:
            self._apply_scheme(dark)
            self.redraw()

    def changeEvent(self, event: QEvent) -> None:
        """Follow a palette change (light or dark mode) from the event loop."""
        super().changeEvent(event)
        if event.type() == QEvent.PaletteChange and self._scheme == "auto" and not self._scheme_check_pending:
            self._scheme_check_pending = True
            QTimer.singleShot(0, self, self._check_scheme)

    # ----- keeping an axis consistent with its primary curve -----
    def _primary_color(self, axis: _Axis) -> Optional[str]:
        """Return the colour of the axis' primary curve, if any."""
        curve = axis.curves.get(axis.primary) if axis.primary else None
        return self._shown(("curve", curve.id)) if curve is not None else None

    def _refresh_axis(self, axis: _Axis) -> None:
        """Update y label, zero line and grid after a primary/colour change."""
        ax = axis.ax
        primary = axis.curves.get(axis.primary) if axis.primary else None
        value_dir = "x" if axis.twin_axis == "y" else "y"
        spec = axis.x_spec if value_dir == "x" else axis.y_spec

        if spec.get("label"):
            text = axis_text(spec["label"], spec.get("unit", ""))
        elif primary is not None:
            text = axis_text(primary.label, primary.unit)
        else:
            text = ""
        self._set_label_text(ax, value_dir, text)

        color = self._primary_color(axis)
        if axis.zero_line is not None:
            zero = self._axes_style["zero_line"].get("color", "k")
            axis.zero_line.set_color(color or (self._dark_version(zero) if self._dark else zero))

        if axis.select_one:  # nothing selected: hide this axis' value scale
            has = primary is not None
            side = {"left": has, "labelleft": has} if axis.twin_of is None else {"right": has, "labelright": has}
            if axis.twin_axis == "y":
                side = {"top": has, "labeltop": has}
            ax.tick_params(axis=value_dir, which="both", **side)
            getattr(ax, f"{value_dir}axis").get_offset_text().set_visible(has)
            if axis.zero_line is not None:
                axis.zero_line.set_visible(has)
        self._apply_grid(axis)

    def _apply_grid(self, axis: _Axis) -> None:
        """Draw the remembered grid; value-axis grid lines take the primary colour."""
        value_dir = "x" if axis.twin_axis == "y" else "y"
        color = self._primary_color(axis)
        for direction in ("x", "y"):  # every combination, so that cleared ones are switched off too
            for which in ("major", "minor"):
                self._draw_grid(axis, direction, which, axis.grid.get((direction, which), False),
                                value_dir, color)

    def _draw_grid(self, axis: _Axis, direction: str, which: str, on: bool, value_dir: str,
                   color: Optional[str]) -> None:
        """Show or hide one set of grid lines of an axes."""
        if on and not (axis.select_one and axis.primary is None and direction == value_dir):
            own = axis.value_grid_props if direction == value_dir else axis.grid_props
            rc = mpl.rcParams
            # Pass every property each time: Matplotlib keeps earlier grid settings otherwise
            props = {"linestyle": rc["grid.linestyle"], "linewidth": rc["grid.linewidth"],
                     "alpha": rc["grid.alpha"], "color": rc["grid.color"],
                     **own, **self._grid_style}
            if direction == value_dir and color is not None and "color" not in own:
                props["color"] = color
            axis.ax.grid(True, which=which, axis=direction, **props)
        else:
            axis.ax.grid(False, which=which, axis=direction)

    def _update_legend(self, panel_id: str) -> None:
        """Rebuild a panel's legend from the visible labelled curves of the panel and its twin."""
        if panel_id not in self._legends:
            return
        axes = [a for a in self._axes.values() if a.panel_id == panel_id]
        handles, labels = [], []
        for axis in axes:
            if not axis.ax.get_visible():
                continue
            for curve in axis.curves.values():
                if curve.legend and curve.line.get_visible():
                    handles.append(curve.line)
                    labels.append(curve.legend)
        top = max(axes, key=lambda a: a.ax.get_zorder()).ax
        for axis in axes:
            old = axis.ax.get_legend()
            if old is not None:
                old.remove()
        if handles:
            legend = top.legend(handles, labels, **self._legends[panel_id])
            legend.set_visible(self._legend_on.get(panel_id, True))
            if self._dark:
                legend.get_frame().set_facecolor(self._dark_frame["legend_face"])
                legend.get_frame().set_edgecolor(self._dark_frame["legend_edge"])
                for text in legend.get_texts():
                    text.set_color(self._dark_frame["text"])

    # ----- lookups -----
    def _axis(self, axis_id: str) -> _Axis:
        try:
            return self._axes[axis_id]
        except KeyError:
            raise KeyError(f"no panel or twin {axis_id!r}; known: {', '.join(self._axes)}") from None

    def _curve(self, curve_id: str) -> _Curve:
        try:
            return self._curves[curve_id]
        except KeyError:
            raise KeyError(f"no curve {curve_id!r}") from None

    def axis_ids(self) -> List[str]:
        """Return the ids of all panels and twins."""
        return list(self._axes)

    def curve_ids(self, axis_id: Optional[str] = None) -> List[str]:
        """Return the curve ids of the figure, or of one panel or twin."""
        if axis_id is None:
            return list(self._curves)
        return list(self._axis(axis_id).curves)

    def axes(self, axis_id: str) -> Axes:
        """Return the Matplotlib axes of a panel or twin, for anything not covered here."""
        return self._axis(axis_id).ax

    def line(self, curve_id: str) -> Line2D:
        """Return the Matplotlib line of a curve."""
        return self._curve(curve_id).line

    # ----- data and visibility -----
    def set_curve_data(self, curve_id: str, x: Iterable[float], y: Iterable[float]) -> None:
        """Replace a curve's data (call ``redraw`` afterwards)."""
        self._curve(curve_id).line.set_data(x, y)

    def clear_curve(self, curve_id: str) -> None:
        """Remove a curve's data."""
        self._curve(curve_id).line.set_data([], [])

    def set_curve_visible(self, curve_id: str, visible: bool) -> None:
        """Show or hide one curve. On a ``select: one`` axis use ``select_curve``."""
        curve = self._curve(curve_id)
        curve.line.set_visible(bool(visible))
        self._update_legend(self._axes[curve.axis_id].panel_id)

    def is_curve_visible(self, curve_id: str) -> bool:
        """Return whether a curve is shown."""
        return self._curve(curve_id).line.get_visible()

    def select_curve(self, axis_id: str, curve_id: Optional[str]) -> None:
        """Show one curve of a ``select: one`` axis and hide the others.

        ``None`` shows none and hides the axis' value scale.
        """
        axis = self._axis(axis_id)
        if curve_id is not None and curve_id not in axis.curves:
            raise KeyError(f"{axis_id!r} has no curve {curve_id!r}")
        for cid, curve in axis.curves.items():
            curve.line.set_visible(cid == curve_id)
        axis.primary = curve_id
        self._refresh_axis(axis)
        self._update_legend(axis.panel_id)

    def selected_curve(self, axis_id: str) -> Optional[str]:
        """Return the shown curve of a ``select: one`` axis (or its primary curve)."""
        return self._axis(axis_id).primary

    def set_axis_visible(self, axis_id: str, visible: bool) -> None:
        """Show or hide a whole panel or twin with its curves."""
        axis = self._axis(axis_id)
        axis.ax.set_visible(bool(visible))
        self._update_legend(axis.panel_id)

    def is_axis_visible(self, axis_id: str) -> bool:
        """Return whether a panel or twin is shown."""
        return self._axis(axis_id).ax.get_visible()

    # ----- style -----
    def set_curve_style(self, curve_id: str, **props: Any) -> None:
        """Change line properties of a curve, e.g. ``color="r", linewidth=2``.

        ``color`` is the light-mode colour; ``dark_color`` is the curve's own
        dark-mode colour (``None``: automatic, see ``dark_variant``).
        """
        curve = self._curve(curve_id)
        entry = self._colors[("curve", curve_id)]
        if "color" in props:
            entry[0] = mcolors.to_hex(props.pop("color"))
        if "dark_color" in props:
            dark = props.pop("dark_color")
            entry[1] = None if dark is None else mcolors.to_hex(dark)
        curve.line.set(**props)
        curve.line.set_color(self._shown(("curve", curve_id)))
        axis = self._axes[curve.axis_id]
        if axis.primary == curve_id:
            self._refresh_axis(axis)
        self._update_legend(axis.panel_id)
        self.curveStyleChanged.emit(curve_id)

    def get_curve_style(self, curve_id: str) -> Dict[str, Any]:
        """Return a curve's colour, line style and width, marker and marker size.

        ``color`` is the light-mode colour and ``dark_color`` the curve's own
        dark-mode colour, or ``None`` when it is automatic; ``curve_color``
        returns the colour shown now.
        """
        return self._style_of(curve_id)

    def curve_color(self, curve_id: str) -> str:
        """Return the colour a curve is drawn with now (light or dark mode)."""
        self._curve(curve_id)
        return self._shown(("curve", curve_id))

    def _style_of(self, curve_id: str) -> Dict[str, Any]:
        """The style as ``get_curve_style`` returns it; used internally so that
        subclasses may extend ``get_curve_style`` without affecting the canvas."""
        line = self._curve(curve_id).line
        light, dark = self._colors[("curve", curve_id)]
        return {
            "color": light,
            "dark_color": dark,
            "linestyle": line.get_linestyle(),
            "linewidth": float(line.get_linewidth()),
            "marker": line.get_marker(),
            "markersize": float(line.get_markersize()),
        }

    def default_curve_style(self, curve_id: str) -> Dict[str, Any]:
        """Return a curve's style as given by the description (``get_curve_style`` format)."""
        self._curve(curve_id)
        return dict(self._default_styles[curve_id])

    def style_axes(self, ax: Axes, zero_line: bool = True) -> Optional[Line2D]:
        """Apply the canvas' axis styling to any axes, e.g. in a separate export figure.

        Args:
            ax: Matplotlib axes, from any figure.
            zero_line: Also draw the zero line.

        Returns:
            The zero line, or ``None``.
        """
        self._style_axes(ax)
        if zero_line and self._axes_style.get("zero_line"):
            return ax.axhline(0.0, **self._axes_style["zero_line"])
        return None

    def get_curve_name(self, curve_id: str) -> str:
        """Return a curve's plain-text name (for menus and selectors)."""
        return self._curve(curve_id).name

    def get_curve_label(self, curve_id: str) -> Tuple[str, str]:
        """Return a curve's ``(label, unit)`` math text."""
        curve = self._curve(curve_id)
        return curve.label, curve.unit

    # ----- axes -----
    def set_limits(self, axis_id: str, x: Optional[Tuple[float, float]] = None,
                   y: Optional[Tuple[float, float]] = None) -> None:
        """Set the x and/or y limits of a panel or twin."""
        ax = self._axis(axis_id).ax
        if x is not None:
            ax.set_xlim(x)
        if y is not None:
            ax.set_ylim(y)

    def get_limits(self, axis_id: str) -> Tuple[Tuple[float, float], Tuple[float, float]]:
        """Return ``(xlim, ylim)`` of a panel or twin."""
        ax = self._axis(axis_id).ax
        return tuple(ax.get_xlim()), tuple(ax.get_ylim())

    def set_label(self, axis_id: str, which: str, label: str, unit: str = "") -> None:
        """Set the ``"x"`` or ``"y"`` label of a panel or twin (math text, without ``$``).

        A y label set here replaces the one taken from the primary curve; an
        empty label gives that back.
        """
        if which not in ("x", "y"):
            raise ValueError("which must be 'x' or 'y'")
        axis = self._axis(axis_id)
        spec = axis.x_spec if which == "x" else axis.y_spec
        spec["label"], spec["unit"] = label, unit
        if which == "x" and axis.twin_axis != "y":
            self._set_label_text(axis.ax, "x", axis_text(label, unit))
        else:
            self._refresh_axis(axis)

    def set_grid(self, axis_id: str, visible: bool, which: str = "major", direction: str = "y") -> None:
        """Show or hide grid lines of a panel or twin.

        Args:
            axis_id: Panel or twin id.
            visible: Whether to show them.
            which: ``"major"`` or ``"minor"``.
            direction: ``"x"`` (vertical lines) or ``"y"`` (horizontal lines).
        """
        if which not in ("major", "minor") or direction not in ("x", "y"):
            raise ValueError("which must be 'major'/'minor' and direction 'x'/'y'")
        axis = self._axis(axis_id)
        axis.grid[(direction, which)] = bool(visible)
        self._apply_grid(axis)

    def set_legend_visible(self, panel_id: str, visible: bool) -> None:
        """Show or hide a panel's legend (only panels with a ``legend`` entry)."""
        panel = self._axis(panel_id).panel_id
        self._legend_on[panel] = bool(visible)
        self._update_legend(panel)

    def is_legend_visible(self, panel_id: str) -> bool:
        """Return whether a panel's legend is shown."""
        panel = self._axis(panel_id).panel_id
        return panel in self._legends and self._legend_on.get(panel, True)

    # ----- markers -----
    def add_marker(self, marker_id: str, kind: str, panels: Any = "all", at: Any = None,
                   *, visible: bool = True, name: Optional[str] = None, **props: Any) -> None:
        """Draw a line or band on panels.

        Args:
            marker_id: Id used to move or hide it later.
            kind: ``"vline"``, ``"hline"`` (a line at ``at``) or ``"vspan"``,
                ``"hspan"`` (a band from ``at[0]`` to ``at[1]``).
            panels: ``"all"`` (every panel, not the twins) or a list of
                panel or twin ids.
            at: Position; defaults to 0 for lines and (0, 1) for bands.
            visible: Whether it is shown at first.
            name: Plain text for menus (default: the id).
            **props: Matplotlib properties (``color``, ``alpha``, ...), and
                the dark-mode colours: ``dark_color`` (a line, or both parts
                of a span), ``dark_facecolor``, ``dark_edgecolor`` (a span).

        Raises:
            ValueError: For a repeated id or an unknown kind.
        """
        if marker_id in self._markers:
            raise ValueError(f"marker {marker_id!r} already exists")
        if kind not in _MARKER_KINDS:
            raise ValueError(f"marker {marker_id!r}: kind must be one of {', '.join(_MARKER_KINDS)}")
        ids = [a for a, axis in self._axes.items() if axis.twin_of is None] if panels == "all" else list(panels)
        dark_color = props.pop("dark_color", None)
        dark_face = props.pop("dark_facecolor", dark_color)
        dark_edge = props.pop("dark_edgecolor", dark_color)
        if at is None:
            at = (0.0, 1.0) if kind.endswith("span") else 0.0
        artists = []
        for axis_id in ids:
            ax = self._axis(axis_id).ax
            if kind == "vline":
                artists.append(ax.axvline(at, **props))
            elif kind == "hline":
                artists.append(ax.axhline(at, **props))
            elif kind == "vspan":
                artists.append(ax.axvspan(at[0], at[1], **props))
            else:
                artists.append(ax.axhspan(at[0], at[1], **props))
        marker = _Marker(kind=kind, artists=artists, at=at, name=name or marker_id)

        def own(color: Any) -> Optional[str]:
            return None if color is None else mcolors.to_hex(color)

        if kind in _SPAN_KINDS:
            probe = artists[0] if artists else self.figure.axes[0].axvspan(0, 1, **props)
            marker.default_style = _span_style_of(probe)
            if not artists:
                probe.remove()
            self._colors[("face", marker_id)] = [marker.default_style["facecolor"], own(dark_face)]
            self._colors[("edge", marker_id)] = [marker.default_style["edgecolor"], own(dark_edge)]
            marker.default_style.update(dark_facecolor=own(dark_face), dark_edgecolor=own(dark_edge))
        else:
            probe = artists[0] if artists else self.figure.axes[0].axvline(0, **props)
            marker.default_style = _line_style_of(probe)
            if not artists:
                probe.remove()
            self._colors[("line", marker_id)] = [marker.default_style["center_color"], own(dark_color)]
            marker.default_style["dark_center_color"] = own(dark_color)
        self._markers[marker_id] = marker
        self.set_marker_visible(marker_id, visible)
        if self._dark:
            self._show_marker_colors(marker_id)

    def _marker(self, marker_id: str) -> _Marker:
        try:
            return self._markers[marker_id]
        except KeyError:
            raise KeyError(f"no marker {marker_id!r}") from None

    def set_marker(self, marker_id: str, at: Any) -> None:
        """Move a marker: a position for a line, ``(lo, hi)`` for a band."""
        marker = self._marker(marker_id)
        marker.at = at
        for artist in marker.artists:
            if marker.kind == "vline":
                artist.set_xdata([at, at])
            elif marker.kind == "hline":
                artist.set_ydata([at, at])
            else:
                lo, hi = at
                if hasattr(artist, "set_width"):  # Rectangle (Matplotlib >= 3.9)
                    if marker.kind == "vspan":
                        artist.set_x(lo)
                        artist.set_width(hi - lo)
                    else:
                        artist.set_y(lo)
                        artist.set_height(hi - lo)
                elif marker.kind == "vspan":  # Polygon (older Matplotlib)
                    artist.set_xy([[lo, 0], [lo, 1], [hi, 1], [hi, 0], [lo, 0]])
                else:
                    artist.set_xy([[0, lo], [0, hi], [1, hi], [1, lo], [0, lo]])

    def get_marker(self, marker_id: str) -> Any:
        """Return a marker's position (``at``)."""
        return self._marker(marker_id).at

    def set_marker_visible(self, marker_id: str, visible: bool) -> None:
        """Show or hide a marker on all its panels."""
        for artist in self._marker(marker_id).artists:
            artist.set_visible(bool(visible))

    def is_marker_visible(self, marker_id: str) -> bool:
        """Return whether a marker is shown."""
        artists = self._marker(marker_id).artists
        return bool(artists) and artists[0].get_visible()

    def remove_marker(self, marker_id: str) -> None:
        """Delete a marker (and its link to a span or centre line)."""
        marker = self._marker(marker_id)
        for artist in marker.artists:
            artist.remove()
        for part in ("face", "edge", "line"):
            self._colors.pop((part, marker_id), None)
        if marker.center is not None and marker.center in self._markers:
            self._markers[marker.center].center_of = None
        if marker.center_of is not None and marker.center_of in self._markers:
            self._markers[marker.center_of].center = None
        del self._markers[marker_id]

    def marker_ids(self) -> List[str]:
        """Return the ids of all markers."""
        return list(self._markers)

    def span_ids(self) -> List[str]:
        """Return the ids of the span markers (``vspan``, ``hspan``)."""
        return [mid for mid, m in self._markers.items() if m.kind in _SPAN_KINDS]

    def get_marker_name(self, marker_id: str) -> str:
        """Return a marker's plain-text name (for menus)."""
        return self._marker(marker_id).name

    def _span(self, marker_id: str) -> _Marker:
        marker = self._marker(marker_id)
        if marker.kind not in _SPAN_KINDS:
            raise ValueError(f"marker {marker_id!r} is a {marker.kind}, not a span")
        return marker

    def set_span_center(self, span_id: str, line_id: Optional[str]) -> None:
        """Make a line marker the centre line of a span (``None`` unlinks it).

        The line's style is then part of the span's style (``center_*`` keys).
        Moving and showing the line stay separate (``set_marker``,
        ``set_marker_visible``).

        Raises:
            KeyError: For an unknown marker.
            ValueError: If ``span_id`` is not a span, ``line_id`` not a line,
                or the line already belongs to another span.
        """
        span = self._span(span_id)
        if span.center is not None and span.center in self._markers:
            self._markers[span.center].center_of = None
        span.center = None
        if line_id is None:
            return
        line = self._marker(line_id)
        if line.kind in _SPAN_KINDS:
            raise ValueError(f"marker {line_id!r} is a span, not a line")
        if line.center_of not in (None, span_id):
            raise ValueError(f"line {line_id!r} already belongs to span {line.center_of!r}")
        span.center, line.center_of = line_id, span_id

    def get_span_style(self, marker_id: str) -> Dict[str, Any]:
        """Return a span's style.

        Keys: ``facecolor`` and ``alpha`` (fill colour and opacity),
        ``edgecolor`` and ``edge_alpha`` (edge colour and opacity),
        ``linewidth`` and ``linestyle`` (edge line; ``"None"`` for no edge);
        with a centre line also ``center_color``, ``center_alpha``,
        ``center_linewidth`` and ``center_linestyle``. Colours are the
        light-mode ones; ``dark_facecolor``, ``dark_edgecolor`` and
        ``dark_center_color`` are the span's own dark-mode colours, or
        ``None`` when automatic.
        """
        marker = self._span(marker_id)
        style = _span_style_of(marker.artists[0]) if marker.artists else {
            k: marker.default_style[k] for k in _SPAN_STYLE_KEYS}
        style["facecolor"], style["dark_facecolor"] = self._colors[("face", marker_id)]
        style["edgecolor"], style["dark_edgecolor"] = self._colors[("edge", marker_id)]
        if marker.center is not None:
            line = self._markers[marker.center]
            style.update(_line_style_of(line.artists[0]) if line.artists else line.default_style)
            style["center_color"], style["dark_center_color"] = self._colors[("line", marker.center)]
        return style

    def default_span_style(self, marker_id: str) -> Dict[str, Any]:
        """Return a span's style as given by the description (``get_span_style`` format)."""
        marker = self._span(marker_id)
        style = dict(marker.default_style)
        if marker.center is not None:
            style.update(self._markers[marker.center].default_style)
        return style

    def set_span_style(self, marker_id: str, **props: Any) -> None:
        """Change the style of a span on all its panels.

        Args:
            marker_id: Id of a ``vspan`` or ``hspan`` marker.
            **props: Any key of ``get_span_style``; keys not given keep
                their value. ``center_*`` keys need a centre line.

        Raises:
            KeyError: For an unknown marker.
            ValueError: For a marker that is not a span, or an unknown key.
        """
        marker = self._span(marker_id)
        allowed = _SPAN_STYLE_KEYS + (_CENTER_STYLE_KEYS if marker.center is not None else ())
        unknown = set(props) - set(allowed)
        if unknown:
            raise ValueError(f"span style: unknown key(s) {sorted(unknown)}; "
                             f"allowed: {', '.join(allowed)}")
        style = {**self.get_span_style(marker_id), **props}

        def own(color: Any) -> Optional[str]:
            return None if color is None else mcolors.to_hex(color)

        self._colors[("face", marker_id)] = [mcolors.to_hex(style["facecolor"]), own(style["dark_facecolor"])]
        self._colors[("edge", marker_id)] = [mcolors.to_hex(style["edgecolor"]), own(style["dark_edgecolor"])]
        if marker.center is not None:
            self._colors[("line", marker.center)] = [mcolors.to_hex(style["center_color"]),
                                                     own(style["dark_center_color"])]
        if any(k in props for k in _SPAN_STYLE_KEYS):
            face = mcolors.to_rgba(self._shown(("face", marker_id)), float(style["alpha"]))
            edge = mcolors.to_rgba(self._shown(("edge", marker_id)), float(style["edge_alpha"]))
            for artist in marker.artists:
                artist.set_alpha(None)  # the opacities live in the two colours
                artist.set_facecolor(face)
                artist.set_edgecolor(edge)
                artist.set_linewidth(float(style["linewidth"]))
                artist.set_linestyle(style["linestyle"])
        if any(k in props for k in _CENTER_STYLE_KEYS):
            for artist in self._markers[marker.center].artists:
                artist.set_color(self._shown(("line", marker.center)))
                artist.set_alpha(float(style["center_alpha"]))
                artist.set_linewidth(float(style["center_linewidth"]))
                artist.set_linestyle(style["center_linestyle"])
        self.spanStyleChanged.emit(marker_id)

    def default_grid_style(self) -> Dict[str, Any]:
        """Return the grid line style from the description (horizontal lines of a panel)."""
        value = _merge(self._axes_style["grid"], self._axes_style["grid_value"])
        return {
            "linestyle": value.get("linestyle", value.get("ls", "-")),
            "linewidth": float(value.get("linewidth", value.get("lw", mpl.rcParams["grid.linewidth"]))),
            "alpha": float(value.get("alpha", 1.0)),
        }

    def get_grid_style(self) -> Dict[str, Any]:
        """Return the grid line style in use (``linestyle``, ``linewidth``, ``alpha``)."""
        return {**self.default_grid_style(), **self._grid_style}

    def set_grid_style(self, **props: Any) -> None:
        """Set the style of all grid lines: ``linestyle``, ``linewidth``, ``alpha``.

        Colours stay automatic. Values equal to the description's are dropped,
        so ``get_config`` only reports real changes. No arguments resets it.
        """
        unknown = set(props) - set(_GRID_STYLE_KEYS)
        if unknown:
            raise ValueError(f"grid style: unknown key(s) {sorted(unknown)}; allowed: {', '.join(_GRID_STYLE_KEYS)}")
        default = self.default_grid_style()
        self._grid_style = {k: v for k, v in props.items() if v != default[k]}
        for axis in self._axes.values():
            self._apply_grid(axis)

    # ----- user configuration -----
    def get_config(self) -> Dict[str, Any]:
        """Return what differs from the description, as plain JSON data.

        Contains curve styles, the visibility of curves that are not on a
        ``select: one`` axis, grids, legend visibility, the grid style and
        span styles::

            {"curves": {"flux": {"color": "#d62728", "linewidth": 2.0},
                        "fit": {"visible": False}},
             "axes": {"flux": {"y_major": True}, "spectrum": {"legend": False}},
             "grid_style": {"linestyle": ":", "alpha": 0.5},
             "markers": {"window": {"facecolor": "#2ca02c", "alpha": 0.2}}}
        """
        curves: Dict[str, Dict[str, Any]] = {}
        for cid, curve in self._curves.items():
            style = self._style_of(cid)
            diff = {k: v for k, v in style.items() if v != self._default_styles[cid][k]}
            if not self._axes[curve.axis_id].select_one and curve.line.get_visible() != self._default_visible[cid]:
                diff["visible"] = curve.line.get_visible()
            if diff:
                curves[cid] = diff
        axes: Dict[str, Dict[str, Any]] = {}
        for axis_id, axis in self._axes.items():
            diff = {_GRID_KEYS[key]: True for key, on in axis.grid.items() if on}
            if axis_id in self._legends and not self._legend_on.get(axis_id, True):
                diff["legend"] = False
            if diff:
                axes[axis_id] = diff
        out: Dict[str, Any] = {}
        if curves:
            out["curves"] = curves
        if axes:
            out["axes"] = axes
        if self._grid_style:
            out["grid_style"] = dict(self._grid_style)
        markers: Dict[str, Dict[str, Any]] = {}
        for mid in self.span_ids():
            default = self.default_span_style(mid)
            diff = {k: v for k, v in self.get_span_style(mid).items() if v != default.get(k)}
            if diff:
                markers[mid] = diff
        if markers:
            out["markers"] = markers
        return out

    def set_config(self, config: Mapping[str, Any]) -> None:
        """Apply a configuration from ``get_config`` (no ``configChanged``).

        Everything not in ``config`` returns to the description's state;
        unknown curves, axes and keys are ignored, so an old file still loads.
        """
        self.reset_config()
        for cid, diff in dict(config.get("curves", {})).items():
            if cid not in self._curves:
                continue
            style = {k: v for k, v in diff.items() if k in _STYLE_KEYS}
            if style:
                self.set_curve_style(cid, **style)
            if "visible" in diff and not self._axes[self._curves[cid].axis_id].select_one:
                self.set_curve_visible(cid, bool(diff["visible"]))
        grid_style = {k: v for k, v in dict(config.get("grid_style", {})).items() if k in _GRID_STYLE_KEYS}
        if grid_style:
            self.set_grid_style(**grid_style)
        spans = set(self.span_ids())
        for mid, diff in dict(config.get("markers", {})).items():
            if mid not in spans:
                continue
            keys = _SPAN_STYLE_KEYS + (_CENTER_STYLE_KEYS if self._markers[mid].center else ())
            style = {k: v for k, v in dict(diff).items() if k in keys}
            if style:
                self.set_span_style(mid, **style)
        reverse = {v: k for k, v in _GRID_KEYS.items()}
        for axis_id, diff in dict(config.get("axes", {})).items():
            if axis_id not in self._axes:
                continue
            for key, on in diff.items():
                if key in reverse:
                    direction, which = reverse[key]
                    self.set_grid(axis_id, bool(on), which, direction)
                elif key == "legend" and axis_id in self._legends:
                    self.set_legend_visible(axis_id, bool(on))

    def reset_config(self) -> None:
        """Return styles, visibility, grids and legends to the description (no signal)."""
        for cid, curve in self._curves.items():
            self.set_curve_style(cid, **self._default_styles[cid])
            if not self._axes[curve.axis_id].select_one:
                self.set_curve_visible(cid, self._default_visible[cid])
        self._grid_style = {}
        for axis_id, axis in self._axes.items():
            axis.grid.clear()
            self._apply_grid(axis)
        for panel_id in self._legends:
            self.set_legend_visible(panel_id, True)
        for mid in self.span_ids():
            self._reset_span(mid)

    def _reset_span(self, marker_id: str) -> None:
        """Give a span its style from the description, only if it was changed
        (so an untouched span keeps exactly the description's artists' state)."""
        current, default = self.get_span_style(marker_id), self.default_span_style(marker_id)
        changed = {k: v for k, v in default.items() if current.get(k) != v}
        if changed:  # setting only these keeps the rest exactly as built
            self.set_span_style(marker_id, **{
                **({k: default[k] for k in _SPAN_STYLE_KEYS} if set(changed) & set(_SPAN_STYLE_KEYS) else {}),
                **({k: default[k] for k in _CENTER_STYLE_KEYS} if set(changed) & set(_CENTER_STYLE_KEYS) else {}),
            })

    # ----- right-click menu -----
    def _on_press(self, event: Any) -> None:
        """Open the menu on a right click inside a panel."""
        if event.button != 3 or event.inaxes is None:
            return
        hit = next((a for a in self._axes.values() if a.ax is event.inaxes), None)
        if hit is None:
            return
        panel_id = hit.panel_id
        group = [a for a in self._axes.values() if a.panel_id == panel_id]
        under = next((c for a in group if a.ax.get_visible() for c in a.curves.values()
                      if c.line.get_visible() and c.line.contains(event)[0]), None)
        self._show_menu(panel_id, group, under)

    def _user_changed(self) -> None:
        """Redraw and report a change made through the menu."""
        self.redraw()
        self.configChanged.emit(self.get_config())

    def _edit_style(self, curve_id: str) -> None:
        """Open the style dialog for a curve."""
        curve = self._curves[curve_id]
        before = self._style_of(curve_id)

        def preview(style: Dict[str, Any]) -> None:
            self.set_curve_style(curve_id, **style)
            self.redraw()

        dialog = CurveStyleDialog(curve.name, before, self._default_styles[curve_id], self,
                                  preview=preview, auto_dark=self._dark_version)
        if dialog.exec() == QDialog.Accepted:
            self.set_curve_style(curve_id, **dialog.style())
            self._user_changed()
        else:
            self.set_curve_style(curve_id, **before)
            self.redraw()

    def _edit_grid_style(self) -> None:
        """Open the grid style dialog (applies to all panels)."""
        before = dict(self._grid_style)

        def preview(style: Dict[str, Any]) -> None:
            self.set_grid_style(**style)
            self.redraw()

        dialog = GridStyleDialog(self.get_grid_style(), self.default_grid_style(), self, preview=preview)
        if dialog.exec() == QDialog.Accepted:
            self.set_grid_style(**dialog.style())
            self._user_changed()
        else:
            self.set_grid_style(**before)
            self.redraw()

    def _edit_span_style(self, marker_id: str) -> None:
        """Open the style dialog for a span, with a live preview; Cancel restores the old style."""
        before = self.get_span_style(marker_id)

        def preview(style: Dict[str, Any]) -> None:
            self.set_span_style(marker_id, **style)
            self.redraw()

        dialog = SpanStyleDialog(self._markers[marker_id].name, before,
                                 self.default_span_style(marker_id), self, preview=preview,
                                 auto_dark=self._dark_version)
        if dialog.exec() == QDialog.Accepted:
            self.set_span_style(marker_id, **dialog.style())
            self._user_changed()
        else:
            self.set_span_style(marker_id, **before)
            self.redraw()

    def _show_menu(self, panel_id: str, group: List[_Axis], under: Optional[_Curve]) -> None:
        """Show the right-click menu of a panel at the mouse."""
        self._build_menu(panel_id, group, under).exec(QCursor.pos())

    def _build_menu(self, panel_id: str, group: List[_Axis], under: Optional[_Curve]) -> QMenu:
        """Build the right-click menu of a panel."""
        menu = QMenu(self)

        def action(text: str, slot, checked: Optional[bool] = None, parent: QMenu = menu) -> QAction:
            act = QAction(text, parent)
            if checked is not None:
                act.setCheckable(True)
                act.setChecked(checked)
            act.triggered.connect(slot)
            parent.addAction(act)
            return act

        if under is not None:
            act = action(f"Style of {under.name}…", lambda: self._edit_style(under.id))
            act.setIcon(color_icon(self.curve_color(under.id)))
            act.setIconVisibleInMenu(True)  # macOS hides menu icons unless asked
            menu.addSeparator()

        for axis in group:
            if not axis.curves:
                continue
            sub = menu.addMenu("Curves (right axis)" if axis.twin_of and len(group) > 1 else "Curves")
            for cid, curve in axis.curves.items():
                item = sub.addMenu(color_icon(self.curve_color(cid)), curve.name)
                item.menuAction().setIconVisibleInMenu(True)  # macOS hides menu icons unless asked
                action("Style…", lambda _=False, c=cid: self._edit_style(c), parent=item)
                if not axis.select_one:
                    def toggle(on: bool, c: str = cid) -> None:
                        self.set_curve_visible(c, on)
                        self._user_changed()
                    action("Visible", toggle, curve.line.get_visible(), parent=item)

        grid_menu = menu.addMenu("Grid")
        for axis in group:
            if not axis.ax.get_visible():
                continue
            prefix = "Right axis: " if axis.twin_of and axis.twin_axis == "x" else (
                "Top axis: " if axis.twin_of else "")
            directions = ("y", "x") if axis.twin_of is None else (("y",) if axis.twin_axis == "x" else ("x",))
            for direction in directions:
                for which in ("major", "minor"):
                    text = f"{prefix}{'Horizontal' if direction == 'y' else 'Vertical'} {which}"

                    def toggle_grid(on: bool, a: str = axis.id, d: str = direction, w: str = which) -> None:
                        self.set_grid(a, on, w, d)
                        self._user_changed()
                    action(text, toggle_grid, axis.grid.get((direction, which), False), parent=grid_menu)

        grid_menu.addSeparator()
        action("Grid style…", self._edit_grid_style, parent=grid_menu)

        group_axes = [a.ax for a in group]
        panel_spans = [mid for mid in self.span_ids()
                       if any(artist.axes in group_axes for artist in self._markers[mid].artists)]
        if len(panel_spans) == 1:
            mid = panel_spans[0]
            act = action(f"{self._markers[mid].name} style…", lambda: self._edit_span_style(mid))
            act.setIcon(color_icon(self._shown(("face", mid))))
            act.setIconVisibleInMenu(True)
        elif panel_spans:
            span_menu = menu.addMenu("Span style")
            for mid in panel_spans:
                act = action(f"{self._markers[mid].name}…",
                             lambda _=False, m=mid: self._edit_span_style(m), parent=span_menu)
                act.setIcon(color_icon(self._shown(("face", mid))))
                act.setIconVisibleInMenu(True)

        if panel_id in self._legends:
            def toggle_legend(on: bool) -> None:
                self.set_legend_visible(panel_id, on)
                self._user_changed()
            action("Legend", toggle_legend, self.is_legend_visible(panel_id))

        menu.addSeparator()

        def reset_panel() -> None:
            for axis in group:
                for cid in axis.curves:
                    self.set_curve_style(cid, **self._default_styles[cid])
                    if not axis.select_one:
                        self.set_curve_visible(cid, self._default_visible[cid])
                axis.grid.clear()
                self._apply_grid(axis)
            if panel_id in self._legends:
                self.set_legend_visible(panel_id, True)
            for mid in panel_spans:
                self._reset_span(mid)
            self._user_changed()
        action("Reset this panel", reset_panel)
        return menu

    def export(self, path: str, *, dpi: Optional[float] = None, pad_inches: float = 0.1,
               scheme: str = "light", **kwargs: Any) -> None:
        """Save the figure to a file; the format follows the extension (pdf, png, svg, ...).

        Args:
            path: Output file.
            dpi: Resolution for bitmap formats (default: the figure's).
            pad_inches: Margin around the tight bounding box.
            scheme: ``"light"`` (default; for papers and printing), ``"dark"``,
                or ``"current"`` for the colours shown on screen.
            **kwargs: Further ``Figure.savefig`` arguments.

        Raises:
            ValueError: For an unknown ``scheme``.
        """
        if scheme not in ("light", "dark", "current"):
            raise ValueError(f"scheme must be 'light', 'dark' or 'current', got {scheme!r}")
        dark = self._dark if scheme == "current" else scheme == "dark"
        shown = self._dark
        if dark != shown:
            self._apply_scheme(dark, notify=False)
        try:
            kwargs.setdefault("bbox_inches", "tight")
            kwargs.setdefault("facecolor", self.figure.get_facecolor())
            self.figure.savefig(path, dpi=dpi or self.figure.dpi, pad_inches=pad_inches, **kwargs)
        finally:
            if dark != shown:
                self._apply_scheme(shown, notify=False)
                self.redraw()

    def redraw(self) -> None:
        """Schedule a redraw (cheap to call often)."""
        self.draw_idle()
