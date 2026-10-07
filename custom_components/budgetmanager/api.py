"""Client for the Budget Manager server's REST API.

The server authenticates with SimpleJWT: an access token lives 15 minutes and
a refresh token 7 days. Refresh tokens are rotated and the old one is
blacklisted, so every new refresh token must be persisted at once through
``on_refresh_token``, or the next restart would be left with a dead one.
"""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import date
from typing import Any

import aiohttp


class BudgetManagerError(Exception):
    """The server could not be reached or answered with an error."""


class BudgetManagerAuthError(BudgetManagerError):
    """The credentials or the refresh token were rejected."""


class BudgetManagerApi:
    def __init__(
        self,
        session: aiohttp.ClientSession,
        url: str,
        refresh_token: str | None = None,
        on_refresh_token: Callable[[str], None] | None = None,
    ) -> None:
        self._session = session
        self._url = url.rstrip("/")
        self._refresh_token = refresh_token
        self._access_token: str | None = None
        self._on_refresh_token = on_refresh_token
        self._refresh_lock = asyncio.Lock()

    @property
    def refresh_token(self) -> str | None:
        return self._refresh_token

    def set_refresh_token_listener(
        self, on_refresh_token: Callable[[str], None]
    ) -> None:
        self._on_refresh_token = on_refresh_token

    async def login(self, username: str, password: str) -> None:
        """Obtain a token pair; the password itself is never stored."""
        data = await self._post_json(
            "/api/token/", {"username": username, "password": password})
        self._access_token = data["access"]
        self._set_refresh_token(data["refresh"])

    async def get_summary(self, month_id: int | None = None) -> dict[str, Any]:
        params = {"month_id": str(month_id)} if month_id else None
        return await self._request("GET", "/api/summary/", params=params)

    async def get_statistics(self) -> dict[str, Any]:
        return await self._request("GET", "/api/statistics/")

    async def set_planned_savings(self, value: float) -> dict[str, Any]:
        return await self._request(
            "POST", "/api/planned-savings/", json={"planned_savings": value})

    async def add_expense(
        self,
        month_id: int,
        category_id: int,
        value: float,
        expense_date: date,
        comment: str | None = None,
        is_monthly: bool = False,
    ) -> dict[str, Any]:
        return await self._request("POST", "/api/expense/", json={
            "month": month_id,
            "category": category_id,
            "value": f"{value:.2f}",
            "date": expense_date.isoformat(),
            "comment": comment,
            "is_monthly": is_monthly,
        })

    async def add_income(
        self,
        month_id: int,
        value: float,
        income_date: date,
        comment: str | None = None,
        is_salary: bool = False,
    ) -> dict[str, Any]:
        return await self._request("POST", "/api/income/", json={
            "month": month_id,
            "value": f"{value:.2f}",
            "date": income_date.isoformat(),
            "comment": comment,
            "is_salary": is_salary,
        })

    async def _refresh(self, stale_access_token: str | None) -> None:
        # A refresh token works once, so concurrent callers must not each
        # spend it: the first one refreshes, the rest reuse its result.
        async with self._refresh_lock:
            if self._access_token != stale_access_token:
                return
            if not self._refresh_token:
                raise BudgetManagerAuthError("No refresh token")
            data = await self._post_json(
                "/api/token/refresh/", {"refresh": self._refresh_token})
            self._access_token = data["access"]
            if "refresh" in data:
                self._set_refresh_token(data["refresh"])

    def _set_refresh_token(self, token: str) -> None:
        self._refresh_token = token
        if self._on_refresh_token:
            self._on_refresh_token(token)

    async def _request(
        self, method: str, path: str, *, retry: bool = True, **kwargs: Any
    ) -> Any:
        if self._access_token is None:
            await self._refresh(None)
        access_token = self._access_token
        headers = {"Authorization": f"Bearer {access_token}"}
        try:
            async with self._session.request(
                method, self._url + path, headers=headers, **kwargs
            ) as resp:
                if resp.status == 401 and retry:
                    await self._refresh(access_token)
                    return await self._request(
                        method, path, retry=False, **kwargs)
                if resp.status == 401:
                    raise BudgetManagerAuthError("Access token rejected")
                if resp.status >= 400:
                    raise BudgetManagerError(
                        f"{method} {path}: HTTP {resp.status} {await resp.text()}")
                if resp.status == 204:
                    return None
                return await resp.json()
        except aiohttp.ClientError as err:
            raise BudgetManagerError(f"{method} {path}: {err}") from err

    async def _post_json(self, path: str, payload: dict[str, Any]) -> Any:
        """An unauthenticated POST to a token endpoint."""
        try:
            async with self._session.post(
                self._url + path, json=payload
            ) as resp:
                if resp.status in (400, 401):
                    raise BudgetManagerAuthError(await resp.text())
                if resp.status >= 400:
                    raise BudgetManagerError(
                        f"POST {path}: HTTP {resp.status} {await resp.text()}")
                return await resp.json()
        except aiohttp.ClientError as err:
            raise BudgetManagerError(f"POST {path}: {err}") from err
