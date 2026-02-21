"""Omnira Voice Agent — the main agent definition."""
import logging

from livekit.agents import Agent, AgentSession
from livekit.plugins import deepgram, silero, anthropic

from agent.config import Config, PracticeConfig
from agent.prompts import build_system_prompt
from agent.tools import (
    check_availability,
    book_appointment,
    send_sms,
    send_email,
    lookup_patient,
)
from agent.logger import CallLogger

logger = logging.getLogger("omnira-agent")

VOICE_OPTIONS = {
    "deepgram": {
        "thalia": {"provider": "deepgram", "model": "aura-2-thalia-en", "label": "Thalia (Natural Female)"},
        "luna": {"provider": "deepgram", "model": "aura-2-luna-en", "label": "Luna (Warm Female)"},
    },
    "elevenlabs": {
        "aria": {"provider": "elevenlabs", "voice_id": "9BWtsMINqrJLrRacOk9x", "label": "Aria (Professional Female)"},
        "sarah": {"provider": "elevenlabs", "voice_id": "EXAVITQu4vr4xnSDxMaL", "label": "Sarah (Friendly Female)"},
        "charlotte": {"provider": "elevenlabs", "voice_id": "XB0fDUnXU5powFXDhCwa", "label": "Charlotte (Elegant Female)"},
    },
}

DEFAULT_VOICE = ("deepgram", "thalia")


class OmniraReceptionist(Agent):
    """The Omnira dental receptionist voice agent."""

    def __init__(self, call_logger: CallLogger, practice_config: PracticeConfig):
        super().__init__(
            instructions=build_system_prompt(practice_config),
        )
        self.call_logger = call_logger
        self.practice_config = practice_config
        logger.info(f"Agent created: practice={practice_config.practice_name} agent={practice_config.agent_name}")

    async def on_enter(self):
        self.session.generate_reply(
            instructions="Greet the caller warmly. Say: Thank you for calling "
            f"{self.practice_config.practice_name}, this is {self.practice_config.agent_name}, how can I help you today?"
        )


def create_agent_session(practice_config: PracticeConfig) -> AgentSession:
    """Create a configured AgentSession with TTS based on practice preference."""
    tts_provider = practice_config.tts_provider or "deepgram"
    voice_id = practice_config.tts_voice_id or ""

    if tts_provider == "elevenlabs" and Config.ELEVENLABS_API_KEY:
        from livekit.plugins import elevenlabs
        resolved_voice_id = voice_id
        if not resolved_voice_id:
            resolved_voice_id = VOICE_OPTIONS["elevenlabs"]["aria"]["voice_id"]
        tts = elevenlabs.TTS(
            api_key=Config.ELEVENLABS_API_KEY,
            voice_id=resolved_voice_id,
            model="eleven_flash_v2_5",
        )
        logger.info(f"Using ElevenLabs TTS: voice={resolved_voice_id}")
    else:
        model = "aura-2-thalia-en"
        if voice_id and voice_id in [v["model"] for v in VOICE_OPTIONS["deepgram"].values()]:
            model = voice_id
        tts = deepgram.TTS(
            api_key=Config.DEEPGRAM_API_KEY,
            model=model,
        )
        logger.info(f"Using Deepgram TTS: model={model}")

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
        tts=tts,
        tools=[
            lookup_patient,
            check_availability,
            book_appointment,
            send_sms,
            send_email,
        ],
    )

    return session
