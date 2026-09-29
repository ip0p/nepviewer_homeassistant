"""Client for the current NEPViewer v2 web API."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from aiohttp import ClientError, ClientResponse, ClientSession

from .const import (
    API_BASE_URL,
    DEFAULT_COMPANY_ID,
    DEFAULT_LANGUAGE,
    LOGIN_ENDPOINT,
    SITES_ENDPOINT,
)


class NepviewerError(Exception):
    """Base exception raised by the NEPViewer client."""


class NepviewerAuthenticationError(NepviewerError):
    """Raised when NEPViewer rejects the credentials or token."""


class NepviewerConnectionError(NepviewerError):
    """Raised when NEPViewer cannot be reached."""


def site_identifier(site: dict[str, Any], index: int) -> str:
    """Return a stable scalar identifier for a NEPViewer site."""
    for key in ("sid", "siteId", "site_id", "serialNumber"):
        value = site.get(key)
        if isinstance(value, (str, int)) and str(value):
            return str(value)
    return f"site-{index}"


def serialize_payload(payload: dict[str, Any]) -> str:
    """Serialize a request exactly like the NEPViewer web client."""
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def request_signature(serialized_payload: str) -> str:
    """Return the request signature used by the current NEPViewer clients."""
    normalized = serialized_payload.replace(" ", "").replace("\r", "").replace("\n", "")
    normalized = normalized.replace("e", "NEP")
    return hashlib.md5(normalized.encode()).hexdigest().upper()


class NepviewerApiClient:
    """Small asynchronous NEPViewer API client with token renewal."""

    def __init__(
        self,
        session: ClientSession,
        *,
        account: str | None = None,
        password: str | None = None,
        token: str | None = None,
        company_id: int = DEFAULT_COMPANY_ID,
    ) -> None:
        self._session = session
        self._account = account
        self._password = password
        self._token = token
        self._company_id = company_id

    @property
    def account(self) -> str | None:
        """Return the configured account name."""
        return self._account

    async def async_login(self) -> None:
        """Log in and retain the short-lived API token in memory."""
        if not self._account or not self._password:
            raise NepviewerAuthenticationError("NEPViewer credentials are missing")

        response = await self._async_request(
            LOGIN_ENDPOINT,
            {"account": self._account, "password": self._password},
            allow_reauthentication=False,
        )
        data = response.get("data") or {}
        token_info = data.get("tokenInfo") or {}
        token = token_info.get("token")
        if not token:
            raise NepviewerAuthenticationError("NEPViewer did not return a token")

        self._token = str(token)
        user_info = data.get("userInfo") or {}
        try:
            self._company_id = int(user_info.get("companyId", DEFAULT_COMPANY_ID))
        except (TypeError, ValueError):
            self._company_id = DEFAULT_COMPANY_ID

    async def async_get_sites(self) -> list[dict[str, Any]]:
        """Return all solar sites visible to the account."""
        if not self._token:
            await self.async_login()

        payload = {
            "page": {"size": 100, "num": 0},
            "filters": {
                "keywords": "",
                "site_name": "",
                "user_email": "",
                "installer_email": "",
                "country_code": "",
                "created_start_date": "",
                "created_end_date": "",
                "street": "",
            },
            "sort": [],
        }
        response = await self._async_request(SITES_ENDPOINT, payload)
        data = response.get("data") or {}
        sites = data.get("list") or []
        if not isinstance(sites, list):
            raise NepviewerError("NEPViewer returned an invalid site list")
        return [site for site in sites if isinstance(site, dict)]

    async def _async_request(
        self,
        endpoint: str,
        payload: dict[str, Any],
        *,
        allow_reauthentication: bool = True,
    ) -> dict[str, Any]:
        serialized = serialize_payload(payload)
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "lan": str(DEFAULT_LANGUAGE),
            "client": "web",
            "oem": "NEP",
            "app": str(self._company_id),
            "sign": request_signature(serialized),
        }
        if self._token:
            headers["Authorization"] = self._token

        try:
            async with self._session.post(
                API_BASE_URL + endpoint,
                data=serialized.encode(),
                headers=headers,
            ) as response:
                result = await self._async_decode_response(response)
        except NepviewerAuthenticationError:
            if allow_reauthentication and self._account and self._password:
                self._token = None
                await self.async_login()
                return await self._async_request(
                    endpoint, payload, allow_reauthentication=False
                )
            raise
        except (ClientError, TimeoutError) as err:
            raise NepviewerConnectionError(str(err)) from err

        return result

    @staticmethod
    async def _async_decode_response(response: ClientResponse) -> dict[str, Any]:
        try:
            result = await response.json(content_type=None)
        except (ValueError, TypeError) as err:
            raise NepviewerConnectionError(
                f"NEPViewer returned HTTP {response.status} without valid JSON"
            ) from err

        if response.status in (401, 403):
            raise NepviewerAuthenticationError("NEPViewer rejected the authentication")
        if response.status != 200:
            raise NepviewerConnectionError(f"NEPViewer returned HTTP {response.status}")
        if not isinstance(result, dict):
            raise NepviewerConnectionError("NEPViewer returned an invalid response")

        code = result.get("code", 200)
        if code in (401, 403):
            raise NepviewerAuthenticationError(
                str(result.get("msg") or "NEPViewer rejected the authentication")
            )
        if code != 200:
            raise NepviewerError(str(result.get("msg") or f"NEPViewer error {code}"))
        return result
