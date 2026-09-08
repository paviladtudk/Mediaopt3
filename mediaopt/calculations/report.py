"""One call that runs the whole model and returns a single nested dict.

The web layer does nothing but render this. Keeping the boundary here is what lets the
science be unit-tested without a browser, and lets the same engine drive a CLI, a
notebook or an Excel export.
"""
from __future__ import annotations
from ..models.compounds import CompoundLibrary
from . import (delivered_carbon, delivered_elements, carbon_balance, electron_balance,
               gas_demand, invert_kla, observed_yields, respiratory_quotient,
               liebig_ranking, supplementation)
from .carbon_balance import verdict as carbon_verdict
from ..validation import validate_setup, compare_biomass_descriptions
from ..validation.consistency_checks import cross_check_product_by_difference


def full_report(*, organism, batch, feed, proc, products, lib: CompoundLibrary,
                substrate: str, Yxs: float, co2_mmol_L: float = 0.0,
                o2_mmol_L: float | None = None, titrant_mmol_L: dict | None = None,
                feedstock=None) -> dict:
    sub = lib.get_or_raise(substrate)
    wCs = sub.carbon_fraction
    eta = organism.carbon_efficiency_from_Yxs(Yxs, wCs)

    issues = validate_setup(proc, batch, feed, lib, organism, products)

    # ---- shared: what the recipe delivers -------------------------------------
    extra_el = dict(titrant_mmol_L or {})
    for e, v in (feedstock.elements if feedstock else {}).items():
        extra_el[e] = extra_el.get(e, 0.0) + v
    els = delivered_elements(batch, feed, proc, lib, extra_el)
    carb = delivered_carbon(batch, feed, proc, lib)
    if feedstock:
        carb["carbon_g_per_L"] += feedstock.carbon
        carb["carbon_g_total"] = carb["carbon_g_per_L"] * proc.V_delivered / 1000.0
        carb["feedstock_carbon_g_per_L"] = feedstock.carbon
    S_delivered = carb["carbon_g_per_L"] / wCs if wCs else 0.0

    # ---- design ----------------------------------------------------------------
    lie = liebig_ranking(els, organism.minerals_pct_CDW, carb["carbon_g_per_L"],
                         organism.yield_max_on_carbon() * eta)
    supp = supplementation(els, organism.minerals_pct_CDW, proc.target_CDW)
    rates = products.rates(lib)
    gas = gas_demand(mu=proc.mu, biomass_g_L=proc.target_CDW, Yxs=Yxs, mS=proc.mS,
                     substrate_carbon_fraction=wCs, substrate_mw=sub.mw,
                     substrate_gamma=sub.gamma, biomass_carbon_fraction=organism.wCx,
                     biomass_electrons_per_g=organism.electrons_per_gram,
                     product_substrate_g_L_h=rates["substrate_g_L_h"],
                     product_carbon_g_L_h=rates["carbon_g_L_h"],
                     product_electrons_mol_L_h=rates["electrons_mol_L_h"],
                     aerobic=proc.aerobic)
    o2_per_gX = (sub.gamma / sub.mw / Yxs - organism.electrons_per_gram) / 4 * 1000
    kla = invert_kla(OUR_mmol_L_h=gas["OUR_mmol_L_h"], driving_force=proc.driving_force,
                     kLa_available=proc.kLa_available, mu=proc.mu,
                     biomass_g_L=proc.target_CDW, o2_per_g_biomass=o2_per_gX, mS=proc.mS,
                     substrate_carbon_fraction=wCs, substrate_mw=sub.mw,
                     substrate_gamma=sub.gamma,
                     product_electrons_mol_L_h=rates["electrons_mol_L_h"],
                     product_substrate_g_L_h=rates["substrate_g_L_h"])

    # ---- measured --------------------------------------------------------------
    cdw_del = proc.to_delivered_basis(proc.CDW_assay, proc.CDW_sampled)
    factor = 1.0
    if proc.V_sampled > 0:
        tot = products.measured_titre_total()
        sampled = proc.titre_sampled if proc.titre_sampled is not None else tot
        if tot > 0:
            factor = (proc.V_harvest + (sampled / tot) * proc.V_sampled) / proc.V_delivered
    cb = carbon_balance(substrate_delivered_g_L=S_delivered,
                        residual_substrate_g_L=proc.residual_substrate,
                        substrate_carbon_fraction=wCs, biomass_g_L=cdw_del,
                        biomass_carbon_fraction=organism.wCx,
                        product_carbon_g_L=products.measured_carbon_g_L(lib, factor),
                        co2_mmol_L=co2_mmol_L,
                        intracellular_product_g_L=proc.to_delivered_basis(
                            products.intracellular_titre(), 0.0))
    cb["verdict"] = carbon_verdict(cb["carbon_recovery"])
    eb = electron_balance(substrate_consumed_g_L=cb["substrate_consumed_g_L"],
                          substrate_mw=sub.mw, substrate_gamma=sub.gamma,
                          biomass_g_L=cb["catalytic_biomass_g_L"],
                          biomass_electrons_per_g=organism.electrons_per_gram,
                          product_electrons_mol_L=products.measured_electrons_mol_L(lib, factor),
                          o2_measured_mmol_L=o2_mmol_L)
    ys = observed_yields(biomass_g_L=cdw_del,
                         substrate_consumed_g_L=cb["substrate_consumed_g_L"],
                         carbon_consumed_g_L=cb["carbon_consumed_g_L"],
                         target_product_g_L=products.measured_titre_target(factor))

    # ---- the four checks --------------------------------------------------------
    target = next((p for p in products.products if p.is_target), None)
    byprod_C = sum(lib.get_or_raise(p.compound).carbon_fraction * p.measured_g_L * factor
                   for p in products.products if not p.is_target)
    xcheck = None
    if target:
        xcheck = cross_check_product_by_difference(
            carbon_consumed_g_L=cb["carbon_consumed_g_L"],
            biomass_carbon_g_L=cb["biomass_carbon_g_L"], co2_carbon_g_L=cb["co2_carbon_g_L"],
            byproduct_carbon_g_L=byprod_C,
            target_carbon_fraction=lib.get_or_raise(target.compound).carbon_fraction,
            measured_target_g_L=products.measured_titre_target(factor))
    rq_meas = respiratory_quotient(co2_mmol_L, o2_mmol_L) if o2_mmol_L else None

    return {
        "issues": [i.__dict__ for i in issues],
        "shared": {"elements_mmol_L": els, **carb,
                   "substrate_delivered_g_L": S_delivered,
                   "substrate": substrate, "substrate_carbon_fraction": wCs,
                   "carbon_efficiency": eta},
        "design": {"liebig": lie, "supplementation": supp, "gas": gas, "kla": kla,
                   "product_rates": rates, "o2_per_g_biomass": o2_per_gX},
        "measured": {"biomass_delivered_g_L": cdw_del, "volume_basis_factor": factor,
                     "carbon": cb, "electrons": eb, "yields": ys, "RQ": rq_meas},
        "checks": {"RQ_design": gas["RQ"], "RQ_measured": rq_meas,
                   "kLa_required": kla["kLa_required"], "kLa_available": proc.kLa_available,
                   "oxygen_verdict": kla["verdict"],
                   "carbon_verdict": cb["verdict"], "oxygen_balance": eb["verdict"],
                   "product_by_difference": xcheck},
        "organism_consistency": compare_biomass_descriptions(organism),
    }
