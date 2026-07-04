"""
Thin async HTTP client for the SupoClip backend API.

The local SupoClip backend has no login or API-key layer, so this client does
not attach authentication headers.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

import httpx

from .config import Settings


class SupoClipError(Exception):
    """A friendly, already-formatted error suitable for returning to the model."""


class SupoClipClient:
    """Async client wrapping the SupoClip REST API."""

    def __init__(self, settings: Settings):
        self.settings = settings

    # -- auth ---------------------------------------------------------------
    def _auth_headers(self) -> Dict[str, str]:
        return {}

    def _require_auth(self) -> None:
        return None

    # -- requests -----------------------------------------------------------
    async def request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
        authenticated: bool = True,
    ) -> Any:
        """Make a JSON request and return the decoded body."""
        self._require_auth()

        headers = {"Accept": "application/json"}
        headers.update(self._auth_headers())

        url = f"{self.settings.api_url}{path}"
        try:
            async with httpx.AsyncClient(timeout=self.settings.timeout) as client:
                response = await client.request(
                    method, url, params=params, json=json_body, headers=headers
                )
        except httpx.TimeoutException as exc:
            raise SupoClipError(
                f"Request to {path} timed out after {self.settings.timeout:g}s."
            ) from exc
        except httpx.HTTPError as exc:
            raise SupoClipError(f"Could not reach SupoClip at {url}: {exc}") from exc

        return self._parse(response, path)

    async def download(
        self,
        path: str,
        destination_dir: str,
        filename: str,
        *,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Stream a binary file (a clip) to ``destination_dir`` and return its path."""
        self._require_auth()
        headers = self._auth_headers()
        url = f"{self.settings.api_url}{path}"

        dest_dir = Path(destination_dir).expanduser()
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_path = dest_dir / filename

        bytes_written = 0
        try:
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream(
                    "GET", url, params=params, headers=headers
                ) as response:
                    if response.status_code >= 400:
                        body = (await response.aread()).decode("utf-8", "replace")
                        raise SupoClipError(
                            _error_message(response.status_code, body, path)
                        )
                    with dest_path.open("wb") as handle:
                        async for chunk in response.aiter_bytes(chunk_size=1 << 16):
                            handle.write(chunk)
                            bytes_written += len(chunk)
        except httpx.HTTPError as exc:
            raise SupoClipError(f"Download from {url} failed: {exc}") from exc

        return {
            "path": str(dest_path.resolve()),
            "filename": filename,
            "bytes": bytes_written,
        }

    # -- helpers ------------------------------------------------------------
    @staticmethod
    def _parse(response: httpx.Response, path: str) -> Any:
        if response.status_code >= 400:
            raise SupoClipError(
                _error_message(response.status_code, response.text, path)
            )
        if not response.content:
            return {}
        try:
            return response.json()
        except ValueError:
            return {"raw": response.text}


def _error_message(status: int, body: str, path: str) -> str:
    """Turn a backend error response into an actionable message."""
    detail: Any = body
    try:
        import json

        parsed = json.loads(body)
        detail = parsed.get("detail", parsed) if isinstance(parsed, dict) else parsed
    except ValueError:
        pass

    if status == 401:
        return f"Backend rejected the request (401): {detail}"
    if status == 402:
        return f"Payment required (402): {detail}"
    if status == 403:
        return f"Permission denied (403): you do not have access to this resource. {detail}"
    if status == 404:
        return f"Not found (404) for {path}: {detail}"
    if status == 429:
        return "Rate limited (429). Wait a moment and try again."
    return f"SupoClip API error ({status}) for {path}: {detail}"
