"""TTS provider factory — swap providers via env config."""
import logging
from agent.config import Config

logger = logging.getLogger("tts-provider")


def get_tts():
    """Return configured TTS provider instance."""
    provider = Config.TTS_PROVIDER.lower()

    if provider == "kokoro":
        from tts.kokoro_tts import KokoroTTS
        logger.info(f"Using Kokoro TTS (voice={Config.KOKORO_VOICE})")
        return KokoroTTS(
            base_url=Config.KOKORO_BASE_URL,
            api_key=Config.KOKORO_API_KEY,
            voice=Config.KOKORO_VOICE,
        )

    elif provider == "elevenlabs":
        from livekit.plugins import elevenlabs
        logger.info(f"Using ElevenLabs TTS (voice={Config.ELEVENLABS_VOICE_ID})")
        return elevenlabs.TTS(
            api_key=Config.ELEVENLABS_API_KEY,
            voice_id=Config.ELEVENLABS_VOICE_ID,
        )

    elif provider == "cartesia":
        from livekit.plugins import cartesia
        logger.info(f"Using Cartesia TTS (voice={Config.CARTESIA_VOICE_ID})")
        return cartesia.TTS(
            api_key=Config.CARTESIA_API_KEY,
            voice=Config.CARTESIA_VOICE_ID,
        )

    else:
        raise ValueError(f"Unknown TTS provider: {provider}. Use: kokoro, elevenlabs, cartesia")
