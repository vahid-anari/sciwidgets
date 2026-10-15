import pytest

from sciwidgets.formatting import (
    format_is_valid, get_numeric_format_field, is_sci_format, pretty_sci_text, value_to_text,
)


@pytest.mark.parametrize("value, fmt, expected", [
    (12345.678, "{:.3S}", "1.23×10<sup>4</sup>"),
    (0.01, "{:.2S}", "1.0×10<sup>-2</sup>"),
    (123.456, "{:.3S}", "123"),
    (50000, "{:.8S}", "50,000"),
    (3.14159, "{:.2f}", "3.14"),
])
def test_value_to_text(value, fmt, expected):
    assert value_to_text(value, fmt).replace("−", "-") == expected


def test_pretty_sci_text_notations():
    assert pretty_sci_text(6.67e-11, 3, notation="latex") == r"6.67\times 10^{-11}"
    assert pretty_sci_text(12345.678, 3, notation="plain") == "1.23×10^4"


def test_format_helpers():
    assert is_sci_format("{:.3S}") and not is_sci_format("{:.3f}")
    assert get_numeric_format_field("{:.3S}") == "{:.3g}"
    assert format_is_valid("{:.2f}", 1.0)
    assert not format_is_valid("{:.2q}", 1.0)
