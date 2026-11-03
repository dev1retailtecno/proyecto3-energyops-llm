import pytest
import app
from query_understanding import normalize_query, explicit_intent


@pytest.mark.parametrize('question,start,hours',[
    ('bateria el 03/10/2026 a las 12am por 45 minutos','2026-10-03T00:00:00-06:00',.75),
    ('sin red hoy a las 12pm durante 120 minutos','2026-11-02T12:00:00-06:00',2),
    ('bateria ayer a las 7pm durante tres horas','2026-11-01T19:00:00-06:00',3),
])
def test_date_clock_and_duration_units(question,start,hours):
    args=app.extract_arguments(question,'simulate_outage','2026-11-02')
    assert args['start']==start
    assert args['horizon_hours']==hours


def test_supported_typos_do_not_erase_negation_or_explicit_date():
    q=normalize_query('No optimisa nada; resum consmo del 03/10/2026')
    assert q.startswith('no optimiza nada;')
    assert 'consumo' in q and '2026-10-03' in q


def test_previous_calendar_week_and_arbitrary_rolling_period():
    previous=app.extract_arguments('consumo semana pasada','get_energy_summary','2026-11-02')
    assert previous['start']=='2026-10-26T00:00:00-06:00'
    assert previous['end']=='2026-11-02T00:00:00-06:00'
    rolling=app.extract_arguments('consumo ultimos 14 dias','get_energy_summary','2026-11-02')
    assert rolling['start']=='2026-10-20T00:00:00-06:00'


def test_invalid_slash_date_cannot_turn_into_default_day():
    with pytest.raises(ValueError,match='fecha no es válida'):
        normalize_query('consumo del 31/02/2026')


def test_all_explicit_circuits_are_preserved():
    args=app.extract_arguments('revisa iluminacion, servidores y bomba ayer','detect_anomalies','2026-11-02')
    assert set(args['meters'])=={'lighting','critical','pump'}


def test_review_respects_negation_and_records_tool_repair():
    name,args,notes=app.review_interpretation('No programes horarios; busco picos raros hoy','optimize_schedule',{'building_id':'demo-building','date':'2026-11-02'},'2026-11-02')
    assert name=='detect_anomalies'
    assert args['target_date']=='2026-11-02'
    assert notes[0]=={'field':'tool','from':'optimize_schedule','to':'detect_anomalies'}
    assert explicit_intent('No inventes cifras; resume el consumo')=='get_energy_summary'
    assert explicit_intent('no quiero horarios solo quiero consumo de ayer')=='get_energy_summary'


def test_review_does_not_invent_an_intent_for_ambiguous_request():
    assert explicit_intent('hazlo ya') is None
    name,args,notes=app.review_interpretation('hazlo ya','clarify',{'message':'¿Qué tarea quieres revisar?'},'2026-11-02')
    assert name=='clarify'
    assert notes==[]


def test_two_different_tasks_are_not_collapsed_by_guard():
    assert explicit_intent('optimiza horarios y simula un apagón') is None
