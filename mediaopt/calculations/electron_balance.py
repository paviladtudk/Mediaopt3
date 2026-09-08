"""Oxygen from the electron balance - a check that shares no data with the carbon one.

    electrons in substrate = electrons in biomass + electrons in products + 4 * O2

It uses degrees of reduction and never touches a carbon mass fraction, so it can fail
while the carbon balance closes. That combination is informative rather than
contradictory: it usually means carbon went somewhere more, or less, reduced than
assumed.
"""
from __future__ import annotations


def electron_balance(*, substrate_consumed_g_L: float, substrate_mw: float,
                     substrate_gamma: float,
                     biomass_g_L: float, biomass_electrons_per_g: float,
                     product_electrons_mol_L: float = 0.0,
                     o2_measured_mmol_L: float | None = None) -> dict:
    if substrate_mw <= 0:
        raise ValueError("substrate molecular weight must be positive")
    e_in = substrate_consumed_g_L / substrate_mw * substrate_gamma
    e_X = biomass_g_L * biomass_electrons_per_g
    o2_pred = max(0.0, (e_in - e_X - product_electrons_mol_L) / 4.0) * 1000.0

    out = {"electrons_in_mol_L": e_in,
           "electrons_biomass_mol_L": e_X,
           "electrons_product_mol_L": product_electrons_mol_L,
           "o2_predicted_mmol_L": o2_pred,
           "o2_measured_mmol_L": o2_measured_mmol_L,
           "ratio": None, "verdict": "no measured oxygen to compare against"}
    if o2_measured_mmol_L and o2_measured_mmol_L > 0:
        r = o2_pred / o2_measured_mmol_L
        out["ratio"] = r
        if 0.95 <= r <= 1.05:
            out["verdict"] = f"AGREES - predicted and measured oxygen within {abs(r-1)*100:.1f}%"
        elif r > 1:
            out["verdict"] = (f"PREDICTED HIGH by {(r-1)*100:.1f}% - the culture used LESS oxygen "
                              f"than the balance says. Carbon likely left in a reduced product "
                              f"you have not measured.")
        else:
            out["verdict"] = (f"PREDICTED LOW by {(1-r)*100:.1f}% - the culture used MORE oxygen "
                              f"than the balance says. Check the off-gas figures first.")
    return out
