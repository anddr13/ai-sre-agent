"""Audit log: one JSONL file per investigation, one line per event (the alert, every LLM turn, every tool
call and result, the outcome). It holds exactly what the LLM saw, i.e. the redacted text, and doubles as the
dataset of the backtest."""

import json
import re
import time
import uuid
from pathlib import Path
from typing import Any


class Audit:
    def __init__(self, directory: str, alertname: str):
        self.investigation_id = uuid.uuid4().hex[:12]
        safe = re.sub(r"[^\w-]", "_", alertname)[:60] or "alert"
        stamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
        Path(directory).mkdir(parents=True, exist_ok=True)
        self.path = Path(directory) / f"{stamp}-{safe}-{self.investigation_id}.jsonl"

    def write(self, event: str, **data: Any) -> None:
        record = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "investigation": self.investigation_id,
            "event": event,
            **data,
        }
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
