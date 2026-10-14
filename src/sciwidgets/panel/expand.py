"""Expand templates and container defaults in a layout description.

Two shortcuts keep long descriptions short:

* **Templates.** A top-level ``"templates"`` mapping names reusable widget
  descriptions; a widget uses one with ``"template": "name"`` and adds or
  overrides keys. Nested dicts are merged key by key, so
  ``{"template": "pulse", "a": {"max_val": 50}}`` changes one value inside
  the template's ``"a"``.
* **Defaults.** A container (or the whole panel) may have ``"defaults"``:
  keys applied to every widget inside it, nested containers included. A key
  goes only to widgets whose constructor accepts it, so
  ``{"val_fmt": "{:.3S}"}`` reaches the sliders and skips a toggle.

The most specific value wins: template, then the defaults of the outer
containers, then of the inner ones, then the widget's own keys.

Expansion produces a plain description without ``"template"`` and
``"defaults"`` keys, which :class:`ParameterPage` then builds.
"""

from __future__ import annotations

import copy
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple

from .factory import accepted_args

__all__ = ["deep_merge", "expand_layout", "expand_layouts"]


def deep_merge(base: Mapping[str, Any], override: Mapping[str, Any]) -> Dict[str, Any]:
    """Return ``base`` updated by ``override``; nested dicts are merged too.

    Lists and other values in ``override`` replace those in ``base``.
    Neither argument is modified.
    """
    out = copy.deepcopy(dict(base))
    for key, value in override.items():
        if isinstance(value, Mapping) and isinstance(out.get(key), Mapping):
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


class _Expander:
    """Walk a layout tree, resolving templates and defaults."""

    def __init__(self, templates: Optional[Mapping[str, Any]]) -> None:
        self._templates = dict(templates or {})
        # For each defaults block: where it is, its keys, and the keys some widget took.
        self._defaults_use: List[Tuple[str, Set[str], Set[str]]] = []

    def template(self, name: str, where: str, chain: Tuple[str, ...] = ()) -> Dict[str, Any]:
        """Return a template with any template it is based on resolved."""
        if name in chain:
            raise ValueError(f"{where}: template loop {' -> '.join(chain + (name,))}")
        if name not in self._templates:
            known = ", ".join(sorted(self._templates)) or "none"
            raise ValueError(f"{where}: unknown template {name!r}; known templates: {known}")
        spec = dict(self._templates[name])
        base = spec.pop("template", None)
        if base is None:
            return copy.deepcopy(spec)
        return deep_merge(self.template(base, where, chain + (name,)), spec)

    def widget(self, item: Mapping[str, Any], where: str,
               defaults: List[Tuple[Dict[str, Any], Set[str]]]) -> Dict[str, Any]:
        """Resolve one widget description."""
        own = dict(item)
        name = own.pop("template", None)
        spec = self.template(name, where) if name is not None else {}

        type_name = own.get("type", spec.get("type"))
        if not type_name:
            raise ValueError(f"{where}: widget has no 'type' (neither its own nor from its template)")
        accepted = accepted_args(type_name)  # None = unknown type; the factory reports it later

        for block, used in defaults:
            take = {k: v for k, v in block.items() if accepted is None or k in accepted}
            used.update(take)
            spec = deep_merge(spec, take)
        return deep_merge(spec, own)

    def item(self, item: Any, where: str, defaults: List[Tuple[Dict[str, Any], Set[str]]]) -> Any:
        """Resolve one item: a widget, a container, or anything else (left as is)."""
        if not isinstance(item, Mapping):
            return item
        if "type" in item or "template" in item:
            return self.widget(item, where, defaults)

        out = {k: v for k, v in item.items() if k != "defaults"}
        inner = defaults
        if "defaults" in item:
            block = item["defaults"]
            if not isinstance(block, Mapping):
                raise ValueError(f"{where}: 'defaults' must be an object")
            used: Set[str] = set()
            self._defaults_use.append((where, set(block), used))
            inner = defaults + [(dict(block), used)]
        for key in ("column", "row"):
            if isinstance(item.get(key), list):
                out[key] = [self.item(child, f"{where}.{key}[{i}]", inner)
                            for i, child in enumerate(item[key])]
        return out

    def check_defaults(self) -> None:
        """Report defaults keys that no widget accepted (usually typos)."""
        for where, keys, used in self._defaults_use:
            unused = keys - used
            if unused:
                raise ValueError(f"{where}: defaults key(s) {sorted(unused)} are not accepted "
                                 f"by any widget they apply to")


def expand_layouts(layouts: Sequence[Tuple[str, Mapping[str, Any]]],
                   templates: Optional[Mapping[str, Any]] = None,
                   defaults: Optional[Mapping[str, Any]] = None) -> List[Dict[str, Any]]:
    """Expand several layouts that share templates and panel-wide defaults.

    A panel-wide defaults key only has to be accepted by some widget in any
    of the layouts (e.g. any tab).

    Args:
        layouts: ``(where, layout)`` pairs; ``where`` prefixes error messages.
        templates: Named widget descriptions usable with ``"template"``.
        defaults: Panel-wide defaults, applied before any container's own.

    Returns:
        The expanded layouts, in order; the inputs are not modified.

    Raises:
        ValueError: For an unknown template, a template loop, a widget without
            a type, or a defaults key that no widget in its scope accepts.
    """
    exp = _Expander(templates)
    outer: List[Tuple[Dict[str, Any], Set[str]]] = []
    if defaults:
        if not isinstance(defaults, Mapping):
            raise ValueError("'defaults' must be an object")
        used: Set[str] = set()
        exp._defaults_use.append(("defaults", set(defaults), used))
        outer = [(dict(defaults), used)]
    result = [exp.item(layout, where, outer) for where, layout in layouts]
    exp.check_defaults()
    return result


def expand_layout(layout: Mapping[str, Any],
                  templates: Optional[Mapping[str, Any]] = None,
                  defaults: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    """Return a copy of one layout with templates and defaults applied.

    See :func:`expand_layouts`.
    """
    return expand_layouts([("layout", layout)], templates, defaults)[0]
