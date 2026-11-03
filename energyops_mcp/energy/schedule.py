"""Flexible-load schedule optimization: brute-force search over 15-minute
start times within each load's allowed window.

Modeling choice: the flexible loads are independent of the five measured
circuits (not embedded in any historical meter reading). Their "original"
schedule is just their configured default start time, used only to produce a
before/after comparison, so evaluating a candidate never needs to
subtract-then-re-add energy that was never in the base profile to begin
with -- this keeps the simulation explainable without inventing an
embedding the demo data doesn't actually contain.

Solar generation offsets grid energy interval-by-interval (self-consumption,
no export credit) before the tariff is applied, matching energy.battery's
convention.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import Any

from .timeutil import INTERVAL_MINUTES, INTERVALS_PER_DAY

INTERVAL_HOURS = INTERVAL_MINUTES / 60


@dataclass(frozen=True)
class FlexibleLoad:
    id: str
    name: str
    power_kw: float
    duration_minutes: int
    window_start_minute: int
    window_end_minute: int
    original_start_minute: int

    def duration_intervals(self) -> int:
        return self.duration_minutes // INTERVAL_MINUTES

    def valid_starts(self) -> list[int]:
        """15-min-aligned start minutes such that [start, start+duration) fits the window."""
        starts = []
        m = self.window_start_minute
        while m + self.duration_minutes <= self.window_end_minute:
            starts.append(m)
            m += INTERVAL_MINUTES
        return starts

    def contribution_kwh(self, start_minute: int) -> list[float]:
        profile = [0.0] * INTERVALS_PER_DAY
        start_slot = start_minute // INTERVAL_MINUTES
        for i in range(self.duration_intervals()):
            profile[start_slot + i] = self.power_kw * INTERVAL_HOURS
        return profile


@dataclass
class ScheduleOption:
    starts_minute: dict[str, int]
    cost: float
    max_demand_kw: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "starts_minute": self.starts_minute,
            "cost": round(self.cost, 4),
            "max_demand_kw": round(self.max_demand_kw, 4),
        }


@dataclass
class ScheduleResult:
    feasible: bool
    original: ScheduleOption | None
    proposed: ScheduleOption | None
    savings_variable_cost: float | None
    reason_if_infeasible: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "feasible": self.feasible,
            "original": self.original.to_dict() if self.original else None,
            "proposed": self.proposed.to_dict() if self.proposed else None,
            "savings_variable_cost": (
                round(self.savings_variable_cost, 4) if self.savings_variable_cost is not None else None
            ),
            "reason_if_infeasible": self.reason_if_infeasible,
            "note": (
                "Optimo dentro de las restricciones y resolucion de 15 minutos de este modelo; "
                "no es un optimo universal de todos los esquemas de programacion posibles."
            ),
        }


def _evaluate(
    base_profile_kwh: list[float],
    solar_kwh: list[float],
    tariff_price_per_kwh: list[float],
    max_demand_kw: float,
    loads: list[FlexibleLoad],
    starts: dict[str, int],
) -> ScheduleOption | None:
    total = list(base_profile_kwh)
    for load in loads:
        for i, kwh in enumerate(load.contribution_kwh(starts[load.id])):
            total[i] += kwh

    peak_kw = max(kwh / INTERVAL_HOURS for kwh in total)
    if peak_kw > max_demand_kw + 1e-9:
        return None  # exceeds building capacity

    cost = sum(max(0.0, total[i] - solar_kwh[i]) * tariff_price_per_kwh[i] for i in range(INTERVALS_PER_DAY))
    return ScheduleOption(starts_minute=dict(starts), cost=cost, max_demand_kw=peak_kw)


def optimize_schedule(
    base_profile_kwh: list[float],
    solar_kwh: list[float],
    tariff_price_per_kwh: list[float],
    max_demand_kw: float,
    loads: list[FlexibleLoad],
) -> ScheduleResult:
    if not (len(base_profile_kwh) == len(solar_kwh) == len(tariff_price_per_kwh) == INTERVALS_PER_DAY):
        raise ValueError(f"profiles must have exactly {INTERVALS_PER_DAY} entries (15-minute resolution, one day)")
    if not loads:
        raise ValueError("at least one flexible load is required")

    original_starts = {load.id: load.original_start_minute for load in loads}
    original = _evaluate(base_profile_kwh, solar_kwh, tariff_price_per_kwh, max_demand_kw, loads, original_starts)

    per_load_starts = [load.valid_starts() for load in loads]
    if any(not starts for starts in per_load_starts):
        empty = [load.name for load, starts in zip(loads, per_load_starts) if not starts]
        return ScheduleResult(
            feasible=False,
            original=original,
            proposed=None,
            savings_variable_cost=None,
            reason_if_infeasible=f"sin inicio valido dentro de la ventana permitida para: {', '.join(empty)}",
        )

    best: ScheduleOption | None = None
    best_key: tuple[float, float, int] | None = None
    for combo in product(*per_load_starts):
        starts = {load.id: start for load, start in zip(loads, combo)}
        option = _evaluate(base_profile_kwh, solar_kwh, tariff_price_per_kwh, max_demand_kw, loads, starts)
        if option is None:
            continue
        key = (option.cost, option.max_demand_kw, sum(starts.values()))
        if best_key is None or key < best_key:
            best, best_key = option, key

    if best is None:
        return ScheduleResult(
            feasible=False,
            original=original,
            proposed=None,
            savings_variable_cost=None,
            reason_if_infeasible="ninguna combinacion de inicios respeta la capacidad maxima del edificio",
        )

    savings = (original.cost - best.cost) if original is not None else None
    return ScheduleResult(feasible=True, original=original, proposed=best, savings_variable_cost=savings, reason_if_infeasible=None)
