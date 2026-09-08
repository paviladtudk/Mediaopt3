"""The full pipeline, end to end, on the workbook's own worked example."""
import pytest
from mediaopt.examples import worked_example
from mediaopt.calculations import full_report

R = full_report(**worked_example())


def test_report_has_both_pathways_and_the_checks():
    assert set(R) >= {"shared", "design", "measured", "checks", "issues"}


def test_shared_inventory_is_the_only_thing_both_pathways_use():
    s = R["shared"]
    assert s["carbon_g_per_L"] > 0
    assert s["substrate_delivered_g_L"] == pytest.approx(
        s["carbon_g_per_L"] / s["substrate_carbon_fraction"], rel=1e-12)


def test_carbon_efficiency_derived_not_guessed():
    assert R["shared"]["carbon_efficiency"] == pytest.approx(0.480486, abs=1e-5)


def test_measured_carbon_balance_closes():
    assert 0.95 <= R["measured"]["carbon"]["carbon_recovery"] <= 1.05
    assert R["measured"]["carbon"]["verdict"].startswith("CLOSED")


def test_electron_balance_is_reported_independently():
    """It must not be quietly tuned to agree - it shares no data with the carbon one."""
    eb = R["measured"]["electrons"]
    assert eb["ratio"] is not None
    assert "PREDICTED" in eb["verdict"] or "AGREES" in eb["verdict"]


def test_oxygen_feasibility_is_decided():
    k = R["design"]["kla"]
    assert k["kLa_required"] > 0
    assert k["verdict"].startswith(("OK", "OXYGEN-LIMITED"))
    assert k["max_biomass_g_L"] is not None and k["max_mu"] is not None


def test_missing_productivity_is_surfaced_not_silently_ignored():
    """Two byproducts have no productivity, so they contribute nothing to gas demand."""
    assert len(R["design"]["product_rates"]["without_productivity"]) == 2
    assert any(i["field"] == "productivity" for i in R["issues"])


def test_by_difference_cross_check_runs():
    assert R["checks"]["product_by_difference"]["implied_titre_g_L"] is not None


def test_mismatched_recipe_is_caught_at_entry():
    """A feed from a different experiment: every assay fine, the balance impossible.

    This is the failure the spreadsheet could not detect, and the reason the validation
    layer exists.
    """
    kw = worked_example()
    for c in kw["feed"].components:
        if c.compound.startswith("Glucose"):
            c.g_per_L = 500.0          # the wrong run's feed
    out = full_report(**kw)
    assert any(i["level"] == "error" and i["field"] == "recipe" for i in out["issues"])


@pytest.mark.parametrize("path,expected", [
    ("shared.carbon_g_per_L",                            32.8816794167561),
    ("shared.substrate_delivered_g_L",                   82.2000920962049),
    ("measured.volume_basis_factor",                      0.924435215687499),
    ("measured.carbon.substrate_consumed_g_L",           82.0500920962049),
    ("measured.carbon.carbon_consumed_g_L",              32.8216764193538),
    ("measured.carbon.biomass_carbon_g_L",               10.5024188696965),
    ("measured.carbon.product_carbon_g_L",                7.30565145657125),
    ("measured.carbon.co2_carbon_g_L",                   15.01375),
    ("measured.carbon.carbon_accounted_g_L",             32.8218203262677),
    ("measured.carbon.carbon_recovery",                   1.00000438450834),
    ("measured.electrons.electrons_in_mol_L",            10.9305391455678),
    ("measured.electrons.o2_predicted_mmol_L",         1293.39870789421),
    ("measured.electrons.ratio",                          0.862265805262807),
    ("design.kla.kLa_required",                         886.961748213687),
])
def test_full_report_matches_the_workbook(path, expected):
    """End-to-end against the spreadsheet, to nine significant figures."""
    v = R
    for k in path.split("."):
        v = v[k]
    assert v == pytest.approx(expected, rel=1e-9)
