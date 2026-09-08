"""Volumes, titrants, targets and the vessel.

Every concentration the engine reports is per litre DELIVERED - batch plus feed plus
titrants. That is the only basis on which the recipe and the assays can be compared,
because it is the only volume both of them are defined against.
"""
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class ProcessSetup:
    # volumes, mL, totals for the whole run
    V_batch: float = 0.0
    V_feed: float = 0.0
    V_base: float = 0.0
    V_acid: float = 0.0
    # sampling
    V_sampled: float = 0.0
    CDW_sampled: float = 0.0
    residual_sampled: float = 0.0
    titre_sampled: float | None = None      # None -> assume the final titre (upper bound)
    # design
    target_CDW: float = 0.0                 # g/L delivered
    mu: float = 0.0                         # 1/h at the moment gas demand is asked for
    mS: float = 0.0                         # g substrate / (g CDW . h)
    aerobic: bool = True
    C_star: float = 0.2156                  # mmol O2 / L at saturation
    DO_setpoint_fraction: float = 0.30
    kLa_available: float | None = None      # 1/h
    # measured
    CDW_assay: float = 0.0                  # g/L of HARVEST broth
    residual_substrate: float = 0.0         # g/L at harvest

    @property
    def V_delivered(self) -> float:
        return self.V_batch + self.V_feed + self.V_base + self.V_acid

    @property
    def V_harvest(self) -> float:
        return max(0.0, self.V_delivered - self.V_sampled)

    @property
    def driving_force(self) -> float:
        """C* - C_L, mmol O2/L."""
        return self.C_star * (1 - self.DO_setpoint_fraction)

    @property
    def OTR_available(self) -> float | None:
        """mmol O2 / L / h the vessel can transfer."""
        if self.kLa_available is None:
            return None
        return self.kLa_available * self.driving_force

    def to_delivered_basis(self, harvest_conc: float, sampled_conc: float = 0.0) -> float:
        """Rebase a harvest assay onto the delivered volume.

            C_delivered = (C_harvest * V_harvest + C_sampled * V_sampled) / V_delivered

        With no sampling this returns the assay unchanged. Mixing an assay measured on
        harvest broth with substrate figures defined per delivered litre is the single
        commonest reason a fed-batch balance appears not to close.
        """
        if self.V_delivered <= 0:
            raise ValueError("no volume delivered")
        if self.V_sampled <= 0:
            return harvest_conc
        return (harvest_conc * self.V_harvest + sampled_conc * self.V_sampled) / self.V_delivered
