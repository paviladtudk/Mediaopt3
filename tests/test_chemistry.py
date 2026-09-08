"""Chemistry that must be right before anything else can be."""
import pytest
from mediaopt.models import load_compounds, load_organisms

LIB = load_compounds()
ORG = load_organisms()


@pytest.mark.parametrize("name,wC,gamma_per_C", [
    ("Glucose anhydrous, C6H12O6",  0.400020, 4.000),
    ("Glycerol, C3H8O3",            0.391263, 4.667),
    ("Succinic acid, C4H6O4",       0.406849, 3.500),
    ("Acetic acid, C2H4O2",         0.400020, 4.000),
    ("Lactic acid, C3H6O3",         0.400020, 4.000),
])
def test_carbon_fraction_and_degree_of_reduction(name, wC, gamma_per_C):
    c = LIB[name]
    assert c.carbon_fraction == pytest.approx(wC, abs=1e-5)
    assert c.gamma_per_cmol == pytest.approx(gamma_per_C, abs=1e-3)


def test_counter_ion_correction():
    """Sodium acetate is 8 electrons per mol, not 7.

    Ignoring the counter-ion charge understates the electron content of every organic
    salt, which then understates oxygen demand.
    """
    assert LIB["Sodium acetate anhydrous, C2H3NaO2"].gamma == 8
    assert LIB["Acetic acid, C2H4O2"].gamma == 8


def test_compound_not_in_library_raises_clearly():
    with pytest.raises(KeyError, match="not in the compound library"):
        LIB.get_or_raise("Unobtainium sulfate")


def test_ecoli_formula():
    o = ORG["Escherichia coli"]
    assert o.gamma_X == pytest.approx(4.07, abs=1e-9)
    assert o.MW_Cmol == pytest.approx(24.99635, abs=1e-5)


def test_carbon_efficiency_round_trips():
    """eta_C = Yx/s * w_C,X / w_C,S must invert exactly back to Yx/s."""
    o = ORG["Escherichia coli"]
    wCs = LIB["Glucose anhydrous, C6H12O6"].carbon_fraction
    eta = o.carbon_efficiency_from_Yxs(0.40, wCs)
    assert o.yield_on_substrate(eta, wCs) == pytest.approx(0.40, abs=1e-12)


def test_rejects_impossible_mass_balance():
    """Biomass carbon plus product carbon cannot exceed the carbon consumed."""
    from mediaopt.calculations import carbon_balance
    r = carbon_balance(substrate_delivered_g_L=10, residual_substrate_g_L=0,
                       substrate_carbon_fraction=0.4, biomass_g_L=8,
                       biomass_carbon_fraction=0.48, product_carbon_g_L=3.0)
    assert r["unaccounted_carbon_g_L"] < 0          # over-closed: impossible as stated
    assert r["carbon_recovery"] > 1.0


def test_intracellular_product_is_not_counted_twice():
    """A product inside the cells is already on the filter when you weigh dry mass."""
    from mediaopt.calculations import carbon_balance
    common = dict(substrate_delivered_g_L=100, residual_substrate_g_L=0,
                  substrate_carbon_fraction=0.4, biomass_g_L=30,
                  biomass_carbon_fraction=0.48, product_carbon_g_L=9.68, co2_mmol_L=1000)
    secreted = carbon_balance(**common)
    intra = carbon_balance(**common, intracellular_product_g_L=23.785)
    assert intra["catalytic_biomass_g_L"] == pytest.approx(6.215, abs=1e-6)
    assert intra["biomass_carbon_g_L"] < secreted["biomass_carbon_g_L"]
    assert intra["carbon_recovery"] < secreted["carbon_recovery"]


def test_product_effect_on_oxygen_depends_on_the_question_asked():
    """The two substrate models give OPPOSITE signs, and both are correct.

    ADDITIVE: product draws extra substrate on top of growth, so oxygen demand can only
    rise - for any yield below the stoichiometric maximum the extra substrate carries
    more electrons than the product removes.

    FIXED_QS: uptake is what it is and product diverts electrons away from respiration,
    so a reduced product LOWERS oxygen demand. This is why ethanol or lactate can be
    made with little or no O2.

    The old workbook asserted a universal floor, which is the additive model mistaken
    for a law.
    """
    from mediaopt.calculations import gas_demand
    base = dict(mu=0.1, biomass_g_L=20, Yxs=0.4, mS=0.0,
                substrate_carbon_fraction=0.400020, substrate_mw=180.156, substrate_gamma=24,
                biomass_carbon_fraction=0.4805, biomass_electrons_per_g=4.07 / 24.99635)
    eth = LIB["Ethanol, C2H6O"]
    assert eth.gamma_per_cmol == pytest.approx(6.0, abs=1e-9)   # far more reduced than biomass
    rP = 2.0
    prod = dict(product_substrate_g_L_h=rP / 0.45,
                product_carbon_g_L_h=rP * eth.carbon_fraction,
                product_electrons_mol_L_h=rP * eth.electrons_per_gram)

    add = gas_demand(**base, **prod)
    assert add["product_effect_on_OUR"] > 0          # extra substrate must be respired

    fixed = gas_demand(**base, **prod, substrate_mode="fixed_qS",
                       total_qS_g_L_h=add["qS_total_g_L_h"])
    assert fixed["product_effect_on_OUR"] < 0        # electrons diverted from oxygen
    # at the same uptake rate, the no-product case demands MORE oxygen than the real one
    assert fixed["OUR_mmol_L_h"] < fixed["biomass_only_OUR_mmol_L_h"]
    # and the two modes differ only in what they compare against, not in OUR itself
    assert fixed["OUR_mmol_L_h"] == pytest.approx(add["OUR_mmol_L_h"], rel=1e-12)


def test_additive_mode_reaches_zero_effect_at_the_stoichiometric_maximum():
    """At the electron-bound maximum yield, product formation is oxygen-neutral."""
    from mediaopt.calculations import gas_demand
    glc, eth = LIB["Glucose anhydrous, C6H12O6"], LIB["Ethanol, C2H6O"]
    Yps_max = glc.electrons_per_gram / eth.electrons_per_gram      # g ethanol / g glucose
    rP = 2.0
    r = gas_demand(mu=0.1, biomass_g_L=20, Yxs=0.4, mS=0.0,
                   substrate_carbon_fraction=glc.carbon_fraction, substrate_mw=glc.mw,
                   substrate_gamma=glc.gamma, biomass_carbon_fraction=0.4805,
                   biomass_electrons_per_g=4.07 / 24.99635,
                   product_substrate_g_L_h=rP / Yps_max,
                   product_carbon_g_L_h=rP * eth.carbon_fraction,
                   product_electrons_mol_L_h=rP * eth.electrons_per_gram)
    assert Yps_max == pytest.approx(0.5114, abs=1e-3)
    assert r["product_effect_on_OUR"] == pytest.approx(0.0, abs=1e-9)
