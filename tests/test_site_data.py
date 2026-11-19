"""Regression cases from the observed site overview (no credentials)."""
import asyncio
import copy
import importlib.util
from pathlib import Path

from test_nepviewer_api import FakeResponse, FakeSession
from custom_components.nepviewer.api import NepviewerApiClient, NepviewerError

spec = importlib.util.spec_from_file_location(
    'custom_components.nepviewer.data',
    Path(__file__).parents[1] / 'custom_components/nepviewer/data.py')
data = importlib.util.module_from_spec(spec)
spec.loader.exec_module(data)

OVERVIEW = {
    'selected': {'local_electric_price': 0.24, 'currency_unit': 'USD'},
    'statisticsProduction': {
        'today': '8.682', 'todayUnit': 'kWh',
        'yesterday': '6200', 'yesterdayUnit': '',
        'month': '134.8', 'monthUnit': 'kWh',
        'year': '7970.4', 'yearUnit': 'kWh',
        'total': '7993.8', 'totalUnit': 'kWh',
        'totalNow': '2481', 'totalNowUnit': 'W',
        'totalMoney': '1918.4836799999998',
        'todayMoney': '0', 'yesterdayMoney': '0', 'monthMoney': '0',
    },
    'deviceList': [
        {'sn': f'TEST{i}', 'now': str(watts), 'nowUnit': 'W',
         'today': str(energy), 'todayUnit': 'kWh', 'statusTitle': 'online',
         'modelTitle': 'BDM-2000'}
        for i, (watts, energy) in enumerate(zip(
            [286, 267, 249, 299, 436, 543, 220, 181],
            [1.097, 1.166, .967, 1.228, 1.116, 1.058, 1.271, .779]))
    ],
    'statusTitle': 'online', 'lastUpdate': '15/11/2026 15:02',
    'benefit': {'car': '27.73', 'carUnit': 'km(*1000)', 'co2': '8041.64'},
}


def test_correct_site_endpoint_payload_and_eight_devices():
    session = FakeSession([FakeResponse(200, {'code': 200, 'data': OVERVIEW})])
    client = NepviewerApiClient(session, token='test-token')
    result = asyncio.run(client.async_get_site_overview('TEST_SITE'))
    url, payload, _ = session.requests[0]
    assert url == 'https://api.nepviewer.net/v2/site/overview'
    assert payload == b'{"sid":"TEST_SITE"}'
    assert len(result['deviceList']) == 8


def test_real_site_values_and_income():
    site = {'_site_overview': OVERVIEW}
    assert data.site_value(site, 'yesterday') == 6.2
    assert data.site_value(site, 'month') == 134.8
    assert data.site_value(site, 'total') == 7993.8
    assert round(data.income(OVERVIEW, 'month'), 2) == 32.35
    assert round(data.income(OVERVIEW, 'yesterday'), 2) == 1.49
    assert round(data.income(OVERVIEW, 'total'), 2) == 1918.48
    assert len(data.devices(site)) == 8


def test_explicit_units_prevent_double_conversion():
    assert data.energy_kwh({'yesterday': '6.2', 'yesterdayUnit': 'kWh'}, 'yesterday') == 6.2
    assert data.energy_kwh({'month': '134800', 'monthUnit': 'Wh'}, 'month') == 134.8
    assert data.energy_kwh({'total': '7.9938', 'totalUnit': 'MWh'}, 'total') == 7993.8
    assert data.energy_kwh({'month': '134.8', 'monthUnit': 'unexpected'}, 'month') is None
    assert data.energy_kwh({'month': '134.8'}, 'month') is None


def test_missing_or_nonfinite_data_is_not_a_fake_zero():
    assert data.site_value({}, 'yesterday') is None
    assert data.energy_kwh({'today': 'nan', 'todayUnit': 'kWh'}, 'today') is None
    assert data.income({}, 'today') is None
    assert data.number('inf') is None


def test_api_money_is_preserved_and_missing_money_can_be_estimated():
    changed = copy.deepcopy(OVERVIEW)
    changed['statisticsProduction']['monthMoney'] = '30.10'
    assert data.income(changed, 'month') == 30.1
    del changed['statisticsProduction']['monthMoney']
    assert round(data.income(changed, 'month'), 2) == 32.35


def test_bad_overview_rejected_instead_of_reporting_device_data():
    session = FakeSession([FakeResponse(200, {'code': 200, 'data': {'production': {}}})])
    try:
        asyncio.run(NepviewerApiClient(session, token='t').async_get_site_overview('TEST'))
    except NepviewerError:
        pass
    else:
        raise AssertionError('Device response must not be accepted as a site overview')
