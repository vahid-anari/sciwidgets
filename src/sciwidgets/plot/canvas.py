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
    ``facecolor``, ...) and ``margins`` (``left``, ``right``, ``bottom``,
    ``top`` as for ``subplots_adjust``).
``styles``
    Named line styles (Matplotlib ``Line2D`` properties).
``axes_style``
    Overrides of the shared axis styling (see ``DEFAULT_AXES_STYLE``).
``panels``
    One entry per panel id of the mosaic:

    * ``curves``: ``{id: {"label", "unit", "legend", "style", "props"}}``.
      ``label`` and ``unit`` are math text (without ``$``) used for the axis
      label; ``legend`` is the legend text (default: the label); ``props``
      overrides single properties of the style.
    * ``x``, ``y``: ``{"label", "unit", "scale", "lim"}`` for the axis.
    * ``primary``: the curve whose colour the zero line and the y grid take
      and whose label/unit name the y axis, unless ``y`` has a label.
    * ``select``: ``"one"`` shows one curve at a time (see ``select_curve``);
      the shown curve is then the primary one.
    * ``zero_line``: draw a horizontal line at y = 0 (default true).
    * ``legend``: Matplotlib legend arguments; without it, no legend.
    * ``grid``: line properties of this panel's grid lines.
    * ``twin``: a second axis sharing the panel: ``{"axis": "x"}`` (default)
      adds a y axis on the right, ``{"axis": "y"}`` an x axis on top. It
      takes ``curves``, ``x``/``y``, ``primary``, ``select``, ``zero_line``
      and ``grid`` like a panel, and is addressed as ``"<panel>.twin"``.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import matplotlib.colors as mcolors
from matplotlib.axes import Axes
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.ticker import AutoMinorLocator, ScalarFormatter
from PySide6.QtWidgets import QWidget

__all__ = ["DEFAULT_AXES_STYLE", "PlotCanvas", "axis_text"]

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
    "grid": {"alpha": 0.3},
}
"""Shared axis styling; a description's ``axes_style`` overrides single keys.

``minor_locator`` is the number of minor intervals per major one, for x and
y; ``x_format``/``y_format`` are ``"plain"`` or ``"sci"`` (scientific with
an offset text when outside ``sci_limits``).
"""

_PANEL_KEYS = frozenset({"curves", "x", "y", "primary", "select", "zero_line", "legend", "grid", "twin"})
_TWIN_KEYS = frozenset({"axis", "curves", "x", "y", "primary", "select", "zero_line", "grid"})
_CURVE_KEYS = frozenset({"label", "unit", "legend", "style", "props"})


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
    grid: Dict[Tuple[str, str], bool] = field(default_factory=dict)  # (direction, which) -> on
    twin_of: Optional[str] = None
    twin_axis: str = ""


class PlotCanvas(FigureCanvasQTAgg):
    """A Qt widget showing panels of curves described by a mapping.

    Panels are addressed by their mosaic id, twins by ``"<panel>.twin"``,
    curves by their id (unique across the figure).
    """

    def __init__(
            self,
            description: Mapping[str, Any],
            parent: Optional[QWidget] = None,
            *,
            usetex: bool = False,
    ) -> None:
        """Build the figure.

        Args:
            description: Figure description (see the module docstring).
            parent: Parent widget.
            usetex: Render axis labels with the system LaTeX.

        Raises:
            ValueError: For an unknown key, a panel missing from the mosaic,
                a repeated curve id, an unknown style or primary curve.
        """
        _check_keys(description, frozenset({"layout", "figure", "styles", "axes_style", "panels"}),
                    "description")
        self._usetex = usetex
        self._styles: Dict[str, Dict[str, Any]] = dict(description.get("styles", {}))
        self._axes_style = _merge(DEFAULT_AXES_STYLE, description.get("axes_style", {}))
        self._axes: Dict[str, _Axis] = {}
        self._curves: Dict[str, _Curve] = {}
        self._legends: Dict[str, Dict[str, Any]] = {}
        self._legend_on: Dict[str, bool] = {}

        fig_spec = dict(description.get("figure", {}))
        margins = fig_spec.pop("margins", None)
        figure = Figure(**fig_spec)
        super().__init__(figure)
        self.setParent(parent)
        if margins:
            figure.subplots_adjust(**margins)

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
            grid_props=_merge(self._axes_style["grid"], spec.get("grid", {})),
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
        (line,) = axis.ax.plot([], [], **props)
        label = spec.get("label", "")
        curve = _Curve(
            id=curve_id, axis_id=axis.id, line=line,
            label=label, unit=spec.get("unit", ""),
            legend=spec.get("legend", f"${label}$" if label else ""),
        )
        axis.curves[curve_id] = curve
        self._curves[curve_id] = curve

    def _style_axes(self, ax: Axes) -> None:
        """Apply the shared axis styling to one axes."""
        st = self._axes_style
        ax.tick_params(axis="both", which="major", **st["ticks"], **st["ticks_major"])
        ax.tick_params(axis="both", which="minor", **st["ticks"], **st["ticks_minor"])
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
        setter(text, usetex=self._usetex, **self._axes_style["label_font"])

    # ----- keeping an axis consistent with its primary curve -----
    def _primary_color(self, axis: _Axis) -> Optional[str]:
        """Return the colour of the axis' primary curve, if any."""
        curve = axis.curves.get(axis.primary) if axis.primary else None
        return mcolors.to_hex(curve.line.get_color()) if curve is not None else None

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
            axis.zero_line.set_color(color or self._axes_style["zero_line"].get("color", "k"))

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
        for (direction, which), on in axis.grid.items():
            if on and not (axis.select_one and axis.primary is None and direction == value_dir):
                props = dict(axis.grid_props)
                if direction == value_dir and color is not None:
                    props.setdefault("color", color)
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
        """Change line properties of a curve, e.g. ``color="r", linewidth=2``."""
        curve = self._curve(curve_id)
        curve.line.set(**props)
        axis = self._axes[curve.axis_id]
        if axis.primary == curve_id:
            self._refresh_axis(axis)
        self._update_legend(axis.panel_id)

    def get_curve_style(self, curve_id: str) -> Dict[str, Any]:
        """Return a curve's colour, line style and width, marker and marker size."""
        line = self._curve(curve_id).line
        return {
            "color": mcolors.to_hex(line.get_color()),
            "linestyle": line.get_linestyle(),
            "linewidth": float(line.get_linewidth()),
            "marker": line.get_marker(),
            "markersize": float(line.get_markersize()),
        }

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

    def redraw(self) -> None:
        """Schedule a redraw (cheap to call often)."""
        self.draw_idle()
