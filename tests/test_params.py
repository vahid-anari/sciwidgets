import math

import numpy as np
import pytest

from sciwidgets.params import (
    ArraySlider, FloatRangeSlider, FloatSlider, IntSlider, MultiVariableSlider,
    NumericLineEdit, ParameterComboBox, ParameterLineEdit, ParameterToggle,
)


# ----- line edit, combo box, toggle -----
def test_line_edit_value_and_silent_setter(spy):
    w = ParameterLineEdit(label="t_0", init_val=5.0, val_fmt="{:.1f}", min_limit=0.0)
    s = spy(w.valueChanged)
    assert w.get_value() == 5.0
    w.set_value(2.5)
    assert w.get_value() == 2.5 and len(s) == 0


def test_line_edit_rejects_wrong_types():
    w = ParameterLineEdit(label="N", init_val=10, value_is_int=True)
    with pytest.raises(TypeError):
        w.set_value(1.5)
    with pytest.raises(TypeError):
        w.set_value(True)


def test_line_edit_unit_and_old_name():
    assert ParameterLineEdit(label="t", init_val=1.0, unit=r"\mathrm{s}")._unit_label is not None
    assert ParameterLineEdit(label="t", init_val=1.0, unit_label=r"\mathrm{s}")._unit_label is not None
    assert ParameterLineEdit(label="t", init_val=1.0)._unit_label is None
    with pytest.raises(TypeError):
        ParameterLineEdit(label="t", init_val=1.0, unit="s", unit_label="s")


def test_numeric_line_edit_rounds_to_format():
    e = NumericLineEdit(init_val=1.23456, val_fmt="{:.3g}")
    assert e.get_value() == pytest.approx(1.23)


def test_combo_box():
    w = ParameterComboBox(label="t", items=["d", "h", "s"])
    w.set_value("h")
    assert w.get_value() == "h"
    with pytest.raises(ValueError):
        w.set_value("years")


def test_toggle(spy):
    w = ParameterToggle(text="Normalize", checked=True)
    s = spy(w.valueChanged)
    w.set_value(False)
    assert w.get_value() is False and len(s) == 0


# ----- sliders -----
def test_float_slider_value_config_and_silence(spy):
    w = FloatSlider(label="T_1", min_val=0.1, max_val=10.0, init_val=1.0, val_fmt="{:.2f}")
    values, configs = spy(w.valueChanged), spy(w.configChanged)
    w.set_value(2.5)
    assert w.get_value() == 2.5
    cfg = w.get_config()
    assert cfg["min_val"] == 0.1 and cfg["max_val"] == 10.0
    w.set_config({**cfg, "max_val": 20.0, "no_such_key": 1})   # unknown keys are ignored
    assert w.get_config()["max_val"] == 20.0
    assert len(values) == 0 and len(configs) == 0


def test_float_slider_infinity():
    w = FloatSlider(label="T_2", min_val=0.1, max_val=10.0, init_val="+inf", min_limit=0.0)
    assert w.get_value() == math.inf and w.get_special_value() == "+inf"
    w.set_value(2.5)
    assert w.get_value() == 2.5
    w.set_value("+inf")
    assert w.get_value() == math.inf


def test_float_slider_hard_limit():
    w = FloatSlider(label="T", min_val=0.1, max_val=10.0, init_val=1.0,
                    min_limit=0.0, min_limit_inclusive=False)
    with pytest.raises(ValueError):
        w.set_value(0.0)


def test_int_slider():
    w = IntSlider(label="N_z", min_val=10, max_val=1000, init_val=200)
    w.set_value(300)
    assert w.get_value() == 300 and isinstance(w.get_value(), int)


def test_array_slider():
    w = ArraySlider(label="z", arr_length=51, min_val=0.0, max_val=1.0, init_index=25)
    assert w.get_value() == {"arr_length": 51, "index": 25}
    w.set_value({"arr_length": 11, "index": 10})
    assert w.get_value() == {"arr_length": 11, "index": 10}


def test_range_slider_value_dict_and_partial_set():
    w = FloatRangeSlider(label=r"\nu", min_val=6.60, max_val=6.75, init_vals=(6.65, 6.70), val_fmt="{:.3f}")
    v = w.get_value()
    assert v["use_margins"] is False and tuple(v["range"]) == (6.65, 6.7)
    w.set_value({"range": (6.66, 6.69)})
    assert tuple(w.get_value()["range"]) == (6.66, 6.69)
    w.set_value({"use_margins": True, "margins": (5, 5)})
    v = w.get_value()
    assert v["use_margins"] is True and tuple(v["margins"]) == (5, 5)
    assert tuple(v["range"]) == (6.66, 6.69)   # untouched


def test_multi_variable_slider():
    w = MultiVariableSlider(label=r"\tau_k", html_label="τ<sub>k</sub>", min_val=0.0, max_val=100.0,
                            init_vals=[10, 25, 40, "+inf", 80], val_fmt="{:.1f}", min_limit=0.0)
    np.testing.assert_array_equal(w.get_arr_values(), [10, 25, 40, np.inf, 80])
    w.set_index(1)
    assert w.get_index() == 1 and w.get_value() == 25
    w.set_value(30.0)
    assert w.get_arr_values()[1] == 30.0


def test_combo_box_set_items(spy):
    w = ParameterComboBox(label="t", items=["d", "h", "s"])
    s = spy(w.valueChanged)
    w.set_value("h")
    w.set_items(["h", "m", "s"])
    assert w.get_value() == "h" and w.items() == ["h", "m", "s"]
    w.set_items(["a", "b"], current="b")
    assert w.get_value() == "b"
    w.set_items(["x", "y"])
    assert w.get_value() == "x" and len(s) == 0
    with pytest.raises(ValueError):
        w.set_items([])
