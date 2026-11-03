import pytest

from energyops_mcp.energy.server import _expand_tariff_bands, _require_complete
from energyops_mcp.energy.timeutil import from_utc_iso


def test_missing_intervals_stop_analysis():
    with pytest.raises(ValueError, match="incomplete readings"):
        _require_complete([], ["critical"], from_utc_iso("2026-03-02T06:00:00+00:00"), 4)


@pytest.mark.parametrize("bands", [
    [{"start_minute": 0, "end_minute": 1440, "price_per_kwh": -1}],
    [{"start_minute": 0, "end_minute": 1440, "price_per_kwh": float("inf")}],
    [{"start_minute": 0, "end_minute": 1440, "price_per_kwh": 1}] * 2,
    [{"start_minute": 1, "end_minute": 1440, "price_per_kwh": 1}],
])
def test_invalid_tariffs_rejected(bands):
    with pytest.raises(ValueError):
        _expand_tariff_bands(bands)
