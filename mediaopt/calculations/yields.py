"""Observed yields, all on substrate and carbon CONSUMED - never on delivered."""
from __future__ import annotations


def observed_yields(*, biomass_g_L: float, substrate_consumed_g_L: float,
                    carbon_consumed_g_L: float, target_product_g_L: float = 0.0) -> dict:
    def d(n, x):
        return n / x if x > 0 else None
    return {"Yx_C": d(biomass_g_L, carbon_consumed_g_L),
            "Yx_S": d(biomass_g_L, substrate_consumed_g_L),
            "Yp_S": d(target_product_g_L, substrate_consumed_g_L),
            "Yp_X": d(target_product_g_L, biomass_g_L)}


def respiratory_quotient(co2_mmol_L: float, o2_mmol_L: float) -> float | None:
    """mol CO2 per mol O2. Plausible whole-run aerobic values sit roughly in 0.4-1.6."""
    return co2_mmol_L / o2_mmol_L if o2_mmol_L else None
