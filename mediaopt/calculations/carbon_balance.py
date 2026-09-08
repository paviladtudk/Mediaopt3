"""Did the carbon add up?

    C_consumed  = (substrate delivered - residual) * w_C,S
    C_accounted = C_biomass + C_products + C_CO2
    recovery    = accounted / consumed

Every term must be on the same volume basis. Biomass and product assays are measured
on harvest broth; substrate is defined per delivered litre. Rebase before you compare.

For an INTRACELLULAR product the CDW assay already contains the product, so the
catalytic (product-free) biomass is what carries the biomass carbon - otherwise that
carbon is counted twice, once as cells and once as product.
"""
from __future__ import annotations

C_ATOMIC = 12.011


def carbon_balance(*, substrate_delivered_g_L: float, residual_substrate_g_L: float,
                   substrate_carbon_fraction: float,
                   biomass_g_L: float, biomass_carbon_fraction: float,
                   product_carbon_g_L: float = 0.0,
                   co2_mmol_L: float = 0.0,
                   intracellular_product_g_L: float = 0.0) -> dict:
    """All concentrations on the DELIVERED-volume basis. Returns a plain dict."""
    if substrate_carbon_fraction <= 0:
        raise ValueError("substrate carbon fraction must be positive")

    catalytic = max(0.0, biomass_g_L - intracellular_product_g_L)
    S_consumed = max(0.0, substrate_delivered_g_L - residual_substrate_g_L)
    C_consumed = S_consumed * substrate_carbon_fraction
    C_X = catalytic * biomass_carbon_fraction
    C_CO2 = co2_mmol_L * C_ATOMIC / 1000.0
    C_acct = C_X + product_carbon_g_L + C_CO2

    return {
        "substrate_consumed_g_L": S_consumed,
        "catalytic_biomass_g_L": catalytic,
        "carbon_consumed_g_L": C_consumed,
        "biomass_carbon_g_L": C_X,
        "product_carbon_g_L": product_carbon_g_L,
        "co2_carbon_g_L": C_CO2,
        "carbon_accounted_g_L": C_acct,
        "carbon_recovery": (C_acct / C_consumed) if C_consumed > 0 else None,
        "unaccounted_carbon_g_L": C_consumed - C_acct,
        "co2_share": (C_CO2 / C_consumed) if C_consumed > 0 else None,
    }


def verdict(recovery: float | None) -> str:
    if recovery is None:
        return "no carbon consumed - check the recipe and the residual substrate"
    if 0.95 <= recovery <= 1.05:
        return "CLOSED - recovery within 95-105%, consistent within normal measurement error"
    if recovery < 0.95:
        return (f"UNDER by {(1-recovery)*100:.1f}% - carbon left somewhere you did not "
                f"measure, or the recipe over-states what you actually fed")
    return (f"OVER by {(recovery-1)*100:.1f}% - something is over-read, or the substrate "
            f"inventory under-states what you fed")
