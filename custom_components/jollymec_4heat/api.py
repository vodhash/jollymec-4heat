# Copyright 2026 vodhash
"""Async client for the 4HEAT cloud used by Jolly Mec Connect.

Reads go through the unauthenticated device summary. Writes need a bearer token
from the OWIN password grant, obtained once and refreshed before it expires.
"""
from __future__ import annotations

import asyncio
import time

from aiohttp import ClientError, ClientResponseError, ClientSession, ClientTimeout

from .protocol import CommandPacer

BASE = "https://wifi4heat.azurewebsites.net"
_TIMEOUT = ClientTimeout(total=30)
_TOKEN_REFRESH_MARGIN = 600
# The module polls one queued command per cycle (~60 s) and keeps only the last,
# so writes are spaced by just over one poll or they clobber each other.
_COMMAND_INTERVAL = 65.0


class JollyMec4HeatError(Exception):
    """Base error for the client."""


class AuthError(JollyMec4HeatError):
    """Raised when the account login is rejected."""


class JollyMec4HeatApi:
    def __init__(
        self,
        session: ClientSession,
        device_id: str,
        pin: str,
        email: str,
        password: str,
    ) -> None:
        self._session = session
        self._device_id = device_id
        self._pin = pin
        self._email = email
        self._password = password
        self._token: str | None = None
        self._token_expiry = 0.0
        self._command_lock = asyncio.Lock()
        self._pacer = CommandPacer(_COMMAND_INTERVAL)

    async def async_get_summary(self) -> dict:
        url = f"{BASE}/api/devices/summary"
        data = await self._get_json(url, params={"ids": self._device_id})
        if not data:
            raise JollyMec4HeatError(f"unknown device {self._device_id}")
        return data[0]

    async def async_get_filemap(self) -> dict:
        url = f"{BASE}/api/Devices/FileMap"
        return await self._get_json(url, params={"pin": self._pin, "id": self._device_id})

    async def async_send_command(self, comando: list[str]) -> None:
        # Serialise and space writes: the cloud mailbox holds one command and the
        # module polls it every ~60 s, so back-to-back writes would overwrite each
        # other. One sender at a time, each waiting for its reserved slot.
        async with self._command_lock:
            delay = self._pacer.schedule(time.monotonic()) - time.monotonic()
            if delay > 0:
                await asyncio.sleep(delay)
            token = await self._async_token()
            url = f"{BASE}/api/devices/command"
            body = {"id": self._device_id, "comando": comando}
            headers = {"Authorization": f"Bearer {token}"}
            try:
                async with self._session.post(
                    url, json=body, headers=headers, timeout=_TIMEOUT
                ) as response:
                    response.raise_for_status()
            except ClientResponseError as err:
                if err.status == 401:
                    self._token = None
                    raise AuthError("token rejected by command endpoint") from err
                raise JollyMec4HeatError(f"command failed: {err.status}") from err
            except ClientError as err:
                raise JollyMec4HeatError("command request failed") from err

    async def async_validate(self) -> dict:
        """Confirm device, account and map during config; return the summary."""
        summary = await self.async_get_summary()
        await self._async_token()
        return summary

    async def _async_token(self) -> str:
        if self._token and time.monotonic() < self._token_expiry:
            return self._token
        form = {
            "grant_type": "password",
            "username": self._email,
            "password": self._password,
        }
        try:
            async with self._session.post(
                f"{BASE}/Token", data=form, timeout=_TIMEOUT
            ) as response:
                if response.status == 400:
                    raise AuthError("invalid email or password")
                response.raise_for_status()
                payload = await response.json()
        except ClientResponseError as err:
            raise JollyMec4HeatError(f"token request failed: {err.status}") from err
        except ClientError as err:
            raise JollyMec4HeatError("token request failed") from err
        self._token = payload["access_token"]
        self._token_expiry = time.monotonic() + payload.get("expires_in", 0) - _TOKEN_REFRESH_MARGIN
        return self._token

    async def _get_json(self, url: str, params: dict) -> object:
        try:
            async with self._session.get(url, params=params, timeout=_TIMEOUT) as response:
                response.raise_for_status()
                return await response.json()
        except ClientResponseError as err:
            raise JollyMec4HeatError(f"request failed: {err.status}") from err
        except ClientError as err:
            raise JollyMec4HeatError("request failed") from err
