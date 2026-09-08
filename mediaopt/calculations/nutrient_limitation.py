"""Liebig's law of the minimum: the nutrient that runs out first sets the ceiling.

A mineral ends up almost entirely in the cells, so its ceiling is stoichiometric.
Carbon is different - in aerobic growth much of it leaves as CO2 - so carbon is ranked
using the realistic yield, not the stoichiometric one.

An element with no biomass content entered is reported as NOT RANKED rather than as
zero. Treating "unknown" as "none" would make it falsely limiting, which is exactly the
failure mode of an incomplete trace-element inventory.
"""
from __future__ import annotations

ATOMIC = {"N": 14.007, "P": 30.974, "S": 32.06, "K": 39.098, "Mg": 24.305, "Ca": 40.078,
          "Fe": 55.845, "Zn": 65.38, "Mn": 54.938, "Cu": 63.546, "Mo": 95.95,
          "Co": 58.933, "Ni": 58.693, "B": 10.81}
MACRO = {"N", "P", "S", "K", "Mg", "Ca"}


def liebig_ranking(delivered_mmol_L: dict, biomass_pct_CDW: dict,
                   carbon_g_L: float | None = None,
                   realistic_yield_on_carbon: float | None = None,
                   rank_carbon: bool = True) -> dict:
    rows, unranked = [], []
    for el, pct in biomass_pct_CDW.items():
        if el not in ATOMIC:
            continue
        if not pct or pct <= 0:
            unranked.append(el)
            continue
        g_per_L = delivered_mmol_L.get(el, 0.0) / 1000.0 * ATOMIC[el]
        rows.append({"element": el, "delivered_g_L": g_per_L,
                     "g_CDW_per_g_element": 100.0 / pct,
                     "max_CDW_g_L": g_per_L * 100.0 / pct,
                     "macro": el in MACRO})
    for el in ATOMIC:
        if el not in biomass_pct_CDW:
            unranked.append(el)
    if rank_carbon and carbon_g_L is not None and realistic_yield_on_carbon:
        rows.append({"element": "C", "delivered_g_L": carbon_g_L,
                     "g_CDW_per_g_element": realistic_yield_on_carbon,
                     "max_CDW_g_L": carbon_g_L * realistic_yield_on_carbon,
                     "macro": True})
    rows.sort(key=lambda r: r["max_CDW_g_L"])
    macro = [r for r in rows if r["macro"]]
    return {"rows": rows,
            "limiting": rows[0]["element"] if rows else None,
            "max_CDW_g_L": rows[0]["max_CDW_g_L"] if rows else None,
            "limiting_macro": macro[0]["element"] if macro else None,
            "max_CDW_macro_g_L": macro[0]["max_CDW_g_L"] if macro else None,
            "not_ranked": sorted(set(unranked))}
