"""Freeze the original regression scenarios independently of the delivery date."""
from datetime import date
import pytest
import app
import live_data

@pytest.fixture(autouse=True)
def fixed_original_reference(monkeypatch):
    monkeypatch.setattr(app,'TODAY',date(2026,11,2))
    monkeypatch.setattr(live_data,'TODAY',date(2026,11,2))
