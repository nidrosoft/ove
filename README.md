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

## Local Test (No Twilio Needed)

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

## Twilio SIP Setup

Run the helper script:
```bash
python scripts/setup_twilio_sip.py
```

Or manually:
1. Create a SIP Trunk in Twilio Console
2. Set the Origination URI to your LiveKit SIP endpoint
3. Point your Twilio phone number to the SIP Trunk
