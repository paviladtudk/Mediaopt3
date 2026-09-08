import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from kla import compute_kla, resolve_diameter, InputError, GENERIC_DIAMETER_CM


def test_default_case_matches_hand_calculation():
    # 500 mL flask, 50 mL fill, 250 rpm, 1" orbit -> the reference case
    # verified by hand and against the source spreadsheet.
    r = compute_kla(
        flask_type="unbaffled",
        flask_size_ml=500,
        working_volume_ml=50,
        rpm=250,
        orbit_in=1,
        temperature_c=37,
    )
    assert r.diameter_cm == 10.0
    assert r.orbit_cm == pytest.approx(2.54)
    assert r.kla_base_s == pytest.approx(0.0185963603320842, rel=1e-9)
    assert r.kla_base_h == pytest.approx(66.9468971955032, rel=1e-9)
    assert r.applied_factor == 1.0
    assert r.kla_adjusted_h == pytest.approx(r.kla_base_h)
    assert r.band_low_h == pytest.approx(r.kla_adjusted_h * 0.70)
    assert r.band_high_h == pytest.approx(r.kla_adjusted_h * 1.30)
    assert r.fill_fraction == pytest.approx(0.10)
    assert r.all_ok


def test_unbaffled_ignores_baffle_factor():
    # A stray baffle_factor must never leak into an "unbaffled" result.
    r = compute_kla(
        flask_type="unbaffled",
        flask_size_ml=500,
        working_volume_ml=50,
        rpm=250,
        orbit_in=1,
        baffle_factor=3.5,
    )
    assert r.applied_factor == 1.0
    assert r.kla_adjusted_h == pytest.approx(r.kla_base_h)


def test_baffled_applies_user_supplied_factor_only():
    base = compute_kla(
        flask_type="unbaffled", flask_size_ml=500, working_volume_ml=50, rpm=250, orbit_in=1,
    )
    baffled = compute_kla(
        flask_type="baffled", flask_size_ml=500, working_volume_ml=50, rpm=250, orbit_in=1,
        baffle_factor=2.2,
    )
    assert baffled.applied_factor == 2.2
    assert baffled.kla_adjusted_h == pytest.approx(base.kla_base_h * 2.2)


def test_custom_diameter_overrides_generic_lookup():
    r = compute_kla(
        flask_size_ml=500, custom_diameter_cm=9.4, working_volume_ml=50, rpm=250, orbit_in=1,
    )
    assert r.diameter_cm == 9.4
    assert r.diameter_cm != GENERIC_DIAMETER_CM[500]


def test_unknown_size_without_custom_diameter_raises():
    with pytest.raises(InputError):
        resolve_diameter(750, None)


def test_validity_flags_detect_out_of_range_conditions():
    r = compute_kla(
        flask_size_ml=500, working_volume_ml=250, rpm=250, orbit_in=1,  # 50% fill -> out of range
    )
    assert r.checks["fill_fraction_in_range"] is False
    assert r.all_ok is False

    r2 = compute_kla(flask_size_ml=500, working_volume_ml=50, rpm=600, orbit_in=1)  # rpm too high
    assert r2.checks["rpm_in_range"] is False
    assert r2.all_ok is False


@pytest.mark.parametrize("bad_kwargs", [
    dict(working_volume_ml=0, rpm=250, orbit_in=1),
    dict(working_volume_ml=50, rpm=0, orbit_in=1),
    dict(working_volume_ml=50, rpm=250, orbit_in=0),
    dict(working_volume_ml=50, rpm=250, orbit_in=1, baffle_factor=0),
    dict(working_volume_ml=50, rpm=250, orbit_in=1, flask_type="bogus"),
])
def test_invalid_inputs_raise(bad_kwargs):
    with pytest.raises(InputError):
        compute_kla(flask_size_ml=500, **bad_kwargs)
