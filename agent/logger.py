"""Call transcript logger — logs every call for compliance."""
import json
import logging
from datetime import datetime, timezone

logger = logging.getLogger("call-logger")


class CallLogger:
    """Logs call transcripts and events."""

    def __init__(self, call_id: str):
        self.call_id = call_id
        self.started_at = datetime.now(timezone.utc).isoformat()
        self.events: list[dict] = []

    def log_event(self, event_type: str, data: dict):
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": event_type,
            **data,
        }
        self.events.append(entry)
        logger.info(f"[{self.call_id}] {event_type}: {json.dumps(data)[:200]}")

    def log_caller_speech(self, text: str):
        self.log_event("caller_speech", {"text": text})

    def log_agent_speech(self, text: str):
        self.log_event("agent_speech", {"text": text})

    def log_tool_call(self, tool_name: str, args: dict, result: str):
        self.log_event("tool_call", {"tool": tool_name, "args": args, "result": result[:500]})

    def log_call_end(self, reason: str = "completed"):
        self.log_event("call_end", {"reason": reason})

    def get_transcript(self) -> dict:
        return {
            "call_id": self.call_id,
            "started_at": self.started_at,
            "ended_at": datetime.now(timezone.utc).isoformat(),
            "events": self.events,
        }
