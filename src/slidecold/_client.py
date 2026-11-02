import asyncio
import time
from typing import Any, Dict, Optional
from urllib.parse import quote

import httpx

from . import _config
from ._exceptions import APIConnectionError, AuthenticationError, error_for_status
from ._files import FileInput, to_upload
from ._operations import OPERATIONS
from ._resources import AsyncResources, SyncResources
from ._version import __version__

RETRY_STATUSES = {429, 500, 502, 503, 504}
TERMINAL_JOB_STATES = {"completed", "failed", "unknown"}
NO_KEY = "No SlideCold API key found. Pass api_key=..., set SLIDECOLD_API_KEY, or run `slidecold login`"


class _BaseClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = 30,
        max_retries: int = 2,
    ) -> None:
        key, url = _config.resolve(api_key, base_url)
        if not key:
            raise AuthenticationError(None, NO_KEY)
        self.api_key = key
        self.base_url = url
        self.timeout = timeout
        self.max_retries = max_retries
        self._headers = {
            "Authorization": f"Bearer {key}",
            "User-Agent": f"slidecold-python/{__version__}",
            "Accept": "application/json",
        }

    def _build(
        self,
        operation_id: str,
        path: Optional[Dict[str, Any]],
        query: Optional[Dict[str, Any]],
        body: Optional[Any],
        file: Optional[FileInput],
    ) -> Dict[str, Any]:
        op = OPERATIONS[operation_id]
        url = op.path
        for p in op.path_params:
            value = (path or {}).get(p.name)
            if value is None or value == "":
                raise ValueError(f"{operation_id}: missing path parameter {p.py_name!r}")
            url = url.replace("{" + p.name + "}", quote(str(value), safe=""))
        params = {}
        for k, v in (query or {}).items():
            if v is not None:
                params[k] = ("true" if v else "false") if isinstance(v, bool) else v
        request: Dict[str, Any] = {"method": op.method, "url": self.base_url + url, "params": params}
        if file is not None:
            if not op.file_field:
                raise ValueError(f"{operation_id} does not accept a file")
            request["files"] = {op.file_field: to_upload(file)}
        elif op.body == "multipart":
            raise ValueError(f"{operation_id} requires a file")
        elif op.body:
            if body is None and op.body_required:
                body = {}
            if body is not None:
                request["json"] = body
        return request

    def _backoff(self, attempt: int, response: Optional[httpx.Response]) -> float:
        retry_after = response.headers.get("retry-after") if response is not None else None
        if retry_after and retry_after.replace(".", "", 1).isdigit():
            return min(float(retry_after), 30.0)
        return min(0.5 * 2.0**attempt, 8.0)

    @staticmethod
    def _parse(response: httpx.Response) -> Any:
        ctype = response.headers.get("content-type", "")
        if response.status_code >= 400:
            body: Any = response.text
            if "json" in ctype:
                try:
                    body = response.json()
                except ValueError:
                    pass
            message = body.get("error") if isinstance(body, dict) else None
            if not isinstance(message, str):
                message = (
                    (body if isinstance(body, str) and body else None) or response.reason_phrase or "Error"
                )
            raise error_for_status(response.status_code, message, body)
        if not response.content:
            return None
        if "json" in ctype:
            return response.json()
        return response.text


class SlideCold(_BaseClient, SyncResources):
    """Synchronous SlideCold client.

    >>> with SlideCold() as client:
    ...     campaigns = client.campaigns.list()
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = 30,
        max_retries: int = 2,
    ) -> None:
        super().__init__(api_key, base_url, timeout, max_retries)
        self._http = httpx.Client(headers=self._headers, timeout=timeout)
        self._init_resources()

    def request(
        self,
        operation_id: str,
        *,
        path: Optional[Dict[str, Any]] = None,
        query: Optional[Dict[str, Any]] = None,
        body: Optional[Any] = None,
        file: Optional[FileInput] = None,
    ) -> Any:
        """Call any operation by its OpenAPI operationId. Only GETs are retried."""
        req = self._build(operation_id, path, query, body, file)
        retries = self.max_retries if req["method"] == "GET" else 0
        attempt = 0
        while True:
            try:
                response = self._http.request(**req)
            except httpx.TransportError as e:
                if attempt >= retries:
                    raise APIConnectionError(None, f"Could not reach {self.base_url}: {e}") from e
                time.sleep(self._backoff(attempt, None))
            else:
                if response.status_code not in RETRY_STATUSES or attempt >= retries:
                    return self._parse(response)
                time.sleep(self._backoff(attempt, response))
            attempt += 1

    def wait_for_login_job(self, job_id: str, interval: float = 2, timeout: float = 120) -> Dict[str, Any]:
        """Poll `accounts.login_status` until the job is completed, failed or unknown; return the last status.

        Raises TimeoutError if the job is still running after `timeout` seconds.
        """
        deadline = time.monotonic() + timeout
        while True:
            status: Dict[str, Any] = self.accounts.login_status(job_id)
            if status.get("state") in TERMINAL_JOB_STATES:
                return status
            if time.monotonic() + interval > deadline:
                raise TimeoutError(f"Login job {job_id} still {status.get('state')!r} after {timeout}s")
            time.sleep(interval)

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "SlideCold":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


class AsyncSlideCold(_BaseClient, AsyncResources):
    """Asynchronous SlideCold client (asyncio).

    >>> async with AsyncSlideCold() as client:
    ...     campaigns = await client.campaigns.list()
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = 30,
        max_retries: int = 2,
    ) -> None:
        super().__init__(api_key, base_url, timeout, max_retries)
        self._http = httpx.AsyncClient(headers=self._headers, timeout=timeout)
        self._init_resources()

    async def request(
        self,
        operation_id: str,
        *,
        path: Optional[Dict[str, Any]] = None,
        query: Optional[Dict[str, Any]] = None,
        body: Optional[Any] = None,
        file: Optional[FileInput] = None,
    ) -> Any:
        """Call any operation by its OpenAPI operationId. Only GETs are retried."""
        req = self._build(operation_id, path, query, body, file)
        retries = self.max_retries if req["method"] == "GET" else 0
        attempt = 0
        while True:
            try:
                response = await self._http.request(**req)
            except httpx.TransportError as e:
                if attempt >= retries:
                    raise APIConnectionError(None, f"Could not reach {self.base_url}: {e}") from e
                await asyncio.sleep(self._backoff(attempt, None))
            else:
                if response.status_code not in RETRY_STATUSES or attempt >= retries:
                    return self._parse(response)
                await asyncio.sleep(self._backoff(attempt, response))
            attempt += 1

    async def wait_for_login_job(
        self, job_id: str, interval: float = 2, timeout: float = 120
    ) -> Dict[str, Any]:
        """Async version of `SlideCold.wait_for_login_job`."""
        deadline = time.monotonic() + timeout
        while True:
            status: Dict[str, Any] = await self.accounts.login_status(job_id)
            if status.get("state") in TERMINAL_JOB_STATES:
                return status
            if time.monotonic() + interval > deadline:
                raise TimeoutError(f"Login job {job_id} still {status.get('state')!r} after {timeout}s")
            await asyncio.sleep(interval)

    async def close(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> "AsyncSlideCold":
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()
