"""Tests for the NEPViewer cloud client."""

from __future__ import annotations

import asyncio
import hashlib
import importlib.util
import json
import sys
import types
from pathlib import Path

PACKAGE_PATH = Path(__file__).parents[1] / "custom_components" / "nepviewer"
package = types.ModuleType("custom_components.nepviewer")
package.__path__ = [str(PACKAGE_PATH)]
sys.modules["custom_components.nepviewer"] = package
for module_name in ("const", "api"):
    spec = importlib.util.spec_from_file_location(
        f"custom_components.nepviewer.{module_name}", PACKAGE_PATH / f"{module_name}.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

from custom_components.nepviewer.api import (
    NepviewerApiClient,
    request_signature,
    serialize_payload,
    site_identifier,
)


class FakeResponse:
    """Minimal aiohttp response stand-in."""

    def __init__(self, status, payload):
        self.status = status
        self._payload = payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return None

    async def json(self, content_type=None):
        return self._payload


class FakeSession:
    """Record requests and return queued responses."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def post(self, url, *, data, headers):
        self.requests.append((url, data, headers))
        return self.responses.pop(0)


def test_signature_matches_web_client_algorithm():
    payload = {"account": "person@example.de", "password": "secret"}
    serialized = serialize_payload(payload)

    assert serialized == '{"account":"person@example.de","password":"secret"}'
    expected = hashlib.md5(serialized.replace("e", "NEP").encode()).hexdigest().upper()
    assert request_signature(serialized) == expected


def test_site_identifier_uses_scalar_sid_not_changing_device_list():
    site = {
        "sid": "DE_example_site",
        "sn": [{"sn": "EXAMPLE123", "now": 14, "lastUpdateCal": "72 minutes ago"}],
    }

    assert site_identifier(site, 0) == "DE_example_site"


def test_site_identifier_ignores_non_scalar_candidates():
    assert site_identifier({"sid": [], "serialNumber": {}}, 2) == "site-2"


def test_login_and_site_request_use_current_headers():
    session = FakeSession(
        [
            FakeResponse(
                200,
                {
                    "code": 200,
                    "data": {
                        "tokenInfo": {"token": "fresh-token"},
                        "userInfo": {"companyId": 23},
                    },
                },
            ),
            FakeResponse(
                200,
                {"code": 200, "data": {"list": [{"id": 42, "now": 123}]}},
            ),
        ]
    )
    client = NepviewerApiClient(session, account="person@example.de", password="secret")

    sites = asyncio.run(client.async_get_sites())

    assert sites == [{"id": 42, "now": 123}]
    login_url, login_body, login_headers = session.requests[0]
    assert login_url.endswith("/v2/sign-in")
    assert login_headers["client"] == "web"
    assert login_headers["oem"] == "NEP"
    assert login_headers["sign"] == request_signature(login_body.decode())
    sites_url, sites_body, sites_headers = session.requests[1]
    assert sites_url.endswith("/v2/site/listWithSN")
    assert sites_headers["Authorization"] == "fresh-token"
    assert sites_headers["app"] == "23"
    assert sites_headers["sign"] == request_signature(sites_body.decode())
    assert json.loads(sites_body)["page"]["size"] == 100


def test_expired_token_is_renewed_once():
    session = FakeSession(
        [
            FakeResponse(401, {"code": 401, "msg": "expired"}),
            FakeResponse(
                200,
                {
                    "code": 200,
                    "data": {
                        "tokenInfo": {"token": "renewed-token"},
                        "userInfo": {},
                    },
                },
            ),
            FakeResponse(200, {"code": 200, "data": {"list": []}}),
        ]
    )
    client = NepviewerApiClient(
        session,
        account="person@example.de",
        password="secret",
        token="expired-token",
    )

    assert asyncio.run(client.async_get_sites()) == []
    assert len(session.requests) == 3
    assert session.requests[0][2]["Authorization"] == "expired-token"
    assert session.requests[2][2]["Authorization"] == "renewed-token"


def test_device_details_are_cached_between_polls():
    session = FakeSession(
        [
            FakeResponse(
                200,
                {
                    "code": 200,
                    "data": {
                        "model": "BDM-600X",
                        "version": "8a01",
                        "timezone": "Europe/Berlin",
                    },
                },
            )
        ]
    )
    client = NepviewerApiClient(session, token="valid-token")

    first = asyncio.run(client.async_get_device_detail("EXAMPLE123"))
    second = asyncio.run(client.async_get_device_detail("EXAMPLE123"))

    assert first == second
    assert first["model"] == "BDM-600X"
    assert len(session.requests) == 1
    url, body, _headers = session.requests[0]
    assert url.endswith("/v2/device/detail")
    assert json.loads(body) == {"sn": "EXAMPLE123"}


def test_device_overview_exposes_production_and_environmental_values():
    session = FakeSession(
        [
            FakeResponse(
                200,
                {
                    "code": 200,
                    "data": {
                        "production": {"month": "6.6", "total": "7.2"},
                        "environmentalBenefit": {"co2": "7.24"},
                    },
                },
            )
        ]
    )
    client = NepviewerApiClient(session, token="valid-token")

    overview = asyncio.run(client.async_get_device_overview("EXAMPLE123"))

    assert overview["production"]["month"] == "6.6"
    assert overview["environmentalBenefit"]["co2"] == "7.24"
    url, body, _headers = session.requests[0]
    assert url.endswith("/v2/device/statistics/overview")
    assert json.loads(body) == {"sn": "EXAMPLE123"}
