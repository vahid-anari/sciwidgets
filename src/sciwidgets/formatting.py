"""Number formatting helpers shared by the parameter widgets.

Formats are ordinary Python format strings, plus a custom scientific marker
``S`` (for example ``"{:.3S}"``) rendered by :func:`pretty_sci_text`.
"""

from __future__ import annotations

import re
from typing import Literal

__all__ = [
    "format_is_valid",
    "get_numeric_format_field",
    "pretty_sci_text",
    "value_to_text",
    "is_sci_format"
]

_SCI_PAT = r"\{:[0-9]*\.(\d+)S\}"

def pretty_sci_text(
        value: float,
        sig_digits: int = 3,
        notation: Literal["plain", "html", "latex"] = "html",
) -> str:
    """Format a float using scientific notation when appropriate.

    Args:
        value: Numeric value to format.
        sig_digits: Number of significant digits. Must be at least 1.
        notation: Output style. Supported values are ``"plain"``, ``"html"``,
            and ``"latex"``.

    Returns:
        Formatted numeric string.

    Note:
        - Zero is returned as ``"0"``.
        - Values with magnitude in ``[1, 10**sig_digits)`` are shown in ordinary
          significant-digit form unless Python switches to exponent notation
          after rounding.
        - Other values are shown in mantissa-times-ten-to-the-power form.
    """
    if sig_digits < 1:
        raise ValueError("sig_digits must be >= 1")

    if notation not in {"plain", "html", "latex"}:
        raise ValueError("notation must be 'plain', 'html', or 'latex'")

    if value == 0:
        return "0"

    av = abs(value)

    if 1 <= av < 10 ** sig_digits:
        s = f"{value:.{sig_digits}g}"
        if "e" not in s and "E" not in s:
            if "." in s:
                int_part, frac_part = s.split(".", 1)
                return f"{int(int_part):,d}.{frac_part}"
            return f"{int(s):,d}"

    s = f"{value:.{sig_digits - 1}e}"
    mant_str, exp_str = s.split("e", 1)
    exp = int(exp_str)

    if notation == "html":
        return f"{mant_str}×10<sup>{exp}</sup>"
    if notation == "latex":
        return rf"{mant_str}\times 10^{{{exp}}}"
    return f"{mant_str}×10^{exp}"

def format_is_valid(fmt: str, sample: int | float) -> bool:
    """Return whether ``fmt`` can format ``sample`` without falling back.

    Args:
        fmt: Format string, possibly using the custom ``"S"`` marker.
        sample: Value of the type the format will be used with.

    Returns:
        ``True`` if the format is usable for ``sample``.
    """
    try:
        get_numeric_format_field(fmt).format(sample)
        if not re.search(_SCI_PAT, fmt):
            fmt.format(sample)
    except (ValueError, TypeError, IndexError, KeyError):
        return False
    return True


def get_numeric_format_field(fmt: str) -> str:
    """Return a Python-compatible numeric replacement field derived from ``fmt``.

    This helper is used to configure numeric line-edit parsing and validation so
    that entered values remain consistent with a widget's display format.

    Args:
        fmt: Original format string.

    Returns:
        Full replacement field such as ``"{:.3f}"`` or ``"{:}"``.

    Note:
        - Only the first replacement field with an explicit format specifier is
          used.
        - If no such field is found, ``"{:}"`` is returned.
        - The custom scientific marker ``"S"`` is replaced with ``"g"`` because
          ``"S"`` is not a valid Python numeric format type.
    """
    m = re.search(r"\{[^{}]*:([^{}]*)\}", fmt)
    if not m:
        return "{:}"
    spec = m.group(1).replace("S", "g")
    spec = spec.replace(",", "")
    return f"{{:{spec}}}"


def value_to_text(value: int | float, fmt: str) -> str:
    """Format a numeric value for display.

    Args:
        value: Numeric value to format.
        fmt: Format string, which may use ordinary Python formatting or the
            custom ``"S"`` scientific marker.

    Returns:
        Formatted text. Falls back to ``str(value)`` if formatting fails.

    Note:
        The custom scientific pattern such as ``"{:.2S}"`` is expanded using
        ``pretty_sci_text``.
    """

    if not re.search(_SCI_PAT, fmt):
        try:
            return fmt.format(value)
        except Exception:
            return str(value)

    def repl(m: re.Match) -> str:
        """Replace a custom scientific field with formatted text."""
        prec = int(m.group(1))
        return pretty_sci_text(float(value), sig_digits=prec)

    try:
        return re.sub(_SCI_PAT, repl, fmt)
    except Exception:
        return str(value)

def is_sci_format(fmt: str) -> bool:
    """Return whether ``fmt`` uses the custom ``S`` scientific marker.

    Args:
        fmt: Format string to inspect.

    Returns:
        ``True`` if ``fmt`` contains a field such as ``"{:.3S}"``.
    """
    return re.search(_SCI_PAT, fmt) is not None