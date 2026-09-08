"""Checks that compare two independently derived numbers."""
from __future__ import annotations
from .validators import ValidationIssue


def compare_biomass_descriptions(organism) -> dict:
    """The CHON formula and the % CDW table come from different measurements.

    A gap is not an error - it is two methods disagreeing - but you should know its size
    before relying on either. The nutrient ceilings use the table; the oxygen balance
    uses the formula.
    """
    n_formula = organism.N_C * 14.007 / organism.MW_Cmol * 100
    c_formula = 12.011 / organism.MW_Cmol * 100
    n_table = organism.minerals_pct_CDW.get("N")
    out = {"N_from_formula_pct": n_formula, "N_from_table_pct": n_table,
           "C_from_formula_pct": c_formula, "C_used_pct": organism.C_pct_CDW,
           "C_difference": c_formula / organism.C_pct_CDW - 1 if organism.C_pct_CDW else None,
           "N_difference": (n_formula / n_table - 1) if n_table else None}
    gaps = [abs(v) for v in (out["C_difference"], out["N_difference"]) if v is not None]
    out["verdict"] = ("consistent" if gaps and max(gaps) < 0.05 else
                      "DIVERGENT - the nutrient ceilings and the oxygen balance are running on "
                      "different descriptions of the same cell")
    return out


def cross_check_product_by_difference(*, carbon_consumed_g_L: float, biomass_carbon_g_L: float,
                                      co2_carbon_g_L: float, byproduct_carbon_g_L: float,
                                      target_carbon_fraction: float,
                                      measured_target_g_L: float) -> dict:
    """A second, independent route to the product titre.

    Whatever carbon is left after biomass, CO2 and byproducts had to become target
    product. Note the identity: implied carbon minus measured target carbon IS the
    unaccounted figure, so a ratio far from 1.0 is the carbon balance restated in
    product units, not a separate finding.
    """
    left = carbon_consumed_g_L - biomass_carbon_g_L - co2_carbon_g_L - byproduct_carbon_g_L
    implied = left / target_carbon_fraction if target_carbon_fraction > 0 else None
    ratio = (implied / measured_target_g_L) if (implied is not None and measured_target_g_L > 0) else None
    v = "enter a measured target-product titre"
    if ratio is not None:
        v = ("AGREES - within 2% of your assay, so two independent routes match"
             if abs(ratio - 1) <= 0.02 else
             f"{'IMPLIED HIGHER' if ratio > 1 else 'IMPLIED LOWER'} by "
             f"{abs(implied - measured_target_g_L):.2f} g/L - this is the carbon balance "
             f"restated in product units, not a separate finding")
    return {"carbon_left_g_L": left, "implied_titre_g_L": implied,
            "measured_titre_g_L": measured_target_g_L, "ratio": ratio, "verdict": v}


def recipe_matches_run(proc, batch, feed, lib, organism, products=None):
    """Does the recipe describe the run the assays describe?

    The single highest-value check in the whole engine. The recipe sets the denominator
    of the carbon recovery, so a recipe from a different experiment yields a confidently
    wrong answer with no other symptom.
    """
    from ..calculations.elemental_balance import delivered_carbon
    if proc.CDW_assay <= 0:
        return None
    try:
        C_del = delivered_carbon(batch, feed, proc, lib)["carbon_g_per_L"]
    except Exception:
        return None
    wCs_guess = 0.4
    C_res = proc.residual_substrate * wCs_guess
    C_cons = max(0.0, C_del - C_res)
    if C_cons <= 0:
        return None
    cdw_del = proc.to_delivered_basis(proc.CDW_assay, proc.CDW_sampled)
    C_bio = cdw_del * organism.wCx
    C_prod = 0.0
    if products:
        C_prod = products.measured_carbon_g_L(lib)
    plausible_max = (C_bio + C_prod) / 0.35      # even at 65% to CO2
    if C_cons > plausible_max:
        return ValidationIssue(
            "error", "recipe",
            f"The recipe delivers {C_del:.1f} g C/L but your measured cells and product only "
            f"account for {C_bio + C_prod:.1f} g C/L. Even sending 65% of the carbon to CO2 "
            f"cannot bridge that. Either the medium tabs describe a different run, or the "
            f"residual substrate is far higher than {proc.residual_substrate:g} g/L.")
    return None
