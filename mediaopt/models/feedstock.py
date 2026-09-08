"""Complex feedstock: yeast extract, corn steep, hydrolysate.

Characterised by ANALYSIS rather than by formula - there is no chemical formula to look
up, so carbon comes from TOC or a protein/carbohydrate estimate and minerals from ICP-MS.
Kept separate from Medium for exactly that reason: the engine must never pretend it can
derive these from a name.
"""
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class ComplexFeedstock:
    name: str = ""
    carbon_g_per_L_delivered: float = 0.0   # metabolizable carbon it contributes, per delivered litre
    elements_mmol_per_L: dict = field(default_factory=dict)
    bioavailable_fraction: float = 1.0
    include: bool = True
    source: str = "analysis"

    @property
    def carbon(self) -> float:
        return self.carbon_g_per_L_delivered * self.bioavailable_fraction if self.include else 0.0

    @property
    def elements(self) -> dict:
        return self.elements_mmol_per_L if self.include else {}
