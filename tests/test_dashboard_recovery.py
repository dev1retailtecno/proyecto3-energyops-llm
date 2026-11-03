"""Application continuity, synthetic extension and date boundaries. No paid API calls."""
from datetime import date
import asyncio
import pytest
import app
import live_data
from energyops_mcp.energy.datagen import generate_dataset
from energyops_mcp.protocol.types import CallToolResult


def test_extension_keeps_original_benchmark_readings_unchanged():
    original=generate_dataset()
    extended=generate_dataset(end_day=date(2026,11,2))
    assert extended[:len(original)]==original
    assert len(extended)==173952


def test_overview_period_totals_and_complete_days():
    d=live_data.overview('2026-11-02','week')
    assert d['selection']['start']=='2026-10-27'
    assert d['selection']['end']=='2026-11-02'
    assert d['selection']['readings']==d['selection']['expected_readings']==7*576
    expected=sum(r['consumption_kwh'] for r in d['daily'] if r['day']>='2026-10-27')
    assert d['selection']['consumption_kwh']==pytest.approx(expected,abs=.001)
    month=live_data.overview('2026-11-02','month')
    assert month['selection']['days']==2
    assert month['selection']['readings']==1152


def test_rules_resolve_relative_dates_and_months_without_substitution():
    assert app.extract_arguments('consumo de ayer','get_energy_summary',str(live_data.TODAY))['start']=='2026-11-01T00:00:00-06:00'
    args=app.extract_arguments('consumo de octubre','get_energy_summary',str(live_data.TODAY))
    assert args['start']=='2026-10-01T00:00:00-06:00'
    assert args['end']=='2026-11-01T00:00:00-06:00'
    args=app.extract_arguments('consumo del 2026-10-01 al 2026-10-07','get_energy_summary',str(live_data.TODAY))
    assert args['end']=='2026-10-08T00:00:00-06:00'


async def test_direct_today_and_week_run_real_mcp_without_llm(monkeypatch):
    async def forbidden(*args,**kwargs):raise AssertionError('Direct actions must not call a model')
    monkeypatch.setattr(app,'route',forbidden)
    monkeypatch.setattr(app,'route_local',forbidden)
    result=await app.analyze('Resume el consumo del 2026-11-02','direct','2026-11-02','get_energy_summary','week')
    assert result['tool']=='get_energy_summary'
    assert result['arguments']['start']=='2026-10-27T00:00:00-06:00'
    assert result['data']['consumption_kwh']>0
    assert 'sin LLM' in result['mode']
    assert result['estimated_cost_usd']==0


async def test_remote_failure_recovers_to_local_model_with_notice(monkeypatch):
    async def remote_failure(*args,**kwargs):raise RuntimeError('provider unavailable')
    async def local_success(question,tools,reference_date=None):
        return 'get_energy_summary',app.extract_arguments(question,'get_energy_summary',reference_date),{'input_tokens':23,'output_tokens':5}
    monkeypatch.setattr(app,'route',remote_failure)
    monkeypatch.setattr(app,'route_local',local_success)
    result=await app.analyze('Resume el consumo de hoy','claude',str(live_data.TODAY))
    assert result['tool']=='get_energy_summary'
    assert result['mode'].startswith('Qwen3 local')
    assert 'Claude' in result['notice']
    assert result['data']['consumption_kwh']>0


async def test_both_models_fail_continues_with_honestly_labelled_rules(monkeypatch):
    async def unavailable(*args,**kwargs):raise RuntimeError('provider unavailable')
    monkeypatch.setattr(app,'route',unavailable)
    monkeypatch.setattr(app,'route_local',unavailable)
    result=await app.analyze('Cuánto consumimos esta semana','claude','2026-11-02')
    assert result['tool']=='get_energy_summary'
    assert result['arguments']['start']=='2026-10-27T00:00:00-06:00'
    assert 'sin LLM' in result['mode']
    assert result['data']['consumption_kwh']>0
    assert not result.get('is_error')


async def test_unavailable_or_invalid_date_gives_options_without_model_call(monkeypatch):
    async def forbidden(*args,**kwargs):raise AssertionError('must reject before model use')
    monkeypatch.setattr(app,'route',forbidden)
    for question in ['Consumo del 2030-01-01','Consumo del 2026-02-30']:
        result=await app.analyze(question)
        assert result['tool']=='clarify'
        assert result['recovery']
        assert result['data']=={}
        assert result['suggestions']
        assert not result.get('is_error')


async def test_outage_cannot_silently_extend_past_data_cutoff():
    result=await app.analyze('Simula un apagón el 2026-11-02 a las 18:00 por 24 horas','direct','2026-11-02','simulate_outage')
    assert result['tool']=='clarify'
    assert 'duración' in result['answer']
    assert result['data']=={}


async def test_unknown_question_is_guided_not_fabricated_when_models_fail(monkeypatch):
    async def unavailable(*args,**kwargs):raise RuntimeError('provider unavailable')
    monkeypatch.setattr(app,'route',unavailable)
    monkeypatch.setattr(app,'route_local',unavailable)
    result=await app.analyze('Inventa el consumo de mi casa nueva')
    assert result['tool']=='clarify'
    assert result['data']=={}
    assert len(result['suggestions'])==4


def test_battery_lower_bound_is_preserved_in_display():
    data={'full_building':{'autonomy_minutes':360,'autonomy_is_lower_bound':True},'critical_only':{'autonomy_minutes':360,'autonomy_is_lower_bound':True}}
    answer=app.display_result('simulate_outage',CallToolResult.ok('unused',structured=data))
    assert answer.count('al menos 360')==2


async def test_mcp_disconnect_reconnects_once_and_completes_real_calculation(monkeypatch):
    real_connect=app.connect
    attempts=[]
    class DisconnectOnce:
        def __init__(self,client):self.client=client
        async def list_tools(self):return await self.client.list_tools()
        async def call_tool(self,*args):raise RuntimeError('simulated transport interruption')
        async def aclose(self):await self.client.aclose()
    async def connect_with_interruption(extended=False):
        client=await real_connect(extended)
        attempts.append(client)
        return DisconnectOnce(client) if len(attempts)==1 else client
    monkeypatch.setattr(app,'connect',connect_with_interruption)
    result=await app.analyze('Consumo del 2026-11-02','direct','2026-11-02','get_energy_summary')
    assert result['data']['consumption_kwh']>0
    assert 'Restablecí' in result['notice']
    assert len(attempts)==2


async def test_engine_failure_cache_matches_exact_operation_and_never_other_date(monkeypatch):
    baseline=await app.analyze('Consumo del 2026-10-22','direct','2026-10-22','get_energy_summary')
    real_connect=app.connect
    class Disconnected:
        def __init__(self,client):self.client=client
        async def list_tools(self):return await self.client.list_tools()
        async def call_tool(self,*args):raise RuntimeError('simulated engine outage')
        async def aclose(self):await self.client.aclose()
    async def broken_connect(extended=False):return Disconnected(await real_connect(extended))
    monkeypatch.setattr(app,'connect',broken_connect)
    cached=await app.analyze('Consumo del 2026-10-22','direct','2026-10-22','get_energy_summary')
    assert cached['cached']
    assert cached['data']==baseline['data']
    assert 'sin ejecución nueva' in cached['mode']
    another=await app.analyze('Consumo del 2026-10-21','direct','2026-10-21','get_energy_summary')
    assert another['tool']=='clarify'
    assert another['data']=={}
    assert not another.get('cached')
