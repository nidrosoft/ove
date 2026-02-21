"""Omnira Voice Agent — the main agent definition."""
import logging
import uuid

from livekit.agents import Agent, AgentSession
from livekit.plugins import deepgram, silero, anthropic

from agent.config import Config
from agent.prompts import build_system_prompt
from agent.tools import (
    check_availability,
    book_appointment,
    send_sms,
    send_email,
    transfer_call,
    lookup_patient,
)
from agent.logger import CallLogger

logger = logging.getLogger("omnira-agent")


class OmniraReceptionist(Agent):
    """The Omnira dental receptionist voice agent."""

    def __init__(self, call_logger: CallLogger):
        super().__init__(
            instructions=build_system_prompt(),
        )
        self.call_logger = call_logger
        logger.info(f"New agent created for call {self.call_logger.call_id}")

    async def on_enter(self):
        """Called when the agent joins. Start with a greeting."""
        self.session.generate_reply(
            instructions="Greet the caller warmly. Say: Thank you for calling "
            f"{Config.PRACTICE_NAME}, this is {Config.AGENT_NAME}, how can I help you today?"
        )


def create_agent_session() -> AgentSession:
    """Create a configured AgentSession with all providers."""
    session = AgentSession(
        vad=silero.VAD.load(),
        stt=deepgram.STT(
            api_key=Config.DEEPGRAM_API_KEY,
            model="nova-2",
            language="en",
        ),
        llm=anthropic.LLM(
            api_key=Config.ANTHROPIC_API_KEY,
            model="claude-haiku-4-5-20251001",
        ),
        tts=deepgram.TTS(
            api_key=Config.DEEPGRAM_API_KEY,
            model="aura-2-thalia-en",
        ),
        tools=[
            lookup_patient,
            check_availability,
            book_appointment,
            send_sms,
            send_email,
            transfer_call,
        ],
    )

    return session
