"""Tests for energy.battery, anchored on the project's own acceptance scenario:
a 10 kWh battery, 100% SOC, 20% reserve, ideal efficiency, a steady 2 kW load
and no solar must yield exactly 4 hours of autonomy (8 kWh usable / 2 kW).
"""

from energyops_mcp.energy.battery import Battery, simulate_outage
from energyops_mcp.energy.timeutil import INTERVAL_MINUTES

INTERVAL_HOURS = INTERVAL_MINUTES / 60


def _ideal_battery(**overrides):
    defaults = {
        "id": "b1",
        "capacity_kwh": 10.0,
        "initial_soc_fraction": 1.0,
        "reserve_fraction": 0.2,
        "charge_efficiency": 1.0,
        "discharge_efficiency": 1.0,
        "max_charge_kw": 5.0,
        "max_discharge_kw": 5.0,
    }
    defaults.update(overrides)
    return Battery(**defaults)


def test_ideal_battery_four_hour_autonomy_matches_hand_calculation():
    horizon = 40  # 10 hours simulated, comfortably past the expected 4h depletion
    demand = [2.0 * INTERVAL_HOURS] * horizon
    solar = [0.0] * horizon

    result = simulate_outage(demand, solar, _ideal_battery())

    assert result.depleted_reason == "energy_exhausted"
    assert result.autonomy_minutes == 4 * 60
    assert result.autonomy_is_lower_bound is False


def test_autonomy_is_reported_as_lower_bound_when_horizon_survived():
    horizon = 4  # only 1 hour simulated; the battery easily lasts that long
    demand = [2.0 * INTERVAL_HOURS] * horizon
    solar = [0.0] * horizon

    result = simulate_outage(demand, solar, _ideal_battery())

    assert result.depleted_reason is None
    assert result.autonomy_is_lower_bound is True
    assert result.autonomy_minutes == horizon * INTERVAL_MINUTES


def test_power_insufficient_is_distinguished_from_energy_exhausted():
    # Plenty of stored energy, but the discharge power limit can't cover the spike.
    battery = _ideal_battery(max_discharge_kw=1.0)  # 0.25 kWh/interval ceiling
    demand = [2.0 * INTERVAL_HOURS]  # needs 0.5 kWh this interval
    solar = [0.0]

    result = simulate_outage(demand, solar, battery)

    assert result.depleted_reason == "power_insufficient"
    assert result.timeline[0].limited_by == "power"


def test_solar_surplus_beyond_charge_capacity_is_curtailed_and_balance_conserved():
    battery = _ideal_battery(capacity_kwh=1.0, initial_soc_fraction=1.0, max_charge_kw=100.0)
    demand = [0.5]
    solar = [3.0]

    result = simulate_outage(demand, solar, battery)

    assert result.total_solar_used_kwh == 0.5
    assert result.total_solar_curtailed_kwh == 2.5
    assert abs(result.total_solar_used_kwh + result.total_solar_curtailed_kwh - result.total_solar_kwh) < 1e-9


def test_critical_only_demand_survives_at_least_as_long_as_full_building():
    battery = _ideal_battery()
    horizon = 40
    full_building = [3.0 * INTERVAL_HOURS] * horizon
    critical_only = [1.0 * INTERVAL_HOURS] * horizon
    solar = [0.0] * horizon

    full_result = simulate_outage(full_building, solar, battery)
    critical_result = simulate_outage(critical_only, solar, battery)

    assert critical_result.autonomy_minutes >= full_result.autonomy_minutes
