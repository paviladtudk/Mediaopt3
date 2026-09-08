"""What the recipe delivers, per litre of everything delivered.

This is the one quantity both the design and the measured pathways use. The design
side asks how much biomass it could support; the measured side subtracts the leftover
substrate from it to decide what was consumed. So the recipe silently sets the
denominator of the carbon recovery, and a recipe that does not describe the run makes
every downstream number wrong while every assay is perfectly good.
"""
from __future__ import annotations
from ..models.compounds import CompoundLibrary
from ..models.media import Medium
from ..models.process import ProcessSetup


def _fractions(proc: ProcessSetup) -> dict:
    V = proc.V_delivered
    if V <= 0:
        raise ValueError("no volume delivered - set batch and feed volumes")
    return {"batch": proc.V_batch / V, "feed": proc.V_feed / V}


def delivered_elements(batch: Medium, feed: Medium, proc: ProcessSetup,
                       lib: CompoundLibrary, extra_mmol_per_L: dict | None = None) -> dict:
    """mmol of each element per litre of delivered broth."""
    f = _fractions(proc)
    out: dict = {}
    for med, frac in ((batch, f["batch"]), (feed, f["feed"])):
        for e, v in med.elements_mmol_per_L(lib).items():
            out[e] = out.get(e, 0.0) + v * frac
    for e, v in (extra_mmol_per_L or {}).items():      # titrant contributions
        out[e] = out.get(e, 0.0) + v
    return out


def delivered_carbon(batch: Medium, feed: Medium, proc: ProcessSetup,
                     lib: CompoundLibrary) -> dict:
    """Metabolizable carbon delivered, per litre and in total."""
    f = _fractions(proc)
    per_L = (batch.metabolizable_carbon_g_per_L(lib) * f["batch"]
             + feed.metabolizable_carbon_g_per_L(lib) * f["feed"])
    return {"carbon_g_per_L": per_L,
            "carbon_g_total": per_L * proc.V_delivered / 1000.0,
            "V_delivered_mL": proc.V_delivered}
