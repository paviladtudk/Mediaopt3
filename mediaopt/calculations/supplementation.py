"""What to add to reach a target, element by element."""
from __future__ import annotations
from .nutrient_limitation import ATOMIC


def supplementation(delivered_mmol_L: dict, biomass_pct_CDW: dict, target_CDW_g_L: float,
                    product_demand_mmol_L: dict | None = None) -> list:
    out = []
    for el, pct in sorted(biomass_pct_CDW.items()):
        if el not in ATOMIC or not pct or pct <= 0:
            continue
        have = delivered_mmol_L.get(el, 0.0) / 1000.0 * ATOMIC[el]
        need = target_CDW_g_L * pct / 100.0 + (product_demand_mmol_L or {}).get(el, 0.0) / 1000.0 * ATOMIC[el]
        out.append({"element": el, "available_g_L": have, "required_g_L": need,
                    "shortfall_g_L": max(0.0, need - have),
                    "sufficient": have >= need})
    return out
