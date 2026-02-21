"""Environment-based configuration loader."""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # LiveKit
    LIVEKIT_URL = os.getenv("LIVEKIT_URL", "ws://localhost:7880")
    LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY", "devkey")
    LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET", "secret")

    # Anthropic
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

    # Deepgram
    DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY", "")

    # TTS
    TTS_PROVIDER = os.getenv("TTS_PROVIDER", "kokoro")
    KOKORO_BASE_URL = os.getenv("KOKORO_BASE_URL", "http://localhost:3000")
    KOKORO_API_KEY = os.getenv("KOKORO_API_KEY", "")
    KOKORO_VOICE = os.getenv("KOKORO_VOICE", "af_heart")
    ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
    ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "")
    CARTESIA_API_KEY = os.getenv("CARTESIA_API_KEY", "")
    CARTESIA_VOICE_ID = os.getenv("CARTESIA_VOICE_ID", "")

    # Twilio
    TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
    TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
    TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER", "")

    # Resend
    RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
    FROM_EMAIL = os.getenv("FROM_EMAIL", "receptionist@omnira.space")

    # Omnira Platform API
    OMNIRA_API_URL = os.getenv("OMNIRA_API_URL", "https://omniradental-cyri.vercel.app/api")
    OMNIRA_API_KEY = os.getenv("OMNIRA_API_KEY", "")

    # Practice
    PRACTICE_ID = os.getenv("PRACTICE_ID", "")
    PRACTICE_NAME = os.getenv("PRACTICE_NAME", "Rivera Dental Care")
    PRACTICE_PHONE = os.getenv("PRACTICE_PHONE", "(555) 867-5309")
    PRACTICE_TIMEZONE = os.getenv("PRACTICE_TIMEZONE", "America/Chicago")
    PRACTICE_HOURS = os.getenv("PRACTICE_HOURS", "Mon-Fri 8am-5pm, Sat 9am-1pm")
    PRACTICE_ADDRESS = os.getenv("PRACTICE_ADDRESS", "742 Evergreen Terrace, Austin, TX 78701")

    # Agent
    AGENT_NAME = os.getenv("AGENT_NAME", "Relay")
