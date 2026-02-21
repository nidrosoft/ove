"""Call transcript logger — logs every call and sends data to Omnira platform."""
import json
import logging
from datetime import datetime, timezone

import httpx

from agent.config import Config

logger = logging.getLogger("call-logger")


class CallLogger:
    """Logs call transcripts and events, sends post-call data to Omnira."""

    def __init__(self, call_id: str, from_number: str = "", to_number: str = ""):
        self.call_id = call_id
        self.from_number = from_number
        self.to_number = to_number
        self.started_at = datetime.now(timezone.utc).isoformat()
        self.events: list[dict] = []
        self.collected_info: dict = {}
        self.tool_results: list[dict] = []

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
        self.tool_results.append({"tool": tool_name, "args": args, "result": result[:500]})

        if tool_name == "book_appointment":
            self.collected_info.update({
                "patient_name": args.get("patient_name", ""),
                "patient_phone": args.get("patient_phone", ""),
                "patient_email": args.get("patient_email", ""),
                "procedure_type": args.get("procedure_type", ""),
                "appointment_date": args.get("date", ""),
                "appointment_time": args.get("time", ""),
            })

    def set_collected_info(self, key: str, value: str):
        self.collected_info[key] = value

    def log_call_end(self, reason: str = "completed"):
        self.log_event("call_end", {"reason": reason})

    def get_transcript_text(self) -> str:
        """Build a human-readable transcript from events."""
        lines = []
        for ev in self.events:
            if ev["type"] == "caller_speech":
                lines.append(f"Caller: {ev['text']}")
            elif ev["type"] == "agent_speech":
                lines.append(f"Nira: {ev['text']}")
            elif ev["type"] == "tool_call":
                lines.append(f"[Tool: {ev['tool']}]")
        return "\n".join(lines)

    def get_full_payload(self) -> dict:
        """Build the payload to send to Omnira's webhook."""
        ended_at = datetime.now(timezone.utc).isoformat()

        return {
            "source": "omnira-voice-engine",
            "call_id": self.call_id,
            "from": self.from_number,
            "to": self.to_number,
            "started_at": self.started_at,
            "ended_at": ended_at,
            "status": "completed",
            "transcript": self.get_transcript_text(),
            "collected_info": self.collected_info,
            "tool_calls": self.tool_results,
            "events": self.events,
        }

    async def send_to_omnira(self):
        """Send the completed call data to the Omnira platform webhook."""
        if not Config.OMNIRA_API_URL:
            logger.warning("OMNIRA_API_URL not configured — skipping post-call report")
            return

        url = f"{Config.OMNIRA_API_URL}/webhooks/voice-engine"
        payload = self.get_full_payload()

        logger.info(f"[{self.call_id}] Sending post-call data to {url}")

        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                resp = await client.post(
                    url,
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {Config.OMNIRA_API_KEY}",
                        "Content-Type": "application/json",
                        "X-Engine-Source": "omnira-voice-engine",
                    },
                )
                if resp.status_code < 300:
                    logger.info(f"[{self.call_id}] Post-call data sent to Omnira (status {resp.status_code})")
                else:
                    logger.error(f"[{self.call_id}] Omnira webhook returned {resp.status_code}: {resp.text[:300]}")
        except Exception as e:
            logger.error(f"[{self.call_id}] Failed to send post-call data to Omnira: {e}")
