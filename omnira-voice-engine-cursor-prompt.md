# OMNIRA VOICE ENGINE — Cursor Build Prompt

## PROJECT OVERVIEW

You are building the **Omnira Voice Engine** — a self-hosted AI phone agent that handles inbound and outbound calls for dental practices. It uses LiveKit Agents as the orchestration framework, Deepgram for speech-to-text, Anthropic Claude for the LLM brain, and self-hosted Kokoro TTS for text-to-speech.

This is a **Python** project (LiveKit Agents Python SDK is more mature than the Node.js SDK and has full Anthropic plugin support). It will be deployed to **Railway** as a Docker container.

---

## WHAT TO BUILD

A single deployable service that:
1. Receives inbound phone calls via Twilio SIP → LiveKit SIP → LiveKit Agent
2. Transcribes caller speech in real-time (Deepgram Nova-2)
3. Processes with Claude Sonnet (Anthropic API) with tool calling
4. Responds with natural voice (Kokoro TTS self-hosted, with ElevenLabs as optional premium fallback)
5. Can execute tools mid-conversation: book appointments, send SMS, send email, transfer calls
6. Logs full transcripts of every call
7. Handles barge-in (caller interrupts the AI mid-sentence)
8. Runs 24/7 on Railway

---

## PROJECT STRUCTURE

```
omnira-voice-engine/
├── Dockerfile
├── docker-compose.yml          # Local dev with LiveKit server + agent
├── requirements.txt
├── .env.example                # Template for all required env vars
├── railway.toml                # Railway deployment config
├── README.md
├── agent/
│   ├── __init__.py
│   ├── main.py                 # Entry point — LiveKit agent worker
│   ├── voice_agent.py          # Agent definition with pipeline config
│   ├── tools.py                # All tool definitions (@ai_callable)
│   ├── prompts.py              # System prompt builder for the dental receptionist
│   ├── config.py               # Provider config loader (env-based)
│   └── logger.py               # Call transcript logger
├── tts/
│   ├── __init__.py
│   ├── kokoro_tts.py           # Custom Kokoro TTS plugin for LiveKit Agents
│   └── provider.py             # TTS provider factory (kokoro / elevenlabs / cartesia)
└── scripts/
    ├── test_call.py            # Quick test: initiate an outbound test call
    └── setup_twilio_sip.py     # Helper to configure Twilio SIP trunk
```

---

## STEP-BY-STEP BUILD INSTRUCTIONS

### Step 1: Initialize the project

```bash
mkdir omnira-voice-engine && cd omnira-voice-engine
python -m venv venv
source venv/bin/activate
```

### Step 2: Install dependencies

Create `requirements.txt`:

```
livekit-agents>=1.0.0
livekit-plugins-deepgram>=1.0.0
livekit-plugins-anthropic>=1.0.0
livekit-plugins-silero>=1.0.0
livekit>=1.0.0
livekit-api>=1.0.0
httpx>=0.27.0
python-dotenv>=1.0.0
resend>=2.0.0
twilio>=9.0.0
pydantic>=2.0.0
```

Run: `pip install -r requirements.txt`

### Step 3: Create `.env.example`

```env
# === LIVEKIT ===
LIVEKIT_URL=ws://localhost:7880
LIVEKIT_API_KEY=devkey
LIVEKIT_API_SECRET=secret

# === ANTHROPIC ===
ANTHROPIC_API_KEY=sk-ant-...

# === DEEPGRAM ===
DEEPGRAM_API_KEY=...

# === TTS PROVIDER (kokoro | elevenlabs | cartesia) ===
TTS_PROVIDER=kokoro
KOKORO_BASE_URL=http://localhost:3000
KOKORO_API_KEY=kokoro-local-key
KOKORO_VOICE=af_heart

# Optional: ElevenLabs (premium fallback)
ELEVENLABS_API_KEY=
ELEVENLABS_VOICE_ID=

# Optional: Cartesia (low-latency fallback)
CARTESIA_API_KEY=
CARTESIA_VOICE_ID=

# === TWILIO ===
TWILIO_ACCOUNT_SID=...
TWILIO_AUTH_TOKEN=...
TWILIO_PHONE_NUMBER=+1...

# === RESEND (Email) ===
RESEND_API_KEY=re_...
FROM_EMAIL=receptionist@omnira.space

# === OMNIRA API (your platform, for booking etc.) ===
OMNIRA_API_URL=http://localhost:3000/api
OMNIRA_API_KEY=...

# === PRACTICE CONFIG ===
PRACTICE_NAME=Demo Dental
PRACTICE_PHONE=+15551234567
PRACTICE_TIMEZONE=America/Los_Angeles
PRACTICE_HOURS=Mon-Fri 8am-5pm, Sat 9am-1pm
PRACTICE_ADDRESS=123 Main St, Suite 100, San Diego, CA 92101
```

### Step 4: Build `agent/config.py`

```python
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

    # Practice
    PRACTICE_NAME = os.getenv("PRACTICE_NAME", "Demo Dental")
    PRACTICE_PHONE = os.getenv("PRACTICE_PHONE", "")
    PRACTICE_TIMEZONE = os.getenv("PRACTICE_TIMEZONE", "America/Los_Angeles")
    PRACTICE_HOURS = os.getenv("PRACTICE_HOURS", "Mon-Fri 8am-5pm")
    PRACTICE_ADDRESS = os.getenv("PRACTICE_ADDRESS", "")
```

### Step 5: Build `agent/prompts.py`

```python
"""System prompt builder for the dental receptionist voice agent."""
from agent.config import Config


def build_system_prompt() -> str:
    return f"""You are the AI receptionist for {Config.PRACTICE_NAME}. You answer phone calls warmly and professionally, like a real dental office receptionist who has been working here for years.

## Your Personality
- Warm, friendly, and professional
- You speak naturally and conversationally — never robotic
- You keep responses SHORT (1-2 sentences for simple questions, 3-4 max for complex ones)
- You use the caller's name once you know it
- You say things like "absolutely", "of course", "let me check that for you"
- You NEVER say you are an AI. You are the receptionist.

## Practice Information
- Name: {Config.PRACTICE_NAME}
- Phone: {Config.PRACTICE_PHONE}
- Address: {Config.PRACTICE_ADDRESS}
- Hours: {Config.PRACTICE_HOURS}
- Timezone: {Config.PRACTICE_TIMEZONE}

## What You Can Do (use tools for these)
1. **Book appointments** — Ask for: patient name, preferred date/time, reason for visit. Use the book_appointment tool.
2. **Check availability** — Use check_availability tool to find open slots.
3. **Send confirmations** — After booking, offer to send an email or text confirmation. Use send_email or send_sms tools.
4. **Answer common questions** — Hours, location, directions, accepted insurance, parking info.
5. **Transfer to staff** — If the caller needs something you can't handle, say "Let me transfer you to our team" and use transfer_call tool.
6. **Take messages** — If the office is closed or staff is unavailable, take a message with name, number, and reason.

## Call Flow Guidelines
- Start with: "Thank you for calling {Config.PRACTICE_NAME}, this is Nira, how can I help you today?"
- If the caller asks to schedule: get their name first, then ask what they need (cleaning, checkup, toothache, etc.), then check availability and offer times.
- Always confirm details before booking: "So that's [name] for a [procedure] on [date] at [time], is that correct?"
- After booking: "You're all set! Would you like me to send you a confirmation text or email?"
- End calls with: "Thank you for calling {Config.PRACTICE_NAME}! Have a great day."

## Important Rules
- NEVER provide medical advice. For emergencies say: "If this is a dental emergency, I'd recommend going to the nearest emergency room or calling us back during business hours at {Config.PRACTICE_PHONE}."
- Keep responses SHORT for voice. Long responses sound terrible on the phone.
- If you're unsure about something, say "Let me check on that" and use the appropriate tool.
- If the caller is upset, be empathetic: "I completely understand, and I'm sorry about that. Let me see how I can help."
"""
```

### Step 6: Build `agent/tools.py`

```python
"""Tool definitions for the voice agent — these are the actions it can take during a call."""
import json
import logging
from datetime import datetime, timedelta

import httpx
import resend
from twilio.rest import Client as TwilioClient

from livekit.agents import function_tool, RunContext

from agent.config import Config

logger = logging.getLogger("omnira-tools")

# Initialize clients
twilio_client = TwilioClient(Config.TWILIO_ACCOUNT_SID, Config.TWILIO_AUTH_TOKEN) if Config.TWILIO_ACCOUNT_SID else None
resend.api_key = Config.RESEND_API_KEY


@function_tool(description="Check available appointment slots. Call this when a patient asks about availability.")
async def check_availability(
    context: RunContext,
    date: str,
    procedure_type: str = "general",
) -> str:
    """Check available appointment slots for a given date.

    Args:
        date: The date to check (YYYY-MM-DD format or natural language like 'next Tuesday')
        procedure_type: Type of appointment (general, cleaning, emergency, consultation)
    """
    # TODO: Replace with real Omnira/Stella API call
    # For MVP, return mock availability
    logger.info(f"Checking availability for {date}, procedure: {procedure_type}")

    # Mock response — replace with actual API call:
    # async with httpx.AsyncClient() as client:
    #     resp = await client.get(f"{Config.OMNIRA_API_URL}/availability",
    #         params={"date": date, "procedure": procedure_type},
    #         headers={"Authorization": f"Bearer {Config.OMNIRA_API_KEY}"})
    #     return resp.text

    return json.dumps({
        "available_slots": [
            {"time": "9:00 AM", "provider": "Dr. Smith"},
            {"time": "10:30 AM", "provider": "Dr. Smith"},
            {"time": "2:00 PM", "provider": "Dr. Johnson"},
            {"time": "3:30 PM", "provider": "Dr. Johnson"},
        ],
        "date": date,
    })


@function_tool(description="Book an appointment for a patient. Use this after confirming details with the caller.")
async def book_appointment(
    context: RunContext,
    patient_name: str,
    date: str,
    time: str,
    procedure_type: str,
    patient_phone: str = "",
    patient_email: str = "",
) -> str:
    """Book an appointment.

    Args:
        patient_name: Full name of the patient
        date: Appointment date (YYYY-MM-DD)
        time: Appointment time (e.g., '9:00 AM')
        procedure_type: Type of procedure (cleaning, checkup, emergency, etc.)
        patient_phone: Patient phone number (optional)
        patient_email: Patient email address (optional)
    """
    logger.info(f"Booking: {patient_name} on {date} at {time} for {procedure_type}")

    # TODO: Replace with real Omnira/Stella API call
    # async with httpx.AsyncClient() as client:
    #     resp = await client.post(f"{Config.OMNIRA_API_URL}/appointments",
    #         json={"patient_name": patient_name, "date": date, "time": time,
    #               "procedure": procedure_type, "phone": patient_phone, "email": patient_email},
    #         headers={"Authorization": f"Bearer {Config.OMNIRA_API_KEY}"})
    #     return resp.text

    return json.dumps({
        "status": "confirmed",
        "appointment_id": "APT-2026-001",
        "patient_name": patient_name,
        "date": date,
        "time": time,
        "procedure": procedure_type,
        "message": f"Appointment booked for {patient_name} on {date} at {time} for {procedure_type}."
    })


@function_tool(description="Send a confirmation SMS to the patient. Use after booking an appointment.")
async def send_sms(
    context: RunContext,
    to_phone: str,
    message: str,
) -> str:
    """Send an SMS message via Twilio.

    Args:
        to_phone: Recipient phone number (E.164 format, e.g., +15551234567)
        message: The SMS message text
    """
    logger.info(f"Sending SMS to {to_phone}: {message[:50]}...")

    if not twilio_client:
        return "SMS service not configured. Message noted for staff follow-up."

    try:
        msg = twilio_client.messages.create(
            body=message,
            from_=Config.TWILIO_PHONE_NUMBER,
            to=to_phone,
        )
        return f"Confirmation text sent successfully to {to_phone}."
    except Exception as e:
        logger.error(f"SMS failed: {e}")
        return "I wasn't able to send the text right now, but I've noted the appointment details."


@function_tool(description="Send a confirmation email to the patient. Use after booking an appointment.")
async def send_email(
    context: RunContext,
    to_email: str,
    subject: str,
    body: str,
) -> str:
    """Send an email via Resend.

    Args:
        to_email: Recipient email address
        subject: Email subject line
        body: Email body text (plain text)
    """
    logger.info(f"Sending email to {to_email}: {subject}")

    if not Config.RESEND_API_KEY:
        return "Email service not configured. Message noted for staff follow-up."

    try:
        email = resend.Emails.send({
            "from": Config.FROM_EMAIL,
            "to": [to_email],
            "subject": subject,
            "text": body,
        })
        return f"Confirmation email sent successfully to {to_email}."
    except Exception as e:
        logger.error(f"Email failed: {e}")
        return "I wasn't able to send the email right now, but your appointment is confirmed."


@function_tool(description="Transfer the call to a human staff member. Use when the caller needs something you cannot handle.")
async def transfer_call(
    context: RunContext,
    reason: str,
    department: str = "front_desk",
) -> str:
    """Transfer the current call to human staff.

    Args:
        reason: Brief reason for the transfer
        department: Which department to transfer to (front_desk, billing, clinical)
    """
    logger.info(f"Call transfer requested: {reason} → {department}")
    # In production, this would trigger a LiveKit SIP transfer
    # For now, return a message
    return f"I'm transferring you now to our {department.replace('_', ' ')} team. One moment please."
```

### Step 7: Build `tts/kokoro_tts.py`

```python
"""Custom Kokoro TTS plugin for LiveKit Agents.

Kokoro-82M is self-hosted via kokoro-web Docker container which provides
an OpenAI-compatible TTS API. This plugin wraps it for LiveKit Agents.
"""
import asyncio
import io
import logging
from typing import AsyncIterable

import httpx

from livekit.agents.tts import TTS, SynthesizedAudio, SynthesizeStream

logger = logging.getLogger("kokoro-tts")


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
            capabilities=TTS.Capabilities(streaming=False),
            sample_rate=sample_rate,
            num_channels=1,
        )
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._voice = voice
        self._model = model
        self._speed = speed
        self._client = httpx.AsyncClient(timeout=30.0)

    async def synthesize(self, text: str) -> SynthesizedAudio:
        """Synthesize text to audio using Kokoro API."""
        try:
            response = await self._client.post(
                f"{self._base_url}/api/v1/audio/speech",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self._model,
                    "voice": self._voice,
                    "input": text,
                    "speed": self._speed,
                    "response_format": "pcm",
                },
            )
            response.raise_for_status()

            # kokoro-web returns raw audio bytes
            audio_data = response.content

            return SynthesizedAudio(
                text=text,
                data=audio_data,
                sample_rate=self._sample_rate,
                num_channels=self._num_channels,
            )

        except Exception as e:
            logger.error(f"Kokoro TTS synthesis failed: {e}")
            raise

    async def aclose(self):
        await self._client.aclose()
```

### Step 8: Build `tts/provider.py`

```python
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
```

### Step 9: Build `agent/logger.py`

```python
"""Call transcript logger — logs every call for HIPAA compliance."""
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
```

### Step 10: Build `agent/voice_agent.py`

```python
"""Omnira Voice Agent — the main agent definition."""
import logging
import uuid

from livekit.agents import Agent, AgentSession, RoomInputOptions
from livekit.agents.voice import MetricsCollectedEvent
from livekit.plugins import deepgram, silero, anthropic

from agent.config import Config
from agent.prompts import build_system_prompt
from agent.tools import check_availability, book_appointment, send_sms, send_email, transfer_call
from agent.logger import CallLogger
from tts.provider import get_tts

logger = logging.getLogger("omnira-agent")


class OmniraReceptionist(Agent):
    """The Omnira dental receptionist voice agent."""

    def __init__(self):
        super().__init__(
            instructions=build_system_prompt(),
        )
        self.call_logger = CallLogger(call_id=str(uuid.uuid4()))
        logger.info(f"New agent created for call {self.call_logger.call_id}")

    async def on_enter(self):
        """Called when the agent joins. Start with a greeting."""
        self.session.generate_reply(
            instructions="Greet the caller warmly. Say: Thank you for calling "
            f"{Config.PRACTICE_NAME}, this is Nira, how can I help you today?"
        )


def create_agent_session() -> AgentSession:
    """Create a configured AgentSession with all providers."""
    tts = get_tts()

    session = AgentSession(
        vad=silero.VAD.load(),
        stt=deepgram.STT(
            api_key=Config.DEEPGRAM_API_KEY,
            model="nova-2",
            language="en",
        ),
        llm=anthropic.LLM(
            api_key=Config.ANTHROPIC_API_KEY,
            model="claude-sonnet-4-5-20250929",
        ),
        tts=tts,
        # Register tools
        tools=[
            check_availability,
            book_appointment,
            send_sms,
            send_email,
            transfer_call,
        ],
    )

    return session
```

### Step 11: Build `agent/main.py`

```python
"""Entry point — LiveKit Agent worker."""
import asyncio
import logging

from dotenv import load_dotenv
from livekit.agents import WorkerOptions, cli

from agent.voice_agent import OmniraReceptionist, create_agent_session

# Load environment
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("omnira")


async def entrypoint(ctx):
    """Handle a new call/room connection."""
    logger.info(f"New connection: room={ctx.room.name}")

    # Wait for a participant to join (the caller)
    await ctx.wait_for_participant()

    # Create the agent session with all providers
    session = create_agent_session()

    # Start the agent
    agent = OmniraReceptionist()
    await session.start(
        agent=agent,
        room=ctx.room,
    )

    logger.info(f"Agent started in room {ctx.room.name}")


if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
        ),
    )
```

### Step 12: Build `Dockerfile`

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# LiveKit agents CLI entry point
# 'start' runs in production mode (vs 'dev' for development)
CMD ["python", "-m", "agent.main", "start"]
```

### Step 13: Build `docker-compose.yml` (local development)

```yaml
version: "3.8"

services:
  # LiveKit server (local dev)
  livekit-server:
    image: livekit/livekit-server:latest
    command: --dev --bind 0.0.0.0
    ports:
      - "7880:7880"   # HTTP/WebSocket
      - "7881:7881"   # RTC (WebRTC)
      - "7882:7882"   # TURN/TCP
    environment:
      - LIVEKIT_KEYS=devkey: secret

  # Kokoro TTS (self-hosted)
  kokoro-tts:
    image: ghcr.io/eduardolat/kokoro-web:latest
    ports:
      - "3001:3000"
    environment:
      - KW_SECRET_API_KEY=kokoro-local-key
    volumes:
      - kokoro-cache:/kokoro/cache
    # Note: CPU inference is slower. For GPU, use NVIDIA runtime:
    # deploy:
    #   resources:
    #     reservations:
    #       devices:
    #         - driver: nvidia
    #           count: 1
    #           capabilities: [gpu]

  # Omnira Voice Agent
  omnira-agent:
    build: .
    depends_on:
      - livekit-server
      - kokoro-tts
    env_file:
      - .env
    environment:
      - LIVEKIT_URL=ws://livekit-server:7880
      - KOKORO_BASE_URL=http://kokoro-tts:3000

volumes:
  kokoro-cache:
```

### Step 14: Build `railway.toml`

```toml
[build]
builder = "DOCKERFILE"
dockerfilePath = "Dockerfile"

[deploy]
startCommand = "python -m agent.main start"
restartPolicyType = "ON_FAILURE"
restartPolicyMaxRetries = 5
```

### Step 15: Build `scripts/test_call.py`

```python
"""Quick test — create a LiveKit room and connect via browser to test the agent.

Run: python scripts/test_call.py

This will print a URL you can open in your browser to talk to the agent.
"""
import asyncio
import os

from dotenv import load_dotenv
from livekit import api

load_dotenv()


async def main():
    lk_api = api.LiveKitAPI(
        os.getenv("LIVEKIT_URL", "http://localhost:7880"),
        os.getenv("LIVEKIT_API_KEY", "devkey"),
        os.getenv("LIVEKIT_API_SECRET", "secret"),
    )

    # Create a room
    room = await lk_api.room.create_room(
        api.CreateRoomRequest(name="test-call-001")
    )
    print(f"Room created: {room.name}")

    # Generate a token for the test caller
    token = (
        api.AccessToken(
            os.getenv("LIVEKIT_API_KEY", "devkey"),
            os.getenv("LIVEKIT_API_SECRET", "secret"),
        )
        .with_identity("test-caller")
        .with_grants(
            api.VideoGrants(
                room_join=True,
                room=room.name,
            )
        )
        .to_jwt()
    )

    print(f"\n{'='*60}")
    print(f"TEST YOUR AGENT")
    print(f"{'='*60}")
    print(f"\nOpen the LiveKit Agents Playground:")
    print(f"https://agents-playground.livekit.io/")
    print(f"\nOr connect manually with this token:")
    print(f"Room: {room.name}")
    print(f"Token: {token[:50]}...")
    print(f"\nLiveKit URL: {os.getenv('LIVEKIT_URL', 'ws://localhost:7880')}")
    print(f"{'='*60}\n")

    await lk_api.aclose()


if __name__ == "__main__":
    asyncio.run(main())
```

### Step 16: Build `README.md`

```markdown
# Omnira Voice Engine

AI-powered phone receptionist for dental practices. Built with LiveKit Agents, Deepgram, Claude, and Kokoro TTS.

## Quick Start (Local Development)

### 1. Clone and configure
```bash
cp .env.example .env
# Edit .env with your API keys (see "Required API Keys" below)
```

### 2. Start all services
```bash
docker compose up -d
```

This starts:
- **LiveKit Server** on port 7880 (local dev mode)
- **Kokoro TTS** on port 3001 (self-hosted voice)
- **Omnira Agent** (connects to LiveKit + Kokoro)

### 3. Test via browser
```bash
python scripts/test_call.py
```

Open the LiveKit Agents Playground at https://agents-playground.livekit.io/ and connect using the local LiveKit URL.

### 4. Test via phone (requires Twilio SIP setup)
See [Twilio SIP Setup Guide](#twilio-sip-setup) below.

## Required API Keys

| Key | Where to get it | Required? |
|-----|-----------------|-----------|
| `ANTHROPIC_API_KEY` | https://console.anthropic.com | **Yes** |
| `DEEPGRAM_API_KEY` | https://console.deepgram.com | **Yes** |
| `TWILIO_ACCOUNT_SID` | https://console.twilio.com | For phone calls |
| `TWILIO_AUTH_TOKEN` | https://console.twilio.com | For phone calls |
| `RESEND_API_KEY` | https://resend.com | For email sending |
| `ELEVENLABS_API_KEY` | https://elevenlabs.io | Optional premium TTS |
| `CARTESIA_API_KEY` | https://cartesia.ai | Optional low-latency TTS |

## Switching TTS Provider

Change one env var:
```bash
TTS_PROVIDER=kokoro        # Free, self-hosted (default)
TTS_PROVIDER=elevenlabs    # Premium quality
TTS_PROVIDER=cartesia      # Lowest latency
```

## Deploy to Railway

1. Push to GitHub
2. Connect repo to Railway
3. Add environment variables in Railway dashboard
4. Deploy

For Kokoro TTS on Railway, deploy it as a separate service in the same Railway project.

## Architecture

```
Phone Call → Twilio SIP → LiveKit SIP → LiveKit Room → Agent Worker
                                                          ├── Deepgram (STT)
                                                          ├── Claude Sonnet (LLM)
                                                          ├── Kokoro TTS (voice)
                                                          └── Tools (book, SMS, email)
```
```

---

## API KEYS YOU NEED TO PROVIDE

Before running, you need these keys:

| # | Key | Get it from | Time to get | Free tier? |
|---|-----|------------|-------------|------------|
| 1 | **ANTHROPIC_API_KEY** | https://console.anthropic.com/settings/keys | 2 min | $5 free credit |
| 2 | **DEEPGRAM_API_KEY** | https://console.deepgram.com → Settings → API Keys | 2 min | $200 free credit |
| 3 | **TWILIO_ACCOUNT_SID + AUTH_TOKEN** | https://console.twilio.com | 5 min | $15 free trial |
| 4 | **TWILIO_PHONE_NUMBER** | Twilio Console → Buy a Number | 2 min | 1 free with trial |
| 5 | **RESEND_API_KEY** | https://resend.com/api-keys | 2 min | 100 emails/day free |
| 6 | *Optional:* ELEVENLABS_API_KEY | https://elevenlabs.io | 2 min | 10K chars/month free |

**Minimum to test in 20 minutes:** You only need #1 (Anthropic) and #2 (Deepgram). Kokoro TTS runs locally via Docker. You can test voice via browser using LiveKit Playground — no Twilio needed for initial test.

---

## LOCAL TEST (NO TWILIO NEEDED)

The fastest path to hearing your agent talk:

```bash
# 1. Copy env and add just Anthropic + Deepgram keys
cp .env.example .env
# Edit: ANTHROPIC_API_KEY and DEEPGRAM_API_KEY

# 2. Start everything
docker compose up -d

# 3. Wait ~60 seconds for Kokoro to download the model on first run

# 4. Run the agent in dev mode
python -m agent.main dev

# 5. Open https://agents-playground.livekit.io/
# Set URL to: ws://localhost:7880
# Set API Key to: devkey
# Set API Secret to: secret
# Click Connect → Talk to your agent!
```

---

## IMPORTANT NOTES FOR CURSOR

1. **LiveKit Agents v1.0 API**: The API recently changed. Use `AgentSession` and `Agent` base class, NOT the old `VoicePipelineAgent`. Check the latest docs at https://docs.livekit.io/agents/ if something doesn't match.

2. **Kokoro TTS plugin**: There is NO official LiveKit plugin for Kokoro. The `tts/kokoro_tts.py` file is a CUSTOM plugin that calls the kokoro-web OpenAI-compatible API. If the LiveKit TTS interface has changed, adapt the class to match the current `livekit.agents.tts.TTS` base class.

3. **Python version**: Use Python 3.12+. LiveKit Agents requires >= 3.10, but 3.12 has the best asyncio performance.

4. **The tools use mock data for MVP**: `check_availability` and `book_appointment` return hardcoded responses. This is intentional — test the voice flow first, then wire to real APIs.

5. **Railway deployment**: Deploy the Kokoro TTS container as a separate Railway service in the same project. The agent service connects to it via private networking (`KOKORO_BASE_URL=http://kokoro-tts.railway.internal:3000`).

6. **If Kokoro TTS is too slow on CPU**: The Docker container runs on CPU by default. For production, use a Railway GPU instance or switch `TTS_PROVIDER=cartesia` (API-based, no GPU needed). Kokoro on CPU may have 1-3 second latency; on GPU it's sub-300ms.

7. **LiveKit server for production**: For Railway deployment, use LiveKit Cloud (free tier: 50 participant-hours/month) instead of self-hosting the LiveKit server. Set `LIVEKIT_URL` to your LiveKit Cloud project URL. Get it at https://cloud.livekit.io/.
