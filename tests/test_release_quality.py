import pytest
import app

def test_uncertain_model_refusal_is_not_overwritten_by_keyword():
    name,args,changes=app.review_interpretation('quiero ahorrar pero no sé qué dato falta','clarify',{'message':'¿Qué fecha quieres analizar?'},'2026-11-02')
    assert name=='clarify'
    assert not changes

def test_excluded_dates_are_not_replaced_by_calendar_default():
    original={'building_id':'demo-building','start':'2026-10-01T00:00:00-06:00','end':'2026-10-30T00:00:00-06:00'}
    _,args,_=app.review_interpretation('consumo de octubre excepto el 2026-10-31','get_energy_summary',original,'2026-11-02')
    assert args==original

async def test_multiple_actions_request_clarification_before_model(monkeypatch):
    async def forbidden(*a,**kw):raise AssertionError('model must not be called')
    monkeypatch.setattr(app,'route',forbidden)
    result=await app.analyze('Optimiza horarios y además simula un apagón hoy')
    assert result['tool']=='clarify'
    assert 'una tarea principal' in result['answer']

def test_incomplete_summary_is_explicit_not_a_complete_building_balance():
    from energyops_mcp.protocol.types import CallToolResult
    r=CallToolResult.ok('consumo 2 kWh',structured={'is_partial':True})
    assert 'Datos incompletos' in app.display_result('get_energy_summary',r)
