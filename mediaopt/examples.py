"""The worked example the workbook ships with, as code.

Reproduces the v30 workbook run: E. coli on glucose with succinate as the target and
acetate and lactate as byproducts. Used by the tests and as the default state of the
web app, so the app opens showing a working calculation rather than an empty shell.
"""
from .models import load_compounds, load_organisms, Medium, ProcessSetup, ProductSet
from .models.feedstock import ComplexFeedstock

def worked_example():
    lib, orgs = load_compounds(), load_organisms()
    organism = orgs["Escherichia coli"]
    organism.C_pct_CDW = 48.0510154482554        # from the CHON formula, as the workbook uses

    batch = (Medium("Batch medium")
             .add("Diammonium hydrogen phosphate, (NH4)2HPO4", 4.5)
             .add("Potassium dihydrogen phosphate, KH2PO4", 5.0)
             .add("Ammonium sulfate, (NH4)2SO4", 5.0)
             .add("Magnesium sulfate anhydrous, MgSO4", 0.601815)
             .add("Sodium chloride, NaCl", 0.5)
             .add("Citric acid anhydrous, C6H8O7", 1.0, is_substrate=False)
             .add("Sodium hydroxide, NaOH", 0.6)
             .add("Glucose anhydrous, C6H12O6", 40.0)
             .add("Calcium chloride dihydrate, CaCl2.2H2O", 0.6))
    feed = (Medium("Feed medium")
            .add("Glucose anhydrous, C6H12O6", 102.078)
            .add("Magnesium sulfate heptahydrate, MgSO4.7H2O", 50.0)
            .add("Iron(III) chloride hexahydrate, FeCl3.6H2O", 1.0))

    proc = ProcessSetup(V_batch=80, V_feed=136, V_base=28.2, V_acid=2.15,
                        V_sampled=22, CDW_sampled=5.1, residual_sampled=0.15,
                        CDW_assay=23.5, residual_substrate=0.15,
                        target_CDW=25, mu=0.08, mS=0.02,
                        titre_sampled=3.0,
                        C_star=0.2156, DO_setpoint_fraction=0.30, kLa_available=870)

    products = (ProductSet()
                .add("Succinic acid, C4H6O4", target_g_L=25, Yps=0.51,
                     measured_g_L=15, productivity_g_L_h=0.9, is_target=True)
                .add("Acetic acid, C2H4O2", target_g_L=2.854, Yps=0.40,
                     measured_g_L=3.0, is_target=False)
                .add("Lactic acid, C3H6O3", target_g_L=1.427, Yps=0.45,
                     measured_g_L=1.5, is_target=False))

    # yeast extract, characterised by analysis. 5.1432 g C/L delivered is what the
    # workbook's Complex Feedstock tab contributes at the doses it specifies. Carried
    # across at full precision rather than re-derived - the feedstock analysis model
    # itself is not yet ported, and rounding it here shifts every downstream number.
    feedstock = ComplexFeedstock(name="Yeast extract", carbon_g_per_L_delivered=5.14315879033898)

    return dict(organism=organism, batch=batch, feed=feed, proc=proc, products=products,
                lib=lib, substrate="Glucose anhydrous, C6H12O6", Yxs=0.40,
                co2_mmol_L=1250, o2_mmol_L=1500, feedstock=feedstock)
