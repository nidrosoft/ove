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
        "thalia": {"provider": "deepgram", "model": "aura-2-thalia-en", "label": "Thalia"},
        "luna": {"provider": "deepgram", "model": "aura-2-luna-en", "label": "Luna"},
        "asteria": {"provider": "deepgram", "model": "aura-2-asteria-en", "label": "Asteria"},
    },
    "elevenlabs": {
        "melissa": {"provider": "elevenlabs", "voice_id": "qgmxQ9pDWmPoMdev9PYB", "label": "Melissa"},
        "ava": {"provider": "elevenlabs", "voice_id": "GPcYs7Mjrv07kZEzMxQE", "label": "Ava"},
        "mark": {"provider": "elevenlabs", "voice_id": "UgBBYS2sOqTuMpoF3BR0", "label": "Mark"},
        "gracie": {"provider": "elevenlabs", "voice_id": "T7eLpgAAhoXHlrNajG8v", "label": "Gracie"},
        "abigail": {"provider": "elevenlabs", "voice_id": "3UFZ7Pkyx3hNTropzBlS", "label": "Abigail"},
        "joey": {"provider": "elevenlabs", "voice_id": "h2I5OFX58E5TL5AitYwR", "label": "Joey"},
        "barry": {"provider": "elevenlabs", "voice_id": "iTdwTswTQ3jxfWoMVywX", "label": "Barry"},
        "belle": {"provider": "elevenlabs", "voice_id": "wewocdDkjSLm9ZwjO7TD", "label": "Belle"},
        "juliet": {"provider": "elevenlabs", "voice_id": "WyFXw4PzMbRnp8iLMJwY", "label": "Juliet"},
        "veda": {"provider": "elevenlabs", "voice_id": "625jGFaa0zTLtQfxwc6Q", "label": "Veda"},
        "liz": {"provider": "elevenlabs", "voice_id": "uMM5TEnpKKgD758knVJO", "label": "Liz"},
        "maya": {"provider": "elevenlabs", "voice_id": "tJ2B69tloiOhZn8Gk9Lp", "label": "Maya"},
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
            resolved_voice_id = VOICE_OPTIONS["elevenlabs"]["abigail"]["voice_id"]
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
