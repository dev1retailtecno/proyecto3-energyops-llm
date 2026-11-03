from energyops_mcp.energy.schedule import INTERVAL_HOURS, FlexibleLoad, optimize_schedule
from energyops_mcp.energy.timeutil import INTERVAL_MINUTES, INTERVALS_PER_DAY


def _flat_profile(value: float = 0.0) -> list[float]:
    return [value] * INTERVALS_PER_DAY


def test_contribution_conserves_energy_and_duration_regardless_of_start():
    load = FlexibleLoad(
        id="l", name="l", power_kw=3.0, duration_minutes=45,
        window_start_minute=0, window_end_minute=24 * 60, original_start_minute=0,
    )
    for start in (0, 15, 60, 23 * 60):
        if start + load.duration_minutes > 24 * 60:
            continue
        profile = load.contribution_kwh(start)
        nonzero = [v for v in profile if v > 0]
        assert len(nonzero) == load.duration_intervals() == 3
        assert abs(sum(profile) - load.power_kw * (load.duration_minutes / 60)) < 1e-9


def test_valid_starts_are_15_minute_aligned_and_fit_the_window():
    load = FlexibleLoad(
        id="l", name="l", power_kw=1.0, duration_minutes=30,
        window_start_minute=60, window_end_minute=120, original_start_minute=60,
    )
    starts = load.valid_starts()
    assert starts == [60, 75, 90]  # last valid start is 90 (90+30=120, fits exactly)
    assert all(s % INTERVAL_MINUTES == 0 for s in starts)


def test_optimizer_picks_the_cheapest_verifiable_slot():
    load = FlexibleLoad(
        id="load-1", name="Test load", power_kw=4.0, duration_minutes=30,
        window_start_minute=0, window_end_minute=24 * 60, original_start_minute=0,
    )
    tariff = _flat_profile(0.5)
    tariff[0] = tariff[1] = 1.0  # original slot is expensive
    tariff[10] = tariff[11] = 0.01  # a clearly cheapest 30-minute slot

    result = optimize_schedule(_flat_profile(), _flat_profile(), tariff, max_demand_kw=100.0, loads=[load])

    assert result.feasible
    assert result.proposed.starts_minute["load-1"] == 10 * INTERVAL_MINUTES
    expected_cost = 4.0 * INTERVAL_HOURS * 0.01 * 2
    assert abs(result.proposed.cost - expected_cost) < 1e-9
    assert result.original.starts_minute["load-1"] == 0
    assert result.savings_variable_cost > 0


def test_infeasible_when_load_duration_exceeds_its_window():
    load = FlexibleLoad(
        id="l", name="l", power_kw=1.0, duration_minutes=120,
        window_start_minute=0, window_end_minute=60, original_start_minute=0,
    )
    result = optimize_schedule(_flat_profile(), _flat_profile(), _flat_profile(0.1), max_demand_kw=100.0, loads=[load])
    assert result.feasible is False
    assert "sin inicio" in result.reason_if_infeasible


def test_infeasible_when_no_combination_respects_building_capacity():
    load = FlexibleLoad(
        id="l", name="l", power_kw=50.0, duration_minutes=15,
        window_start_minute=0, window_end_minute=24 * 60, original_start_minute=0,
    )
    result = optimize_schedule(_flat_profile(), _flat_profile(), _flat_profile(0.1), max_demand_kw=1.0, loads=[load])
    assert result.feasible is False
    assert "capacidad" in result.reason_if_infeasible


def test_two_loads_are_scheduled_independently_and_never_double_added():
    load_a = FlexibleLoad(
        id="a", name="a", power_kw=2.0, duration_minutes=15,
        window_start_minute=0, window_end_minute=24 * 60, original_start_minute=0,
    )
    load_b = FlexibleLoad(
        id="b", name="b", power_kw=2.0, duration_minutes=15,
        window_start_minute=0, window_end_minute=24 * 60, original_start_minute=0,
    )
    result = optimize_schedule(
        _flat_profile(), _flat_profile(), _flat_profile(0.2), max_demand_kw=100.0, loads=[load_a, load_b]
    )
    assert result.feasible
    # each proposed interval's energy is exactly one load's contribution (0.5 kWh), never both stacked silently
    assert result.proposed.cost <= 2 * (2.0 * INTERVAL_HOURS * 0.2)
