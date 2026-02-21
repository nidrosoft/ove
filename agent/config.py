"""Environment-based configuration loader."""
import os
import json
import logging
from dataclasses import dataclass, field
from dotenv import load_dotenv

import httpx

load_dotenv()

logger = logging.getLogger("omnira-config")


class Config:
    """Global config from environment — shared across all calls."""
    LIVEKIT_URL = os.getenv("LIVEKIT_URL", "ws://localhost:7880")
    LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY", "devkey")
    LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET", "secret")

    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
    DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY", "")
    ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")

    TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
    TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
    TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER", "")

    RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
    FROM_EMAIL = os.getenv("FROM_EMAIL", "receptionist@omnira.space")

    OMNIRA_API_URL = os.getenv("OMNIRA_API_URL", "https://omniradental-cyri.vercel.app/api")
    OMNIRA_API_KEY = os.getenv("OMNIRA_API_KEY", "")

    # Fallback practice config (used when API config fetch fails)
    PRACTICE_ID = os.getenv("PRACTICE_ID", "")
    PRACTICE_NAME = os.getenv("PRACTICE_NAME", "Rivera Dental Care")
    PRACTICE_PHONE = os.getenv("PRACTICE_PHONE", "(555) 867-5309")
    PRACTICE_TIMEZONE = os.getenv("PRACTICE_TIMEZONE", "America/Chicago")
    PRACTICE_HOURS = os.getenv("PRACTICE_HOURS", "Mon-Fri 8am-5pm, Sat 9am-1pm")
    PRACTICE_ADDRESS = os.getenv("PRACTICE_ADDRESS", "742 Evergreen Terrace, Austin, TX 78701")
    AGENT_NAME = os.getenv("AGENT_NAME", "Relay")
    TTS_PROVIDER = os.getenv("TTS_PROVIDER", "deepgram")


@dataclass
class PracticeConfig:
    """Per-practice configuration loaded dynamically per call."""
    practice_id: str = ""
    practice_name: str = "Rivera Dental Care"
    practice_phone: str = "(555) 867-5309"
    practice_timezone: str = "America/Chicago"
    practice_hours: str = "Mon-Fri 8am-5pm"
    practice_address: str = "742 Evergreen Terrace, Austin, TX 78701"
    agent_name: str = "Relay"
    tts_provider: str = "deepgram"
    tts_voice_id: str = ""
    knowledge_base: str = ""
    operating_hours: list = field(default_factory=list)

    @classmethod
    def from_env(cls) -> "PracticeConfig":
        """Create from environment variables (single-tenant fallback)."""
        return cls(
            practice_id=Config.PRACTICE_ID,
            practice_name=Config.PRACTICE_NAME,
            practice_phone=Config.PRACTICE_PHONE,
            practice_timezone=Config.PRACTICE_TIMEZONE,
            practice_hours=Config.PRACTICE_HOURS,
            practice_address=Config.PRACTICE_ADDRESS,
            agent_name=Config.AGENT_NAME,
            tts_provider=Config.TTS_PROVIDER,
        )

    @classmethod
    async def fetch(cls, practice_id: str) -> "PracticeConfig":
        """Fetch practice config from Omnira API."""
        url = f"{Config.OMNIRA_API_URL}/voice-engine/practice-config"
        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                resp = await client.get(
                    url,
                    params={"practice_id": practice_id},
                    headers={
                        "Authorization": f"Bearer {Config.OMNIRA_API_KEY}",
                    },
                )
                if resp.status_code == 200 and resp.headers.get("content-type", "").startswith("application/json"):
                    data = resp.json()
                    return cls(
                        practice_id=data.get("practice_id", practice_id),
                        practice_name=data.get("practice_name", Config.PRACTICE_NAME),
                        practice_phone=data.get("practice_phone", Config.PRACTICE_PHONE),
                        practice_timezone=data.get("practice_timezone", Config.PRACTICE_TIMEZONE),
                        practice_hours=data.get("practice_hours", Config.PRACTICE_HOURS),
                        practice_address=data.get("practice_address", Config.PRACTICE_ADDRESS),
                        agent_name=data.get("agent_name", Config.AGENT_NAME),
                        tts_provider=data.get("tts_provider", Config.TTS_PROVIDER),
                        tts_voice_id=data.get("tts_voice_id", ""),
                        knowledge_base=data.get("knowledge_base", ""),
                        operating_hours=data.get("operating_hours", []),
                    )
                else:
                    logger.warning(f"Failed to fetch config for {practice_id}: {resp.status_code}")
        except Exception as e:
            logger.error(f"Config fetch failed for {practice_id}: {e}")

        fallback = cls.from_env()
        fallback.practice_id = practice_id
        return fallback
