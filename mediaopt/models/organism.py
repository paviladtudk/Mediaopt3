"""Biomass composition: mineral content as % of dry weight, and the CHON formula.

These come from DIFFERENT kinds of measurement and need not agree. The engine keeps
them separate rather than forcing one onto the other, and
``consistency_checks.compare_biomass_descriptions`` quantifies the gap.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
import csv

DATA = Path(__file__).resolve().parent.parent / "data"
MINERALS = ["N", "P", "S", "K", "Mg", "Ca", "Fe", "Zn", "Mn", "Cu", "Mo", "Co", "Ni", "B"]


@dataclass
class Organism:
    name: str
    C_pct_CDW: float            # carbon as % of dry weight, used by the carbon balance
    H_C: float                  # hydrogen atoms per carbon
    O_C: float
    N_C: float
    minerals_pct_CDW: dict = field(default_factory=dict)
    source: str = ""

    @property
    def gamma_X(self) -> float:
        """Electrons per C-mol of biomass."""
        return 4 + self.H_C - 2 * self.O_C - 3 * self.N_C

    @property
    def MW_Cmol(self) -> float:
        """Grams per C-mol of the CHON formula (ash-free)."""
        return 12.011 + self.H_C * 1.008 + self.O_C * 15.999 + self.N_C * 14.007

    @property
    def wCx(self) -> float:
        """g carbon per g dry weight."""
        return self.C_pct_CDW / 100.0

    @property
    def electrons_per_gram(self) -> float:
        return self.gamma_X / self.MW_Cmol

    @property
    def CN_molar(self) -> float | None:
        """Carbon per nitrogen in the cell, by atom count."""
        n = self.minerals_pct_CDW.get("N")
        if not n:
            return None
        return (self.C_pct_CDW / 12.011) / (n / 14.007)

    def yield_max_on_carbon(self) -> float:
        """g dry weight per g carbon if no carbon were respired. An upper bound."""
        return 100.0 / self.C_pct_CDW

    def carbon_efficiency_from_Yxs(self, Yxs: float, wCs: float) -> float:
        """Fraction of consumed substrate carbon ending in biomass, from a measured yield.

            eta_C = Yx/s * w_C,X / w_C,S

        Preferred over guessing the efficiency: it is a rearrangement of the definition,
        and it round-trips - feeding it back through yield_on_substrate returns Yx/s.
        """
        if wCs <= 0:
            raise ValueError("substrate carbon fraction must be positive")
        return Yxs * self.wCx / wCs

    def yield_on_substrate(self, eta_C: float, wCs: float) -> float:
        """g dry weight per g substrate, from the carbon efficiency."""
        return self.yield_max_on_carbon() * eta_C * wCs


class OrganismLibrary(dict):
    pass


def load_organisms(path: Path | str | None = None) -> OrganismLibrary:
    path = Path(path) if path else DATA / "organisms.csv"
    lib = OrganismLibrary()
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if not row.get("C_pct_CDW"):
                continue
            mins = {}
            for m in MINERALS:
                v = row.get(f"{m}_pct_CDW", "")
                if v not in (None, ""):
                    mins[m] = float(v)
            lib[row["name"]] = Organism(
                name=row["name"], C_pct_CDW=float(row["C_pct_CDW"]),
                H_C=float(row["H_C"]), O_C=float(row["O_C"]), N_C=float(row["N_C"]),
                minerals_pct_CDW=mins, source=row.get("source", ""))
    return lib
