"""Turn posted form fields into engine objects, and back again.

Every value the user types arrives as a string. This module is the only place that
converts, and it is deliberately forgiving in one direction only: a blank stays None
rather than becoming zero, because "not entered" and "zero" mean different things to
the engine - a blank trace element is NOT RANKED, a zero is genuinely absent.
"""
from __future__ import annotations
from .models import (load_compounds, load_organisms, Medium, ProcessSetup,
                     ProductSet, ComplexFeedstock, Organism)
from .models.organism import MINERALS
from .models.organism import MINERALS as _M

COMPOUNDS = load_compounds()
ORGANISMS = load_organisms()

STEPS = [("organism", "Organism"), ("media", "Media"), ("process", "Process"),
         ("product", "Product"), ("results", "Results")]


def num(v, default=None):
    """A blank stays None. Only a real number becomes a number."""
    if v is None:
        return default
    v = str(v).strip().replace(",", ".")
    if v == "":
        return default
    try:
        return float(v)
    except ValueError:
        return default


def blank_draft() -> dict:
    return {"organism": {}, "batch": [], "feed": [], "feedstock": {},
            "process": {}, "products": [], "gas": {}, "substrate": ""}


# --------------------------------------------------------------------- parsing
def parse_organism(form) -> dict:
    d = {"name": form.get("organism_name", "").strip(),
         "source": form.get("source", "library"),
         "C_pct": num(form.get("C_pct")), "H_C": num(form.get("H_C")),
         "O_C": num(form.get("O_C")), "N_C": num(form.get("N_C")),
         "Yxs": num(form.get("Yxs")), "minerals": {}}
    for m in MINERALS:
        v = num(form.get(f"min_{m}"))
        if v is not None:
            d["minerals"][m] = v
    return d


def _rows(form, prefix) -> list:
    out = []
    for name, gl, sub in zip(form.getlist(f"{prefix}_compound"),
                             form.getlist(f"{prefix}_g_per_L"),
                             _checkbox_list(form, prefix, len(form.getlist(f"{prefix}_compound")))):
        name = (name or "").strip()
        v = num(gl)
        if name and v is not None:
            out.append({"compound": name, "g_per_L": v, "is_substrate": sub})
    return out


def _checkbox_list(form, prefix, n) -> list:
    """Unchecked boxes are not posted, so read an explicit hidden index instead."""
    marked = set(form.getlist(f"{prefix}_is_substrate"))
    return [str(i) in marked for i in range(n)]


def parse_media(form) -> dict:
    fs = {"name": form.get("fs_name", "").strip(),
          "carbon_g_per_L": num(form.get("fs_carbon"), 0.0) or 0.0,
          "include": form.get("fs_include") == "on"}
    return {"batch": _rows(form, "batch"), "feed": _rows(form, "feed"),
            "feedstock": fs, "substrate": form.get("substrate", "").strip()}


def parse_process(form) -> dict:
    keys = ["V_batch", "V_feed", "V_base", "V_acid", "V_sampled", "CDW_sampled",
            "residual_sampled", "titre_sampled", "target_CDW", "mu", "mS", "C_star",
            "DO_setpoint_fraction", "kLa_available", "CDW_assay", "residual_substrate"]
    d = {k: num(form.get(k)) for k in keys}
    d["aerobic"] = form.get("aerobic", "aerobic") == "aerobic"
    return d


def parse_products(form) -> dict:
    prods = []
    names = form.getlist("p_compound")
    tgt_roles = set(form.getlist("p_is_target"))
    intra = set(form.getlist("p_intracellular"))
    for i, name in enumerate(names):
        name = (name or "").strip()
        if not name:
            continue
        prods.append({
            "compound": name,
            "target_g_L": num(form.getlist("p_target")[i], 0.0) or 0.0,
            "Yps": num(form.getlist("p_Yps")[i]),
            "measured_g_L": num(form.getlist("p_measured")[i], 0.0) or 0.0,
            "productivity_g_L_h": num(form.getlist("p_productivity")[i]),
            "is_target": str(i) in tgt_roles,
            "intracellular": str(i) in intra})
    gas = {"co2_mmol_L": num(form.get("co2_mmol_L"), 0.0) or 0.0,
           "o2_mmol_L": num(form.get("o2_mmol_L"))}
    return {"products": prods, "gas": gas}


# ------------------------------------------------------------------- to engine
def build(draft: dict):
    """Draft dict -> engine objects. Raises ValueError with a readable message."""
    o = draft.get("organism") or {}
    if not o.get("name"):
        raise ValueError("Pick an organism on step 1.")
    if o.get("source") == "library" and o["name"] in ORGANISMS:
        base = ORGANISMS[o["name"]]
        organism = Organism(name=base.name, C_pct_CDW=o.get("C_pct") or base.C_pct_CDW,
                            H_C=o.get("H_C") or base.H_C, O_C=o.get("O_C") or base.O_C,
                            N_C=o.get("N_C") or base.N_C,
                            minerals_pct_CDW={**base.minerals_pct_CDW, **o.get("minerals", {})},
                            source=base.source)
    else:
        missing = [k for k in ("C_pct", "H_C", "O_C", "N_C") if o.get(k) in (None, "")]
        if missing:
            raise ValueError("Your own organism needs carbon %, H/C, O/C and N/C on step 1.")
        organism = Organism(name=o["name"], C_pct_CDW=o["C_pct"], H_C=o["H_C"],
                            O_C=o["O_C"], N_C=o["N_C"],
                            minerals_pct_CDW=o.get("minerals", {}), source="entered by hand")

    batch, feed = Medium("Batch"), Medium("Feed")
    for r in draft.get("batch", []):
        batch.add(r["compound"], r["g_per_L"], r.get("is_substrate", True))
    for r in draft.get("feed", []):
        feed.add(r["compound"], r["g_per_L"], r.get("is_substrate", True))
    if not batch.components and not feed.components:
        raise ValueError("Add at least one medium component on step 2.")

    substrate = draft.get("substrate") or ""
    if not substrate:
        raise ValueError("Choose which carbon source the yields are reported against, on step 2.")
    if substrate not in COMPOUNDS:
        raise ValueError(f"{substrate!r} is not in the compound library.")

    fs = draft.get("feedstock") or {}
    feedstock = ComplexFeedstock(name=fs.get("name", ""),
                                 carbon_g_per_L_delivered=fs.get("carbon_g_per_L", 0.0) or 0.0,
                                 include=bool(fs.get("include"))) if fs.get("include") else None

    p = draft.get("process") or {}
    if not (p.get("V_batch") or p.get("V_feed")):
        raise ValueError("Enter the batch and feed volumes on step 3.")
    proc = ProcessSetup(
        V_batch=p.get("V_batch") or 0.0, V_feed=p.get("V_feed") or 0.0,
        V_base=p.get("V_base") or 0.0, V_acid=p.get("V_acid") or 0.0,
        V_sampled=p.get("V_sampled") or 0.0, CDW_sampled=p.get("CDW_sampled") or 0.0,
        residual_sampled=p.get("residual_sampled") or 0.0,
        titre_sampled=p.get("titre_sampled"),
        target_CDW=p.get("target_CDW") or 0.0, mu=p.get("mu") or 0.0, mS=p.get("mS") or 0.0,
        aerobic=p.get("aerobic", True), C_star=p.get("C_star") or 0.2156,
        DO_setpoint_fraction=p.get("DO_setpoint_fraction") if p.get("DO_setpoint_fraction") is not None else 0.30,
        kLa_available=p.get("kLa_available"),
        CDW_assay=p.get("CDW_assay") or 0.0,
        residual_substrate=p.get("residual_substrate") or 0.0)

    products = ProductSet()
    for r in draft.get("products", []):
        products.add(r["compound"], target_g_L=r.get("target_g_L", 0.0), Yps=r.get("Yps"),
                     measured_g_L=r.get("measured_g_L", 0.0),
                     productivity_g_L_h=r.get("productivity_g_L_h"),
                     is_target=r.get("is_target", True),
                     intracellular=r.get("intracellular", False))

    g = draft.get("gas") or {}
    Yxs = o.get("Yxs")
    if not Yxs or Yxs <= 0:
        raise ValueError("Enter the biomass yield Yx/s on step 1 - the carbon efficiency "
                         "is derived from it.")
    return dict(organism=organism, batch=batch, feed=feed, proc=proc, products=products,
                lib=COMPOUNDS, substrate=substrate, Yxs=Yxs,
                co2_mmol_L=g.get("co2_mmol_L", 0.0), o2_mmol_L=g.get("o2_mmol_L"),
                feedstock=feedstock)
MINERALS = _M
