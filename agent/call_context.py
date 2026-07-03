"""Per-call context shared with the tool layer.

LiveKit agents runs ONE job (room/call) per subprocess, so a module-level
context is call-safe — unlike mutating Config.PRACTICE_ID (the old pattern),
this is explicit and carries everything the control plane needs to enforce
the verification gate server-side (spec 59): the call_session_id travels on
EVERY action so the platform, not the LLM, decides what may be disclosed.
"""

from dataclasses import dataclass, field


@dataclass
class CallContext:
    call_id: str = ""
    practice_id: str = ""
    caller_number: str = ""
    # Set from start_call_session's response (display/logging only — the
    # server keeps the authoritative state).
    recognized_first_name: str = ""
    recent_call_topic: str = ""

    def reset(self) -> None:
        self.call_id = ""
        self.practice_id = ""
        self.caller_number = ""
        self.recognized_first_name = ""
        self.recent_call_topic = ""


current_call = CallContext()
