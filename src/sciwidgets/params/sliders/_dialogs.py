"""Out-of-range questions shown by the slider widgets."""

from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import QWidget

from ...dialogs import AskResult, ask_question


def slider_ask_clamp_value(
    proposed_range: str,
    old_cur: str,
    new_cur: str,
    old_dft: str,
    new_dft: str,
    parent: Optional[QWidget] = None,
) -> AskResult:
    """Ask whether a slider value should be clamped to a proposed range.

    Args:
        proposed_range: Proposed allowed range.
        old_cur: Previous current value.
        new_cur: Clamped current value.
        old_dft: Previous default value.
        new_dft: Clamped default value.
        parent: Optional parent widget.

    Returns:
        User's selected answer.
    """

    return ask_question(
        "Out of range",
        "<b>Current</b>/<b>default</b> value is outside the proposed range.",
        f"<b>Proposed range:</b> <code>{proposed_range}</code><br>"
        f"<b>Current:</b> <code>{old_cur}</code> → <code>{new_cur}</code><br>"
        f"<b>Default:</b> <code>{old_dft}</code> → <code>{new_dft}</code><br><br>"
        "Press <b>OK</b> to clamp values to the proposed range, or <b>Cancel</b> to abort.",
        yes_btn_label="OK",
        cancel_btn_label="Cancel",
        parent=parent,
    )


def range_slider_ask_clamp_value(
    proposed_range: str,
    old_cur: str,
    new_cur: str,
    old_dft: str,
    new_dft: str,
    parent: Optional[QWidget] = None,
) -> AskResult:
    """Ask whether range-slider values should be clamped to proposed limits.

    Args:
        proposed_range: Proposed allowed range limits.
        old_cur: Previous current range.
        new_cur: Clamped current range.
        old_dft: Previous default range.
        new_dft: Clamped default range.
        parent: Optional parent widget.

    Returns:
        User's selected answer.
    """

    return ask_question(
        "Out of range",
        "<b>Current</b>/<b>default</b> values are outside the proposed range limits.",
        f"<b>Proposed range limits:</b> <code>{proposed_range}</code><br>"
        f"<b>Current:</b> <code>{old_cur}</code> → <code>{new_cur}</code><br>"
        f"<b>Default:</b> <code>{old_dft}</code> → <code>{new_dft}</code><br><br>"
        "Press <b>OK</b> to clamp values to the proposed range, or <b>Cancel</b> to abort.",
        yes_btn_label="OK",
        cancel_btn_label="Cancel",
        parent=parent,
    )


def multi_slider_ask_clamp_value(
    proposed_range: str,
    cur_min: str,
    cur_max: str,
    dft_min: str,
    dft_max: str,
    parent: Optional[QWidget] = None,
) -> AskResult:
    """Ask whether array-slider values should be clamped to a proposed range.

    Args:
        proposed_range: Proposed allowed range.
        cur_min: Minimum current value.
        cur_max: Maximum current value.
        dft_min: Minimum default value.
        dft_max: Maximum default value.
        parent: Optional parent widget.

    Returns:
        User's selected answer.
    """

    return ask_question(
        "Out of range",
        "<b>Current</b>/<b>default</b> values are outside the proposed range.",
        f"<b>Proposed range:</b> <code>{proposed_range}</code><br>"
        f"<b>Current values range:</b> <code>[{cur_min}, {cur_max}]</code><br>"
        f"<b>Default values range:</b> <code>[{dft_min}, {dft_max}]</code><br><br>"
        "Press <b>OK</b> to clamp values to the proposed range, or <b>Cancel</b> to abort.",
        yes_btn_label="OK",
        cancel_btn_label="Cancel",
        parent=parent,
    )


def slider_ask_extend_range(
    proposed_val: str,
    old_range: str,
    new_range: str,
    parent: Optional[QWidget] = None,
) -> AskResult:
    """Ask whether a slider range should be extended to include a new value.

    Args:
        proposed_val: Proposed new value.
        old_range: Existing range.
        new_range: Extended range.
        parent: Optional parent widget.

    Returns:
        User's selected answer.
    """

    return ask_question(
        "Out of range",
        "The proposed <b>value</b> is outside the current range.",
        f"<b>Proposed value:</b> <code>{proposed_val}</code><br>"
        f"<b>Range:</b> <code>{old_range}</code> → <code>{new_range}</code><br><br>"
        "Press <b>OK</b> to extend the range to include this value, or <b>Cancel</b> to abort.",
        yes_btn_label="OK",
        cancel_btn_label="Cancel",
        parent=parent,
    )


def range_slider_ask_extend_range(
    proposed_vals: str,
    old_range: str,
    new_range: str,
    parent: Optional[QWidget] = None,
) -> AskResult:
    """Ask whether a range-slider range should be extended for new values.

    Args:
        proposed_vals: Proposed new range values.
        old_range: Existing range.
        new_range: Extended range.
        parent: Optional parent widget.

    Returns:
        User's selected answer.
    """

    return ask_question(
        "Out of range",
        "The proposed <b>values</b> are outside the current range limits.",
        f"<b>Proposed values:</b> <code>{proposed_vals}</code><br>"
        f"<b>Range:</b> <code>{old_range}</code> → <code>{new_range}</code><br><br>"
        "Press <b>OK</b> to extend the range to include these values, or <b>Cancel</b> to abort.",
        yes_btn_label="OK",
        cancel_btn_label="Cancel",
        parent=parent,
    )
