import pytest

from fcboard.battery import input_range, pack_voltage


def test_pack_voltage_is_cells_times_cell_voltage():
    assert pack_voltage(6, 4.2) == pytest.approx(25.2)
    assert pack_voltage(2, 3.0) == pytest.approx(6.0)


def test_input_range_2s_to_6s_matches_the_plan():
    r = input_range(2, 6, 3.0, 4.2, 4.45)
    assert r.v_min == pytest.approx(6.0)
    assert r.v_max == pytest.approx(25.2)
    assert r.v_max_hv == pytest.approx(26.7)


@pytest.mark.parametrize(
    "args",
    [
        (0, 6, 3.0, 4.2, 4.45),  # no cells
        (6, 2, 3.0, 4.2, 4.45),  # min above max
        (2, 6, 4.2, 3.0, 4.45),  # empty above full
    ],
)
def test_input_range_rejects_bad_inputs(args):
    with pytest.raises(ValueError):
        input_range(*args)
