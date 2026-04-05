from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime
import json
from pathlib import Path
from typing import Any, Dict, List
from uuid import uuid4


@dataclass
class PlannedTask:
    id: str
    title: str
    estimate_hours: float
    created_at: str
    notes: str = ""


class TaskStore:
    def __init__(self, task_store_path: str, sync_queue_path: str) -> None:
        self.task_store_path = Path(task_store_path)
        self.sync_queue_path = Path(sync_queue_path)
        self.task_store_path.parent.mkdir(parents=True, exist_ok=True)
        self.sync_queue_path.parent.mkdir(parents=True, exist_ok=True)

    def add_task(self, title: str, estimate_hours: float, notes: str = "") -> PlannedTask:
        task = PlannedTask(
            id=str(uuid4()),
            title=title,
            estimate_hours=max(0.0, estimate_hours),
            created_at=datetime.utcnow().isoformat(timespec="seconds"),
            notes=notes,
        )
        tasks = self._read_json_list(self.task_store_path)
        tasks.append(asdict(task))
        self._write_json_list(self.task_store_path, tasks)
        return task

    def queue_todo_sync(self, summary: str, description: str = "") -> None:
        queue_items = self._read_json_list(self.sync_queue_path)
        queue_items.append({
            "summary": summary,
            "description": description,
            "created_at": datetime.utcnow().isoformat(timespec="seconds"),
            "synced": False,
        })
        self._write_json_list(self.sync_queue_path, queue_items)

    def pending_sync_items(self) -> List[Dict[str, Any]]:
        return [item for item in self._read_json_list(self.sync_queue_path) if not item.get("synced")]

    def mark_synced(self, summary: str, created_at: str) -> None:
        queue_items = self._read_json_list(self.sync_queue_path)
        for item in queue_items:
            if item.get("summary") == summary and item.get("created_at") == created_at:
                item["synced"] = True
                break
        self._write_json_list(self.sync_queue_path, queue_items)

    def total_estimated_hours(self) -> float:
        tasks = self._read_json_list(self.task_store_path)
        total = 0.0
        for task in tasks:
            try:
                total += float(task.get("estimate_hours", 0.0))
            except Exception:
                pass
        return total

    def _read_json_list(self, path: Path) -> List[Dict[str, Any]]:
        if not path.exists():
            return []
        try:
            content = path.read_text(encoding="utf-8")
            data = json.loads(content)
            if isinstance(data, list):
                return data
        except Exception:
            pass
        return []

    def _write_json_list(self, path: Path, data: List[Dict[str, Any]]) -> None:
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
