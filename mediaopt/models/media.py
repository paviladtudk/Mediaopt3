"""A medium: a list of components at g/L, plus the elemental totals they deliver."""
from __future__ import annotations
from dataclasses import dataclass, field
from .compounds import CompoundLibrary, C_ATOMIC


@dataclass
class MediumComponent:
    compound: str
    g_per_L: float
    is_substrate: bool = True   # False for carbon the organism cannot grow on (citrate, bicarbonate)


@dataclass
class Medium:
    name: str = ""
    components: list = field(default_factory=list)

    def add(self, compound: str, g_per_L: float, is_substrate: bool = True) -> "Medium":
        self.components.append(MediumComponent(compound, g_per_L, is_substrate))
        return self

    def elements_mmol_per_L(self, lib: CompoundLibrary) -> dict:
        out: dict = {}
        for c in self.components:
            if not c.g_per_L:
                continue
            for e, v in lib.get_or_raise(c.compound).element_mmol_per_L(c.g_per_L).items():
                out[e] = out.get(e, 0.0) + v
        return out

    def metabolizable_carbon_g_per_L(self, lib: CompoundLibrary) -> float:
        """g carbon per litre OF THIS MEDIUM that the organism can actually grow on.

        Components flagged is_substrate=False are excluded: their carbon is delivered
        but never consumed, so counting it inflates the denominator of every yield.
        """
        return sum(lib.get_or_raise(c.compound).carbon_fraction * c.g_per_L
                   for c in self.components if c.is_substrate and c.g_per_L)
