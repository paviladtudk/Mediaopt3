"""Products and byproducts: design targets, measured titres, instantaneous productivity."""
from __future__ import annotations
from dataclasses import dataclass, field
from .compounds import CompoundLibrary


@dataclass
class Product:
    compound: str
    target_g_L: float = 0.0        # design titre, delivered basis
    Yps: float | None = None       # g product / g substrate allocated to THIS product
    measured_g_L: float = 0.0      # assay on harvest broth
    productivity_g_L_h: float | None = None   # r_P at the gas-demand timepoint
    is_target: bool = True         # False -> byproduct
    intracellular: bool = False    # True -> already inside the weighed dry cell mass

    def substrate_needed(self) -> float:
        if not self.Yps or self.Yps <= 0:
            return 0.0
        return self.target_g_L / self.Yps


@dataclass
class ProductSet:
    products: list = field(default_factory=list)

    def add(self, *a, **kw) -> "ProductSet":
        self.products.append(Product(*a, **kw))
        return self

    def _sum(self, fn, only_target=False):
        return sum(fn(p) for p in self.products if (p.is_target or not only_target))

    def measured_carbon_g_L(self, lib: CompoundLibrary, factor: float = 1.0) -> float:
        return sum(lib.get_or_raise(p.compound).carbon_fraction * p.measured_g_L * factor
                   for p in self.products)

    def measured_electrons_mol_L(self, lib: CompoundLibrary, factor: float = 1.0) -> float:
        return sum(lib.get_or_raise(p.compound).electrons_per_gram * p.measured_g_L * factor
                   for p in self.products)

    def measured_titre_total(self, factor: float = 1.0) -> float:
        return self._sum(lambda p: p.measured_g_L) * factor

    def measured_titre_target(self, factor: float = 1.0) -> float:
        return sum(p.measured_g_L for p in self.products if p.is_target) * factor

    def intracellular_titre(self) -> float:
        """Product already weighed into the CDW assay, g/L of harvest broth."""
        return sum(p.measured_g_L for p in self.products if p.intracellular)

    def rates(self, lib: CompoundLibrary) -> dict:
        """Instantaneous substrate, carbon and electron rates from the entered productivity.

        A titre is an accumulated amount; gas demand needs a rate. Multiplying a final
        titre by mu asserts the whole inventory is remade every 1/mu hours, which is
        why this takes r_P instead.
        """
        rS = rC = rE = 0.0
        missing = []
        for p in self.products:
            rP = p.productivity_g_L_h
            if rP is None or rP <= 0:
                missing.append(p.compound)
                continue
            c = lib.get_or_raise(p.compound)
            if p.Yps and p.Yps > 0:
                rS += rP / p.Yps
            rC += rP * c.carbon_fraction
            rE += rP * c.electrons_per_gram
        return {"substrate_g_L_h": rS, "carbon_g_L_h": rC,
                "electrons_mol_L_h": rE, "without_productivity": missing}
