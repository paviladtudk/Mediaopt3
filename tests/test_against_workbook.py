"""Regression against the spreadsheet the engine replaces.

Every expected value in this file was read out of a LibreOffice recalculation of
MediaOpt_FedBatch_Template_30.xlsx - they are the workbook's own numbers, not numbers
chosen to make the tests pass. If the engine and the workbook ever disagree, one of
them is wrong and this test says so.
"""
import json
from pathlib import Path
import pytest

from mediaopt.models import load_compounds, load_organisms, ProcessSetup
from mediaopt.calculations import (carbon_balance, electron_balance, gas_demand,
                                   invert_kla, observed_yields, respiratory_quotient)

G = json.loads((Path(__file__).parent / "golden_workbook.json").read_text())
LIB = load_compounds()
GLC = LIB["Glucose anhydrous, C6H12O6"]
REL = 1e-6


@pytest.fixture
def proc():
    return ProcessSetup(V_batch=G["V_batch"], V_feed=G["V_feed"], V_base=G["V_base"],
                        V_acid=G["V_acid"], V_sampled=G["V_sampled"],
                        CDW_sampled=G["CDW_sampled"], CDW_assay=G["CDW_assay"],
                        residual_substrate=G["resid_harvest"], target_CDW=G["target_CDW"],
                        mu=G["mu"], mS=G["mS"], C_star=G["Cstar"],
                        DO_setpoint_fraction=G["DO_frac"], kLa_available=G["kLa_have"])


def test_volumes(proc):
    assert proc.V_delivered == pytest.approx(G["V_total"], rel=REL)
    assert proc.V_harvest == pytest.approx(G["V_harvest"], rel=REL)


def test_delivered_basis_rebase(proc):
    """The harvest assay put onto the delivered volume."""
    assert proc.to_delivered_basis(G["CDW_assay"], G["CDW_sampled"]) == \
        pytest.approx(G["CDW_delivered"], rel=REL)


def test_substrate_carbon_fraction():
    assert GLC.carbon_fraction == pytest.approx(G["wCs"], rel=REL)


def test_carbon_balance_reproduces_workbook(proc):
    r = carbon_balance(
        substrate_delivered_g_L=G["S_delivered"],
        residual_substrate_g_L=G["resid_harvest"],
        substrate_carbon_fraction=G["wCs"],
        biomass_g_L=G["CDW_delivered"],
        biomass_carbon_fraction=G["wCx_pct"] / 100,
        product_carbon_g_L=G["C_P"],
        co2_mmol_L=G["CO2_mmol"])
    assert r["substrate_consumed_g_L"] == pytest.approx(G["S_consumed"], rel=REL)
    assert r["carbon_consumed_g_L"] == pytest.approx(G["C_consumed"], rel=REL)
    assert r["biomass_carbon_g_L"] == pytest.approx(G["C_X"], rel=REL)
    assert r["co2_carbon_g_L"] == pytest.approx(G["C_CO2"], rel=REL)
    assert r["carbon_accounted_g_L"] == pytest.approx(G["C_acct"], rel=REL)
    assert r["carbon_recovery"] == pytest.approx(G["recovery"], rel=REL)


def test_carbon_balance_closes():
    """The shipped example is built so that it closes; guard that it stays closed."""
    r = carbon_balance(
        substrate_delivered_g_L=G["S_delivered"], residual_substrate_g_L=G["resid_harvest"],
        substrate_carbon_fraction=G["wCs"], biomass_g_L=G["CDW_delivered"],
        biomass_carbon_fraction=G["wCx_pct"] / 100, product_carbon_g_L=G["C_P"],
        co2_mmol_L=G["CO2_mmol"])
    assert 0.99 <= r["carbon_recovery"] <= 1.01


def test_electron_balance_reproduces_workbook():
    r = electron_balance(
        substrate_consumed_g_L=G["S_consumed"], substrate_mw=GLC.mw,
        substrate_gamma=GLC.gamma, biomass_g_L=G["CDW_delivered"],
        biomass_electrons_per_g=G["gamma_X"] / G["MW_Cmol"],
        product_electrons_mol_L=G["e_P"], o2_measured_mmol_L=G["O2_meas"])
    assert r["electrons_in_mol_L"] == pytest.approx(G["e_in"], rel=REL)
    assert r["electrons_biomass_mol_L"] == pytest.approx(G["e_X"], rel=REL)
    assert r["o2_predicted_mmol_L"] == pytest.approx(G["O2_pred"], rel=REL)
    assert r["ratio"] == pytest.approx(G["O2_ratio"], rel=REL)


def test_gas_demand_reproduces_workbook():
    r = gas_demand(
        mu=G["mu"], biomass_g_L=G["target_CDW"], Yxs=G["Yxs_real"], mS=G["mS"],
        substrate_carbon_fraction=G["wCs"], substrate_mw=GLC.mw, substrate_gamma=GLC.gamma,
        biomass_carbon_fraction=G["wCx_pct"] / 100,
        biomass_electrons_per_g=G["gamma_X"] / G["MW_Cmol"],
        product_substrate_g_L_h=G["qS_products"],
        product_carbon_g_L_h=0.36616421651649,
        product_electrons_mol_L_h=0.10670008806991)
    assert r["qS_biomass_g_L_h"] == pytest.approx(G["qS_biomass"], rel=REL)
    assert r["qS_maintenance_g_L_h"] == pytest.approx(G["qS_maint"], rel=REL)
    assert r["qS_total_g_L_h"] == pytest.approx(G["qS_total"], rel=REL)
    assert r["CER_mmol_L_h"] == pytest.approx(G["CER"], rel=1e-5)
    assert r["OUR_mmol_L_h"] == pytest.approx(G["OUR"], rel=1e-5)
    assert r["biomass_only_OUR_mmol_L_h"] == pytest.approx(G["OUR_floor"], rel=1e-5)


def test_required_kla_reproduces_workbook(proc):
    r = invert_kla(OUR_mmol_L_h=G["OUR"], driving_force=proc.driving_force,
                   kLa_available=G["kLa_have"], mu=G["mu"], biomass_g_L=G["target_CDW"],
                   o2_per_g_biomass=G["O2_per_gX"], mS=G["mS"],
                   substrate_carbon_fraction=G["wCs"], substrate_mw=GLC.mw,
                   substrate_gamma=GLC.gamma,
                   product_electrons_mol_L_h=0.10670008806991,
                   product_substrate_g_L_h=G["qS_products"])
    assert r["kLa_required"] == pytest.approx(G["kLa_req"], rel=1e-5)
    assert r["verdict"].startswith("OXYGEN-LIMITED")
    assert r["max_mu"] < G["mu"] and r["max_biomass_g_L"] < G["target_CDW"]


def test_observed_yields_reproduce_workbook():
    y = observed_yields(biomass_g_L=G["CDW_delivered"],
                        substrate_consumed_g_L=G["S_consumed"],
                        carbon_consumed_g_L=G["C_consumed"],
                        target_product_g_L=G["Ypx_obs"] * G["CDW_delivered"])
    assert y["Yx_C"] == pytest.approx(G["Yxc_obs"], rel=1e-5)
    assert y["Yx_S"] == pytest.approx(G["Yxs_obs"], rel=1e-5)


def test_measured_rq():
    assert respiratory_quotient(G["CO2_mmol"], G["O2_mmol"]) == \
        pytest.approx(G["RQ_measured"], rel=REL)
