"""Input sanity checks, run BEFORE the engine, so a wrong number is caught at entry.

This is the layer the spreadsheet never had. In the workbook a feed concentration from
a different experiment produced a confidently wrong answer four tabs later; here it is
flagged the moment the numbers stop describing one another.
"""
from __future__ import annotations
from dataclasses import dataclass

@dataclass
class ValidationIssue:
    level: str      # "error" | "warning"
    field: str
    message: str


def validate_setup(proc, batch, feed, lib, organism, products=None) -> list:
    out: list = []
    A = out.append

    if proc.V_delivered <= 0:
        A(ValidationIssue("error", "volumes", "No volume delivered - set a batch and feed volume."))
        return out
    if proc.V_sampled > proc.V_delivered:
        A(ValidationIssue("error", "V_sampled",
                          f"You removed more broth ({proc.V_sampled:g} mL) than you delivered "
                          f"({proc.V_delivered:g} mL)."))
    if proc.CDW_sampled > proc.CDW_assay > 0:
        A(ValidationIssue("warning", "CDW_sampled",
                          "Average cell density in the samples exceeds the final assay. Samples "
                          "taken earlier normally held fewer cells - check the average is "
                          "volume-weighted."))
    if not 0 <= proc.DO_setpoint_fraction < 1:
        A(ValidationIssue("error", "DO_setpoint_fraction", "Must be a fraction between 0 and 1."))
    if proc.mu < 0 or proc.mS < 0:
        A(ValidationIssue("error", "rates", "Growth rate and maintenance cannot be negative."))
    if proc.mu > 0 and proc.mS == 0:
        A(ValidationIssue("warning", "mS",
                          "Maintenance is zero. Harmless while cells grow fast, but it becomes the "
                          "dominant oxygen demand at high density or near stationary phase."))

    from .consistency_checks import recipe_matches_run
    r = recipe_matches_run(proc, batch, feed, lib, organism, products)
    if r:
        A(r)

    for med, label in ((batch, "batch medium"), (feed, "feed medium")):
        for c in med.components:
            if c.g_per_L and c.compound not in lib:
                A(ValidationIssue("error", label,
                                  f"{c.compound!r} is not in the compound library, so this row "
                                  f"contributes nothing. Add it to compounds.csv."))
            if c.g_per_L and c.g_per_L < 0:
                A(ValidationIssue("error", label, f"{c.compound}: negative concentration."))

    for p in (products.products if products else []):
        if p.productivity_g_L_h in (None, 0) and p.target_g_L:
            A(ValidationIssue("warning", "productivity",
                              f"{p.compound} has no productivity, so it contributes nothing to gas "
                              f"demand while still counting in the carbon balance."))
        if p.intracellular and p.measured_g_L >= proc.CDW_assay > 0:
            A(ValidationIssue("error", "intracellular",
                              f"{p.compound} is flagged intracellular but its titre is at or above "
                              f"the whole CDW assay."))
    return out
