"""Custom Kokoro TTS plugin for LiveKit Agents.

Kokoro-82M is self-hosted via kokoro-web Docker container which provides
an OpenAI-compatible TTS API. This plugin wraps it for LiveKit Agents.
"""
import logging
from dataclasses import dataclass

import httpx

from livekit.agents import utils
from livekit.agents.tts import (
    TTS,
    TTSCapabilities,
    ChunkedStream as BaseChunkedStream,
    AudioEmitter,
)
from livekit.agents.types import DEFAULT_API_CONNECT_OPTIONS, APIConnectOptions

logger = logging.getLogger("kokoro-tts")


@dataclass
class _KokoroOptions:
    base_url: str
    api_key: str
    voice: str
    model: str
    speed: float
    sample_rate: int


class ChunkedStream(BaseChunkedStream):
    def __init__(
        self,
        *,
        tts: "KokoroTTS",
        input_text: str,
        conn_options: APIConnectOptions,
        opts: _KokoroOptions,
    ) -> None:
        super().__init__(tts=tts, input_text=input_text, conn_options=conn_options)
        self._opts = opts

    async def _run(self, output_emitter: AudioEmitter) -> None:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self._opts.base_url}/api/v1/audio/speech",
                headers={
                    "Authorization": f"Bearer {self._opts.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self._opts.model,
                    "voice": self._opts.voice,
                    "input": self._input_text,
                    "speed": self._opts.speed,
                    "response_format": "mp3",
                },
            )
            response.raise_for_status()

            output_emitter.initialize(
                request_id=utils.shortuuid(),
                sample_rate=self._opts.sample_rate,
                num_channels=1,
                mime_type="audio/mpeg",
            )

            output_emitter.push(response.content)
            output_emitter.flush()


class KokoroTTS(TTS):
    """Kokoro TTS via kokoro-web OpenAI-compatible API."""

    def __init__(
        self,
        *,
        base_url: str = "http://localhost:3000",
        api_key: str = "kokoro-key",
        voice: str = "af_heart",
        model: str = "model_q8f16",
        speed: float = 1.0,
        sample_rate: int = 24000,
    ):
        super().__init__(
            capabilities=TTSCapabilities(streaming=False),
            sample_rate=sample_rate,
            num_channels=1,
        )
        self._opts = _KokoroOptions(
            base_url=base_url.rstrip("/"),
            api_key=api_key,
            voice=voice,
            model=model,
            speed=speed,
            sample_rate=sample_rate,
        )

    def synthesize(
        self,
        text: str,
        *,
        conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS,
    ) -> ChunkedStream:
        return ChunkedStream(
            tts=self,
            input_text=text,
            conn_options=conn_options,
            opts=self._opts,
        )
