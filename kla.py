"""
Shake-flask kLa engineering estimator — calculation core.

Implements the Seletzky/Maier correlation for volumetric oxygen transfer
coefficient (kLa) in orbitally shaken, standard non-baffled glass Erlenmeyer
flasks, plus the same honest treatment of baffled flasks used throughout
this project: baffles are known (qualitatively) to increase oxygen
transfer, but no general/universal correlation exists as a function of
baffle geometry. Baffled results are therefore always the base (non-baffled)
estimate multiplied by a correction factor the CALLER supplies, calibrated
against their own measurement (sulfite oxidation, dynamic gassing-out,
RAMOS/OTR, etc.) — never a value invented by this module.

Sources:
  - Seletzky, J. — dissertation, RWTH Aachen.
    https://publications.rwth-aachen.de/record/50532/files/Seletzky_Juri.pdf
  - Brauneck et al., 2025, Engineering in Life Sciences.
    https://pmc.ncbi.nlm.nih.gov/articles/PMC11773345/
  - Kloeckner & Buechs, Comprehensive Biotechnology.
    https://www.sciencedirect.com/topics/engineering/shake-flask
  - Maier & Buechs, 2001. https://doi.org/10.1016/S1369-703X(00)00107-8

This module has no web framework dependency so it can be unit tested and
reused independent of Flask.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

# Generic max. inner diameters (cm) for standard nominal flask sizes (mL),
# reproduced from the Assumptions & Sources reference used throughout this
# project. Replace with a manufacturer-specific diameter via the
# `custom_diameter_cm` argument whenever it is known.
GENERIC_DIAMETER_CM = {
    50: 5.0,
    100: 7.0,
    250: 8.0,
    500: 10.0,
    1000: 12.0,
}

STANDARD_SIZES_ML = sorted(GENERIC_DIAMETER_CM.keys())
ORBIT_CHOICES_IN = (1, 2)
FLASK_TYPES = ("unbaffled", "baffled")

# Validated operating domain of the base correlation.
VALID_SIZE_RANGE_ML = (50, 1000)
VALID_FILL_RANGE = (0.04, 0.20)
VALID_RPM_RANGE = (50, 500)
VALID_ORBIT_RANGE_CM = (1.25, 10.0)


class InputError(ValueError):
    """Raised when a supplied input cannot be used to compute an estimate."""


@dataclass
class KlaResult:
    # echoed inputs
    flask_type: str
    flask_size_ml: Optional[int]
    working_volume_ml: float
    rpm: float
    orbit_in: float
    temperature_c: float
    baffle_factor: float

    # derived geometry
    diameter_cm: float
    orbit_cm: float
    fill_fraction: Optional[float]
    max_accel_g: float

    # results
    kla_base_s: float
    kla_base_h: float
    applied_factor: float
    kla_adjusted_h: float
    band_low_h: float
    band_high_h: float

    # validity
    checks: dict = field(default_factory=dict)

    @property
    def all_ok(self) -> bool:
        return all(v is not False for v in self.checks.values())

    def to_dict(self) -> dict:
        d = self.__dict__.copy()
        return d


def resolve_diameter(flask_size_ml: Optional[int], custom_diameter_cm: Optional[float]) -> float:
    """Return the flask's max. inner diameter in cm.

    A custom diameter always wins (it represents real, manufacturer-known
    geometry). Otherwise the nominal size is looked up in the generic table
    reproduced from the source workbook.
    """
    if custom_diameter_cm not in (None, ""):
        return float(custom_diameter_cm)
    if flask_size_ml is None:
        raise InputError("Provide either a standard flask_size_ml or a custom_diameter_cm.")
    try:
        return GENERIC_DIAMETER_CM[int(flask_size_ml)]
    except (KeyError, ValueError, TypeError):
        raise InputError(
            f"No generic diameter on file for {flask_size_ml} mL. "
            f"Standard sizes are {STANDARD_SIZES_ML}; supply custom_diameter_cm instead."
        )


def compute_kla(
    *,
    flask_type: str = "unbaffled",
    flask_size_ml: Optional[int] = 500,
    custom_diameter_cm: Optional[float] = None,
    working_volume_ml: float,
    rpm: float,
    orbit_in: float = 1,
    temperature_c: float = 37.0,
    baffle_factor: float = 1.0,
) -> KlaResult:
    """Compute the shake-flask kLa estimate for one operating condition.

    All physical inputs must be positive. `flask_type` selects whether the
    user-supplied `baffle_factor` is actually applied: for "unbaffled" the
    applied factor is always forced to 1.0, no matter what `baffle_factor`
    is set to, so a stray calibration value can never silently distort the
    validated base estimate.
    """
    if flask_type not in FLASK_TYPES:
        raise InputError(f"flask_type must be one of {FLASK_TYPES}, got {flask_type!r}")
    if working_volume_ml <= 0:
        raise InputError("working_volume_ml must be > 0")
    if rpm <= 0:
        raise InputError("rpm must be > 0")
    if orbit_in <= 0:
        raise InputError("orbit_in must be > 0")
    if baffle_factor <= 0:
        raise InputError("baffle_factor must be > 0")

    diameter_cm = resolve_diameter(flask_size_ml, custom_diameter_cm)
    orbit_cm = orbit_in * 2.54

    kla_base_s = (
        6.67e-6
        * math.pow(rpm, 1.16)
        * math.pow(working_volume_ml, -0.83)
        * math.pow(orbit_cm, 0.38)
        * math.pow(diameter_cm, 1.92)
    )
    kla_base_h = kla_base_s * 3600.0

    applied_factor = baffle_factor if flask_type == "baffled" else 1.0
    kla_adjusted_h = kla_base_h * applied_factor

    fill_fraction = (working_volume_ml / flask_size_ml) if flask_size_ml else None

    max_accel_g = (
        4 * math.pi ** 2 * (rpm / 60.0) ** 2 * (orbit_in * 0.0254 / 2.0) / 9.80665
    )

    checks = {
        "flask_size_in_range": (
            None if flask_size_ml is None
            else VALID_SIZE_RANGE_ML[0] <= flask_size_ml <= VALID_SIZE_RANGE_ML[1]
        ),
        "fill_fraction_in_range": (
            None if fill_fraction is None
            else VALID_FILL_RANGE[0] <= fill_fraction <= VALID_FILL_RANGE[1]
        ),
        "rpm_in_range": VALID_RPM_RANGE[0] <= rpm <= VALID_RPM_RANGE[1],
        "orbit_in_range": VALID_ORBIT_RANGE_CM[0] <= orbit_cm <= VALID_ORBIT_RANGE_CM[1],
    }

    return KlaResult(
        flask_type=flask_type,
        flask_size_ml=flask_size_ml,
        working_volume_ml=working_volume_ml,
        rpm=rpm,
        orbit_in=orbit_in,
        temperature_c=temperature_c,
        baffle_factor=baffle_factor,
        diameter_cm=diameter_cm,
        orbit_cm=orbit_cm,
        fill_fraction=fill_fraction,
        max_accel_g=max_accel_g,
        kla_base_s=kla_base_s,
        kla_base_h=kla_base_h,
        applied_factor=applied_factor,
        kla_adjusted_h=kla_adjusted_h,
        band_low_h=kla_adjusted_h * 0.70,
        band_high_h=kla_adjusted_h * 1.30,
        checks=checks,
    )
