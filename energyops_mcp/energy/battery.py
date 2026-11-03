"""Battery + solar autonomy simulation during a simulated outage.

Interval-by-interval energy balance: demand is first served by solar
generation, then by the battery (bounded by both remaining usable energy AND
instantaneous charge/discharge power limits), and any shortfall is unmet
demand. Solar surplus beyond demand and battery charge headroom is curtailed
(a real inverter cannot push it onto a dead grid during an outage).
"energy_exhausted" (the battery is empty down to its reserve) and
"power_insufficient" (there is stored energy left, but the discharge power
limit can't cover an instantaneous spike) are reported as distinct failure
modes.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from .timeutil import INTERVAL_MINUTES

INTERVAL_HOURS = INTERVAL_MINUTES / 60


@dataclass(frozen=True)
class Battery:
    id: str
    capacity_kwh: float
    initial_soc_fraction: float
    reserve_fraction: float
    charge_efficiency: float
    discharge_efficiency: float
    max_charge_kw: float
    max_discharge_kw: float


@dataclass
class IntervalRecord:
    index: int
    demand_kwh: float
    solar_kwh: float
    solar_used_kwh: float
    solar_curtailed_kwh: float
    battery_out_kwh: float
    unmet_kwh: float
    soc_fraction: float
    limited_by: str | None


@dataclass
class BatterySimResult:
    autonomy_minutes: int
    autonomy_is_lower_bound: bool
    horizon_minutes: int
    depleted_reason: str | None  # None | "energy_exhausted" | "power_insufficient"
    total_solar_kwh: float
    total_solar_used_kwh: float
    total_solar_curtailed_kwh: float
    total_unmet_kwh: float
    timeline: list[IntervalRecord]

    def to_dict(self, include_timeline: bool = True) -> dict[str, Any]:
        d: dict[str, Any] = {
            "autonomy_minutes": self.autonomy_minutes,
            "autonomy_is_lower_bound": self.autonomy_is_lower_bound,
            "horizon_minutes": self.horizon_minutes,
            "depleted_reason": self.depleted_reason,
            "total_solar_kwh": round(self.total_solar_kwh, 4),
            "total_solar_used_kwh": round(self.total_solar_used_kwh, 4),
            "total_solar_curtailed_kwh": round(self.total_solar_curtailed_kwh, 4),
            "total_unmet_kwh": round(self.total_unmet_kwh, 4),
        }
        if self.autonomy_is_lower_bound:
            d["note"] = (
                "la bateria sobrevivio todo el horizonte simulado sin agotarse; "
                "autonomy_minutes es un limite inferior, no la duracion exacta"
            )
        if include_timeline:
            d["timeline"] = [
                {
                    "interval": r.index,
                    "demand_kwh": round(r.demand_kwh, 4),
                    "solar_used_kwh": round(r.solar_used_kwh, 4),
                    "solar_curtailed_kwh": round(r.solar_curtailed_kwh, 4),
                    "battery_out_kwh": round(r.battery_out_kwh, 4),
                    "unmet_kwh": round(r.unmet_kwh, 4),
                    "soc_fraction": round(r.soc_fraction, 4),
                    "limited_by": r.limited_by,
                }
                for r in self.timeline
            ]
        return d


def simulate_outage(demand_kwh: list[float], solar_kwh: list[float], battery: Battery) -> BatterySimResult:
    """demand_kwh/solar_kwh: one entry per 15-min interval, for the simulated horizon."""
    if len(demand_kwh) != len(solar_kwh):
        raise ValueError("demand_kwh and solar_kwh must have the same length")
    if not demand_kwh or any(not math.isfinite(x) or x < 0 for x in [*demand_kwh, *solar_kwh]):
        raise ValueError("nonempty finite nonnegative energy profiles required")
    if not all(math.isfinite(v) for v in [battery.capacity_kwh, battery.initial_soc_fraction,
            battery.reserve_fraction, battery.charge_efficiency, battery.discharge_efficiency,
            battery.max_charge_kw, battery.max_discharge_kw]):
        raise ValueError("finite battery parameters required")
    if not (battery.capacity_kwh > 0 and 0 <= battery.reserve_fraction <= battery.initial_soc_fraction <= 1
            and 0 < battery.charge_efficiency <= 1 and 0 < battery.discharge_efficiency <= 1
            and battery.max_charge_kw >= 0 and battery.max_discharge_kw >= 0):
        raise ValueError("invalid battery capacity, state of charge, efficiency or power")
    horizon = len(demand_kwh)

    soc_kwh = battery.capacity_kwh * battery.initial_soc_fraction
    reserve_kwh = battery.capacity_kwh * battery.reserve_fraction
    max_charge_kwh = battery.max_charge_kw * INTERVAL_HOURS
    max_discharge_kwh = battery.max_discharge_kw * INTERVAL_HOURS

    timeline: list[IntervalRecord] = []
    total_solar = total_solar_used = total_curtailed = total_unmet = 0.0
    depleted_reason: str | None = None
    autonomy_intervals = horizon

    for i in range(horizon):
        demand = demand_kwh[i]
        solar = solar_kwh[i]
        total_solar += solar

        solar_used = min(solar, demand)
        remaining_demand = demand - solar_used
        solar_surplus = solar - solar_used

        charge_room_kwh = max(0.0, battery.capacity_kwh - soc_kwh)
        max_charge_in_by_room = charge_room_kwh / battery.charge_efficiency if battery.charge_efficiency > 0 else 0.0
        charge_in = min(solar_surplus, max_charge_kwh, max_charge_in_by_room)
        soc_kwh += charge_in * battery.charge_efficiency
        curtailed = solar_surplus - charge_in

        battery_out = 0.0
        limited_by: str | None = None
        if remaining_demand > 1e-9:
            available_stored = max(0.0, soc_kwh - reserve_kwh)
            max_by_power = max_discharge_kwh * battery.discharge_efficiency
            max_by_energy = available_stored * battery.discharge_efficiency
            battery_out = max(0.0, min(remaining_demand, max_by_power, max_by_energy))
            soc_kwh -= (battery_out / battery.discharge_efficiency) if battery.discharge_efficiency > 0 else 0.0
            remaining_demand -= battery_out

            if remaining_demand > 1e-9:
                limited_by = "energy" if max_by_energy < max_by_power - 1e-9 else "power"

        unmet = max(0.0, remaining_demand)
        total_solar_used += solar_used
        total_curtailed += curtailed
        total_unmet += unmet

        timeline.append(
            IntervalRecord(
                index=i,
                demand_kwh=demand,
                solar_kwh=solar,
                solar_used_kwh=solar_used,
                solar_curtailed_kwh=curtailed,
                battery_out_kwh=battery_out,
                unmet_kwh=unmet,
                soc_fraction=(soc_kwh / battery.capacity_kwh) if battery.capacity_kwh > 0 else 0.0,
                limited_by=limited_by,
            )
        )

        if unmet > 1e-9 and depleted_reason is None:
            depleted_reason = "energy_exhausted" if limited_by == "energy" else "power_insufficient"
            autonomy_intervals = i

    return BatterySimResult(
        autonomy_minutes=autonomy_intervals * INTERVAL_MINUTES,
        autonomy_is_lower_bound=depleted_reason is None,
        horizon_minutes=horizon * INTERVAL_MINUTES,
        depleted_reason=depleted_reason,
        total_solar_kwh=total_solar,
        total_solar_used_kwh=total_solar_used,
        total_solar_curtailed_kwh=total_curtailed,
        total_unmet_kwh=total_unmet,
        timeline=timeline,
    )
