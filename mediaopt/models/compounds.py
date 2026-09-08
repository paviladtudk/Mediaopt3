"""Compound library: molecular weight, atom counts, degree of reduction.

Degree of reduction gamma counts available electrons, with ammonia as the nitrogen
reference: C +4, H +1, O -2, N -3, S +6, P +5, and +1 or +2 per counter-ion charge
(Na, K, Mg, Ca) less 1 per Cl. Charged organic salts must carry that correction or
their electron content is understated - sodium acetate is 8 electrons per mol, not 7.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
import csv

C_ATOMIC = 12.011
DATA = Path(__file__).resolve().parent.parent / "data"

ELEMENTS = ["C", "N", "P", "S", "K", "Mg", "Ca", "Fe", "Zn", "Mn",
            "Cu", "Mo", "Co", "Ni", "B", "H", "O", "Na", "Cl"]


def gamma_from_atoms(a: dict) -> float:
    """Available electrons per mole, ammonia reference, with counter-ion correction."""
    g = (4 * a.get("C", 0) + a.get("H", 0) - 2 * a.get("O", 0) - 3 * a.get("N", 0)
         + 6 * a.get("S", 0) + 5 * a.get("P", 0)
         + a.get("Na", 0) + a.get("K", 0)
         + 2 * a.get("Mg", 0) + 2 * a.get("Ca", 0)
         - a.get("Cl", 0))
    return float(g)


@dataclass(frozen=True)
class Compound:
    name: str
    mw: float
    atoms: dict = field(default_factory=dict)

    @property
    def carbon_atoms(self) -> float:
        return self.atoms.get("C", 0)

    @property
    def carbon_fraction(self) -> float:
        """g carbon per g compound."""
        return self.carbon_atoms * C_ATOMIC / self.mw if self.mw else 0.0

    @property
    def gamma(self) -> float:
        """Available electrons per mole."""
        return gamma_from_atoms(self.atoms)

    @property
    def gamma_per_cmol(self) -> float | None:
        """Electrons per C-mol. None for a compound with no carbon."""
        return self.gamma / self.carbon_atoms if self.carbon_atoms else None

    @property
    def electrons_per_gram(self) -> float:
        return self.gamma / self.mw if self.mw else 0.0

    def element_mmol_per_L(self, g_per_L: float) -> dict:
        """mmol of each element delivered per litre, at this concentration."""
        mol = g_per_L / self.mw if self.mw else 0.0
        return {e: mol * n * 1000 for e, n in self.atoms.items() if n}


class CompoundLibrary(dict):
    def get_or_raise(self, name: str) -> Compound:
        try:
            return self[name]
        except KeyError:
            raise KeyError(
                f"{name!r} is not in the compound library. Add a row to "
                f"mediaopt/data/compounds.csv (name, mw, atom counts) - the engine "
                f"cannot parse a formula out of a name."
            ) from None


def load_compounds(path: Path | str | None = None) -> CompoundLibrary:
    path = Path(path) if path else DATA / "compounds.csv"
    lib = CompoundLibrary()
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            atoms = {e: float(row[e]) for e in ELEMENTS if row.get(e) not in (None, "", "0")}
            lib[row["name"]] = Compound(row["name"], float(row["mw"]), atoms)
    return lib
