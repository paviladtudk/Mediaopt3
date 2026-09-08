"""Instantaneous oxygen and CO2 demand, and the kLa the vessel must deliver.

Every term is a RATE at one chosen moment:

    qS = mu*X/Yx/s          biomass growth
       + sum(r_P / Yp/s)    each product at its own entered productivity
       + mS*X               maintenance

CO2 and O2 are then whatever the carbon and electron balances leave over. Two things
this deliberately does NOT do:

* it never turns a final titre into a rate by multiplying by mu - a titre is an
  accumulated amount, and dP/dt = mu*P only holds for a strictly growth-associated
  product still growing exponentially at that titre;
* it does not treat the biomass-only figure as a floor. Whether a product raises or
  lowers oxygen demand depends entirely on which question you are asking, and the two
  answers differ:

  ADDITIVE (default) - product formation draws EXTRA substrate on top of growth. Under
  this model oxygen demand can only rise, because the extra substrate carries more
  electrons than the product removes for any yield below the stoichiometric maximum.
  This is the design question: "I want this much product as well as this much biomass."

  FIXED_QS - total substrate uptake is what it is, and product formation diverts carbon
  and electrons away from respiration. Here a reduced product genuinely LOWERS oxygen
  demand, which is why fermentative products can be made with little or no O2. This is
  the observational question: "the culture is taking up sugar at this rate; what happens
  to the oxygen if it makes product?"

  The biomass-only value is returned as a comparator either way, with no pass/fail
  attached, because "the floor" is a property of the additive model and not a law.
"""
from __future__ import annotations

C_ATOMIC = 12.011


def gas_demand(*, mu: float, biomass_g_L: float, Yxs: float, mS: float = 0.0,
               substrate_carbon_fraction: float, substrate_mw: float, substrate_gamma: float,
               biomass_carbon_fraction: float, biomass_electrons_per_g: float,
               product_substrate_g_L_h: float = 0.0,
               product_carbon_g_L_h: float = 0.0,
               product_electrons_mol_L_h: float = 0.0,
               aerobic: bool = True,
               substrate_mode: str = "additive",
               total_qS_g_L_h: float | None = None) -> dict:
    if Yxs <= 0:
        raise ValueError("Yx/s must be positive")
    if substrate_mode not in ("additive", "fixed_qS"):
        raise ValueError("substrate_mode must be 'additive' or 'fixed_qS'")
    qS_x = mu * biomass_g_L / Yxs
    qS_m = mS * biomass_g_L
    if substrate_mode == "additive":
        qS = qS_x + product_substrate_g_L_h + qS_m
    else:
        if total_qS_g_L_h is None:
            raise ValueError("fixed_qS mode needs total_qS_g_L_h - the measured uptake rate")
        qS = total_qS_g_L_h

    C_in = qS * substrate_carbon_fraction
    C_X = mu * biomass_g_L * biomass_carbon_fraction
    CER = (C_in - C_X - product_carbon_g_L_h) / C_ATOMIC * 1000.0

    e_in = qS / substrate_mw * substrate_gamma
    e_X = mu * biomass_g_L * biomass_electrons_per_g
    OUR = (e_in - e_X - product_electrons_mol_L_h) / 4.0 * 1000.0 if aerobic else None

    # the same biomass and maintenance, making no product at all - a reference, not a bound
    floor = None
    if aerobic:
        qS_ref = (qS_x + qS_m) if substrate_mode == "additive" else qS
        floor = (qS_ref / substrate_mw * substrate_gamma - e_X) / 4.0 * 1000.0

    return {"substrate_mode": substrate_mode,
            "qS_biomass_g_L_h": qS_x, "qS_product_g_L_h": product_substrate_g_L_h,
            "qS_maintenance_g_L_h": qS_m, "qS_total_g_L_h": qS,
            "CER_mmol_L_h": CER, "OUR_mmol_L_h": OUR,
            "RQ": (CER / OUR) if OUR else None,
            "biomass_only_OUR_mmol_L_h": floor,
            "product_effect_on_OUR": (OUR - floor) if (OUR is not None and floor is not None) else None}


def invert_kla(*, OUR_mmol_L_h: float | None, driving_force: float,
               kLa_available: float | None,
               mu: float, biomass_g_L: float, o2_per_g_biomass: float,
               mS: float, substrate_carbon_fraction: float, substrate_mw: float,
               substrate_gamma: float, product_electrons_mol_L_h: float = 0.0,
               product_substrate_g_L_h: float = 0.0) -> dict:
    """Required kLa, and the two useful inversions of it.

    Oxygen demand decomposes as

        OUR = mu*X*k  +  X*mSterm  +  C_fixed

    where k is the biomass-only oxygen per gram (which scales with both mu and X),
    mSterm scales with X only, and C_fixed - the product terms - scales with neither,
    because the productivity you entered is an independent rate. Scaling the whole
    demand linearly with biomass would therefore be wrong.
    """
    out = {"kLa_required": None, "OTR_available": None,
           "max_mu": None, "max_biomass_g_L": None, "verdict": "anaerobic - no oxygen term"}
    if OUR_mmol_L_h is None:
        return out
    if driving_force <= 0:
        out["verdict"] = "check C* and the DO setpoint - no driving force"
        return out

    out["kLa_required"] = OUR_mmol_L_h / driving_force
    if kLa_available is None:
        out["verdict"] = "enter your vessel's kLa to test feasibility"
        return out

    OTR = kLa_available * driving_force
    gs = substrate_gamma / substrate_mw
    mSterm = 250.0 * mS * gs
    C_fixed = 250.0 * (product_substrate_g_L_h * gs - product_electrons_mol_L_h)
    out["OTR_available"] = OTR
    if biomass_g_L > 0 and o2_per_g_biomass > 0:
        out["max_mu"] = max(0.0, (OTR - biomass_g_L * mSterm - C_fixed) /
                            (biomass_g_L * o2_per_g_biomass))
    denom = mu * o2_per_g_biomass + mSterm
    if denom > 0:
        out["max_biomass_g_L"] = max(0.0, (OTR - C_fixed) / denom)
    out["verdict"] = ("OK - the vessel can supply the peak demand"
                      if out["kLa_required"] <= kLa_available else
                      f"OXYGEN-LIMITED - needs kLa {out['kLa_required']:.0f} but has {kLa_available:.0f}")
    return out
