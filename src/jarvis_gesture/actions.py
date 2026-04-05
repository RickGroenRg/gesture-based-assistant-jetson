from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
import re
from typing import Callable, Dict

import cv2
import numpy as np

from .home_assistant_client import HomeAssistantClient
from .task_store import TaskStore
from .website_lookup import WebsiteLookupService


@dataclass
class ActionResult:
    ok: bool
    message: str


class ActionRouter:
    def __init__(
        self,
        snapshot_dir: str,
        ha_client: HomeAssistantClient,
        task_store: TaskStore,
        website_lookup: WebsiteLookupService,
        ha_calendar_entity_id: str,
        ha_todo_entity_id: str,
        planning_daily_hours_limit: float,
    ) -> None:
        self.snapshot_dir = Path(snapshot_dir)
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)
        self.ha_client = ha_client
        self.task_store = task_store
        self.website_lookup = website_lookup
        self.ha_calendar_entity_id = ha_calendar_entity_id
        self.ha_todo_entity_id = ha_todo_entity_id
        self.planning_daily_hours_limit = planning_daily_hours_limit

        self._handlers: Dict[str, Callable[[np.ndarray, str], ActionResult]] = {
            "open_palm": self._handle_play_pause,
            "fist": self._handle_snapshot,
            "voice_play_pause": self._handle_play_pause,
            "voice_snapshot": self._handle_snapshot,
            "voice_volume_up": self._handle_volume_up,
            "voice_volume_down": self._handle_volume_down,
            "add_meeting": self._handle_add_meeting,
            "add_appointment": self._handle_add_appointment,
            "plan_task": self._handle_plan_task,
            "plan_day": self._handle_plan_day,
            "website_lookup": self._handle_website_lookup,
        }

    def execute(self, intent_name: str, frame: np.ndarray, command_text: str = "") -> ActionResult:
        handler = self._handlers.get(intent_name)
        if handler is None:
            return ActionResult(ok=False, message=f"No action for intent: {intent_name}")
        return handler(frame, command_text)

    def _handle_play_pause(self, _: np.ndarray, __: str) -> ActionResult:
        return ActionResult(ok=True, message="Play/Pause toggled (placeholder).")

    def _handle_volume_up(self, _: np.ndarray, __: str) -> ActionResult:
        return ActionResult(ok=True, message="Volume up (placeholder).")

    def _handle_volume_down(self, _: np.ndarray, __: str) -> ActionResult:
        return ActionResult(ok=True, message="Volume down (placeholder).")

    def _handle_snapshot(self, frame: np.ndarray, __: str) -> ActionResult:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = self.snapshot_dir / f"snapshot_{timestamp}.jpg"
        cv2.imwrite(str(path), frame)
        return ActionResult(ok=True, message=f"Snapshot saved: {path}")

    def _handle_add_meeting(self, _: np.ndarray, command_text: str) -> ActionResult:
        return self._create_calendar_event(command_text, default_title="Meeting")

    def _handle_add_appointment(self, _: np.ndarray, command_text: str) -> ActionResult:
        return self._create_calendar_event(command_text, default_title="Appointment")

    def _create_calendar_event(self, command_text: str, default_title: str) -> ActionResult:
        title = self._extract_event_title(command_text, default_title)
        start_at = self._extract_start_datetime(command_text)
        duration_minutes = self._extract_duration_minutes(command_text, default_minutes=30)
        end_at = start_at + timedelta(minutes=duration_minutes)

        response = self.ha_client.create_calendar_event(
            calendar_entity_id=self.ha_calendar_entity_id,
            summary=title,
            start_iso=start_at.isoformat(),
            end_iso=end_at.isoformat(),
            description=f"Created from Jarvis voice command: {command_text}",
        )

        if response.ok:
            return ActionResult(ok=True, message=f"{default_title} added: {title} at {start_at.strftime('%H:%M')}.")

        return ActionResult(ok=False, message=f"Failed to add {default_title.lower()}: {response.message}")

    def _handle_plan_task(self, _: np.ndarray, command_text: str) -> ActionResult:
        title = self._extract_task_title(command_text)
        estimate = self._extract_estimate_hours(command_text, default_hours=1.0)

        task = self.task_store.add_task(title=title, estimate_hours=estimate, notes=command_text)
        description = f"Estimate: {estimate:.1f}h | Source: {command_text}"
        self.task_store.queue_todo_sync(summary=title, description=description)

        if self.ha_client.enabled and self.ha_todo_entity_id:
            response = self.ha_client.add_todo_item(self.ha_todo_entity_id, summary=title, description=description)
            if response.ok:
                pending = self.task_store.pending_sync_items()
                if pending:
                    latest = pending[-1]
                    self.task_store.mark_synced(latest["summary"], latest["created_at"])

        total_hours = self.task_store.total_estimated_hours()
        overload = "" if total_hours <= self.planning_daily_hours_limit else " Warning: plan exceeds daily hour limit."
        return ActionResult(
            ok=True,
            message=f"Task planned: {task.title} ({task.estimate_hours:.1f}h). Total planned: {total_hours:.1f}h.{overload}",
        )

    def _handle_plan_day(self, _: np.ndarray, command_text: str) -> ActionResult:
        # For v1, treat plan-day commands as one summarized planning item.
        summary = self._extract_task_title(command_text)
        estimate = self._extract_estimate_hours(command_text, default_hours=2.0)
        return self._handle_plan_task(_, f"{summary} {estimate} hours")

    def _handle_website_lookup(self, _: np.ndarray, command_text: str) -> ActionResult:
        ok, lookup_message = self.website_lookup.lookup(command_text)

        task_title = self._extract_task_title(command_text)
        if not task_title or task_title.lower() in {"website lookup", "lookup"}:
            task_title = f"Research: {command_text[:60]}".strip()

        self.task_store.add_task(title=task_title, estimate_hours=0.5, notes=f"Lookup: {command_text}")
        self.task_store.queue_todo_sync(summary=task_title, description=f"Website lookup request: {command_text}")

        if self.ha_client.enabled and self.ha_todo_entity_id:
            self.ha_client.add_todo_item(self.ha_todo_entity_id, summary=task_title, description=f"Website lookup: {command_text}")

        if ok:
            return ActionResult(ok=True, message=f"Lookup summary: {lookup_message}")
        return ActionResult(ok=False, message=f"Lookup could not complete. Task added for later: {lookup_message}")

    def _extract_event_title(self, text: str, default_title: str) -> str:
        cleaned = text.strip()
        if not cleaned:
            return default_title

        cleaned = re.sub(r"\b(add|create|schedule|meeting|appointment)\b", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\b(tomorrow|today|at|for|on)\b.*$", "", cleaned, flags=re.IGNORECASE)
        cleaned = cleaned.strip(" ,.-")
        return cleaned.title() if cleaned else default_title

    def _extract_start_datetime(self, text: str) -> datetime:
        now = datetime.now()
        start = now.replace(second=0, microsecond=0) + timedelta(hours=1)

        if "tomorrow" in text.lower():
            start = start + timedelta(days=1)

        time_match = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b", text.lower())
        if time_match:
            hour = int(time_match.group(1))
            minute = int(time_match.group(2) or 0)
            meridiem = time_match.group(3)
            if meridiem == "pm" and hour < 12:
                hour += 12
            if meridiem == "am" and hour == 12:
                hour = 0
            start = start.replace(hour=min(hour, 23), minute=min(minute, 59))

        return start

    def _extract_duration_minutes(self, text: str, default_minutes: int = 30) -> int:
        m = re.search(r"(\d+(?:\.\d+)?)\s*(hour|hours|hr|hrs|minute|minutes|min|mins)\b", text.lower())
        if not m:
            return default_minutes

        value = float(m.group(1))
        unit = m.group(2)
        if unit.startswith("hour") or unit.startswith("hr"):
            return max(5, int(value * 60))
        return max(5, int(value))

    def _extract_estimate_hours(self, text: str, default_hours: float = 1.0) -> float:
        m = re.search(r"(\d+(?:\.\d+)?)\s*(hour|hours|hr|hrs|h)\b", text.lower())
        if m:
            return max(0.25, float(m.group(1)))

        m_minutes = re.search(r"(\d+)\s*(minute|minutes|min|mins)\b", text.lower())
        if m_minutes:
            minutes = int(m_minutes.group(1))
            return max(0.25, round(minutes / 60.0, 2))

        return default_hours

    def _extract_task_title(self, text: str) -> str:
        cleaned = text.strip()
        if not cleaned:
            return "Planned Task"

        cleaned = re.sub(
            r"\b(plan|schedule|task|add|estimate|hours|hour|lookup|look up|website|meeting|appointment|for|with|to)\b",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(r"\d+(?:\.\d+)?", "", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,.-")
        if not cleaned:
            return "Planned Task"
        return cleaned[:120].title()
