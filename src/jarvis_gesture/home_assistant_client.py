from __future__ import annotations

from dataclasses import dataclass
import json
import ssl
from typing import Any, Dict, Optional, Tuple
from urllib import error, request


@dataclass
class HAResponse:
    ok: bool
    status_code: int
    message: str
    data: Optional[Any] = None


class HomeAssistantClient:
    def __init__(
        self,
        enabled: bool,
        base_url: str,
        token: str,
        timeout_seconds: float = 5.0,
        verify_tls: bool = True,
    ) -> None:
        self.enabled = enabled and bool(base_url) and bool(token)
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout_seconds = timeout_seconds
        self.verify_tls = verify_tls

        if verify_tls:
            self._ssl_context = ssl.create_default_context()
        else:
            self._ssl_context = ssl._create_unverified_context()

    def health_check(self) -> HAResponse:
        if not self.enabled:
            return HAResponse(ok=False, status_code=0, message="Home Assistant integration disabled")

        return self._request("GET", "/api/")

    def create_calendar_event(
        self,
        calendar_entity_id: str,
        summary: str,
        start_iso: str,
        end_iso: str,
        description: str = "",
        location: str = "",
    ) -> HAResponse:
        if not calendar_entity_id:
            return HAResponse(ok=False, status_code=0, message="Missing HA calendar entity ID")

        payload = {
            "entity_id": calendar_entity_id,
            "summary": summary,
            "start_date_time": start_iso,
            "end_date_time": end_iso,
        }
        if description:
            payload["description"] = description
        if location:
            payload["location"] = location

        return self._request("POST", "/api/services/calendar/create_event", payload)

    def add_todo_item(self, todo_entity_id: str, summary: str, description: str = "") -> HAResponse:
        if not todo_entity_id:
            return HAResponse(ok=False, status_code=0, message="Missing HA todo entity ID")

        payload: Dict[str, Any] = {
            "entity_id": todo_entity_id,
            "item": summary,
        }
        if description:
            payload["description"] = description

        return self._request("POST", "/api/services/todo/add_item", payload)

    def _request(self, method: str, path: str, payload: Optional[Dict[str, Any]] = None) -> HAResponse:
        if not self.enabled:
            return HAResponse(ok=False, status_code=0, message="Home Assistant integration disabled")

        url = f"{self.base_url}{path}"
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        req = request.Request(url=url, method=method, data=body)
        req.add_header("Authorization", f"Bearer {self.token}")
        req.add_header("Content-Type", "application/json")

        try:
            with request.urlopen(req, timeout=self.timeout_seconds, context=self._ssl_context) as resp:
                raw = resp.read().decode("utf-8")
                data = None
                if raw:
                    try:
                        data = json.loads(raw)
                    except Exception:
                        data = raw
                return HAResponse(ok=True, status_code=resp.status, message="ok", data=data)
        except error.HTTPError as exc:
            detail = ""
            try:
                detail = exc.read().decode("utf-8")
            except Exception:
                pass
            msg = f"HTTP {exc.code}"
            if detail:
                msg = f"{msg}: {detail[:200]}"
            return HAResponse(ok=False, status_code=exc.code, message=msg)
        except Exception as exc:
            return HAResponse(ok=False, status_code=0, message=str(exc))
