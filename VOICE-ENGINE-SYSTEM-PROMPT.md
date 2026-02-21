# Voice Engine — System Prompt for Cursor AI

> Copy everything below this line into a new Cursor workspace as the system prompt or CLAUDE.md / .cursorrules file to guide the AI in building this project from scratch.

---

## Project Overview

You are building **Omnira Voice Engine** — a standalone, self-hosted real-time voice AI agent server that handles inbound and outbound phone calls for dental practices. This is the voice layer for the Omnira dental practice management platform.

The engine receives phone calls via Twilio, transcribes the caller's speech in real-time using Deepgram, processes it through an LLM (Claude or GPT-4o), converts the AI response to speech using ElevenLabs, and streams the audio back to the caller — all in real-time with sub-second latency.

This is NOT a chatbot. This is a real-time bidirectional voice conversation system that must handle:
- Natural turn-taking (the caller can interrupt the AI mid-sentence)
- Sub-800ms round-trip latency (transcription → LLM → TTS → audio)
- Tool calling during the conversation (look up patients, book appointments, send emails/SMS)
- Graceful call transfers to a human
- Call recording, transcription, and summary generation
- Webhook notifications to the parent platform (Omnira) for live activity updates

## Architecture

```
                    PSTN / Mobile
                        │
                   ┌────▼────┐
                   │  Twilio  │  (Phone numbers, SIP, call routing)
                   └────┬────┘
                        │ WebSocket (Media Stream)
                   ┌────▼────────────────────────────┐
                   │     OMNIRA VOICE ENGINE          │
                   │  (Node.js / TypeScript server)   │
                   │                                  │
                   │  ┌──────────┐  ┌──────────────┐  │
                   │  │  Twilio   │  │  Session      │  │
                   │  │  Media    │→ │  Manager      │  │
                   │  │  Handler  │  │  (per-call)   │  │
                   │  └──────────┘  └──────┬───────┘  │
                   │                       │          │
                   │         ┌─────────────┼──────────┤
                   │         │             │          │
                   │  ┌──────▼──┐  ┌───────▼───┐     │
                   │  │ Deepgram │  │    LLM     │     │
                   │  │  STT     │  │ (Claude/   │     │
                   │  │ (stream) │  │  GPT-4o)   │     │
                   │  └─────────┘  └───────┬───┘     │
                   │                       │          │
                   │                ┌──────▼──────┐   │
                   │                │  ElevenLabs  │   │
                   │                │  TTS (stream)│   │
                   │                └──────┬──────┘   │
                   │                       │          │
                   │              Audio back to Twilio │
                   └──────────────────────────────────┘
                        │
                   ┌────▼────────────────┐
                   │   Omnira Platform    │  (Next.js on Vercel)
                   │   - Webhooks         │
                   │   - REST API         │
                   │   - Activity bus     │
                   └─────────────────────┘
```

## Tech Stack

| Component | Technology | Why |
|-----------|-----------|-----|
| Runtime | **Node.js 20+ / TypeScript** | WebSocket support, streaming, async |
| Framework | **Fastify** (preferred) or Express | Fast, WebSocket-native, schema validation |
| Telephony | **Twilio Voice + Media Streams** | Industry standard, phone numbers, SIP, call routing |
| STT | **Deepgram Nova-2** | Fastest real-time STT (~100ms), streaming WebSocket API |
| LLM | **Anthropic Claude 3.5 Sonnet** (primary), **OpenAI GPT-4o** (fallback) | Tool calling, fast streaming, high quality |
| TTS | **ElevenLabs** (primary), **Cartesia** (low-latency alternative) | Most natural voices, streaming WebSocket API |
| Package Manager | **pnpm** | Fast, disk efficient |
| Deployment | **Railway** or **Fly.io** | Persistent servers, WebSocket support, auto-scaling |
| Monitoring | **Sentry** | Error tracking, performance monitoring |

## Project Structure

```
omnira-voice-engine/
├── src/
│   ├── server.ts                    # Fastify server entry point
│   ├── config.ts                    # Environment config with validation
│   │
│   ├── telephony/
│   │   ├── twilio-handler.ts        # Twilio webhook handlers (incoming call, status)
│   │   ├── media-stream.ts          # Twilio Media Stream WebSocket handler
│   │   └── dtmf.ts                  # DTMF tone handling
│   │
│   ├── stt/
│   │   ├── provider.ts              # STT provider interface
│   │   ├── deepgram.ts              # Deepgram streaming STT implementation
│   │   └── whisper.ts               # Whisper fallback (optional)
│   │
│   ├── tts/
│   │   ├── provider.ts              # TTS provider interface
│   │   ├── elevenlabs.ts            # ElevenLabs streaming TTS implementation
│   │   ├── cartesia.ts              # Cartesia alternative (optional)
│   │   └── audio-buffer.ts          # Audio buffering and streaming utilities
│   │
│   ├── llm/
│   │   ├── provider.ts              # LLM provider interface
│   │   ├── claude.ts                # Anthropic Claude implementation
│   │   ├── openai.ts                # OpenAI GPT-4o implementation
│   │   └── tool-handler.ts          # Tool call execution and result handling
│   │
│   ├── agent/
│   │   ├── session.ts               # Call session state machine
│   │   ├── conversation.ts          # Conversation history manager
│   │   ├── prompt-builder.ts        # System prompt construction per-practice
│   │   ├── interruption.ts          # Barge-in / interruption detection
│   │   └── turn-detection.ts        # End-of-turn detection (silence, endpointing)
│   │
│   ├── tools/
│   │   ├── index.ts                 # Tool registry and definitions
│   │   ├── omnira-api.ts            # HTTP client for Omnira platform API
│   │   ├── patient-lookup.ts        # Look up patient by phone/name
│   │   ├── book-appointment.ts      # Book/confirm/reschedule appointment
│   │   ├── send-email.ts            # Trigger email via Omnira API
│   │   ├── send-sms.ts              # Trigger SMS via Omnira API
│   │   ├── transfer-call.ts         # Warm transfer to human staff
│   │   └── collect-info.ts          # Structured data collection helper
│   │
│   ├── pipeline/
│   │   ├── audio-pipeline.ts        # Main audio processing pipeline
│   │   ├── stream-coordinator.ts    # Coordinates STT→LLM→TTS streaming
│   │   └── vad.ts                   # Voice Activity Detection
│   │
│   ├── webhooks/
│   │   ├── omnira-notifier.ts       # Push events to Omnira (call started, ended, action taken)
│   │   └── call-completed.ts        # Post-call processing (summary, transcript, recording)
│   │
│   ├── storage/
│   │   ├── call-store.ts            # In-memory + persistent call state
│   │   └── recording.ts             # Call recording to S3/R2
│   │
│   └── utils/
│       ├── audio.ts                 # Audio format conversion (mulaw ↔ PCM ↔ opus)
│       ├── logger.ts                # Structured logging
│       └── metrics.ts               # Latency tracking, call metrics
│
├── .env.example                     # Environment variables template
├── package.json
├── tsconfig.json
├── Dockerfile                       # For Railway/Fly.io deployment
└── README.md
```

## Environment Variables

```env
# Server
PORT=3001
NODE_ENV=production
ENGINE_API_KEY=<secret key for authenticating requests from Omnira>

# Twilio
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_PHONE_NUMBER=+1XXXXXXXXXX

# Deepgram
DEEPGRAM_API_KEY=

# Anthropic (primary LLM)
ANTHROPIC_API_KEY=

# OpenAI (fallback LLM)
OPENAI_API_KEY=

# ElevenLabs
ELEVENLABS_API_KEY=
ELEVENLABS_VOICE_ID=<default voice ID>

# Omnira Platform (webhook target)
OMNIRA_API_URL=https://your-omnira-app.vercel.app
OMNIRA_WEBHOOK_SECRET=<shared secret for authenticating webhooks to Omnira>

# Storage (for recordings)
S3_BUCKET=
S3_REGION=
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=

# Sentry
SENTRY_DSN=
```

## Core Concepts

### 1. Call Session Lifecycle

Every inbound call creates a `CallSession` object that manages the entire call lifecycle:

```typescript
interface CallSession {
  id: string;                    // Unique session ID
  callSid: string;               // Twilio Call SID
  practiceId: string;            // Which dental practice this call belongs to
  callerNumber: string;          // E.164 phone number of the caller
  practiceNumber: string;        // Which practice number was dialed
  state: 'ringing' | 'greeting' | 'conversation' | 'transferring' | 'ended';
  startedAt: Date;
  conversation: ConversationMessage[];  // Full conversation history for LLM context
  collectedInfo: Record<string, unknown>;  // Patient info collected during call
  tools: ToolDefinition[];       // Available tools for this session
  metadata: {
    practiceConfig: PracticeConfig;  // Fetched from Omnira API at call start
    patientMatch?: PatientInfo;      // If caller's number matches a known patient
  };
}
```

### 2. Audio Pipeline Flow

The core real-time loop works like this:

```
Twilio sends audio chunks (mulaw 8kHz, 20ms frames) via WebSocket
    ↓
Convert mulaw → PCM 16-bit (for Deepgram)
    ↓
Stream PCM to Deepgram WebSocket → receive interim/final transcripts
    ↓
On final transcript (end of utterance):
    - Add caller message to conversation history
    - Send full conversation to LLM (Claude) with tool definitions
    ↓
LLM streams response tokens:
    - If tool_use: execute tool, add result, re-prompt LLM
    - If text: stream text chunks to ElevenLabs TTS WebSocket
    ↓
ElevenLabs streams audio chunks (PCM/opus)
    ↓
Convert to mulaw 8kHz → send back to Twilio WebSocket
    ↓
Caller hears the AI response
```

### 3. Interruption Handling (Barge-In)

When the AI is speaking and the caller starts talking:
1. Deepgram detects speech (VAD)
2. Immediately stop sending TTS audio to Twilio
3. Send a `<clear>` message to Twilio to flush the audio buffer
4. Cancel the in-progress TTS generation
5. Wait for the caller's full utterance
6. Process the new input normally

This must feel natural — the AI should stop talking within 200ms of the caller starting to speak.

### 4. Tool Calling

The LLM has access to tools that interact with the Omnira platform via HTTP API:

```typescript
const tools = [
  {
    name: "lookup_patient",
    description: "Look up a patient by phone number or name in the practice's system",
    parameters: {
      phone?: string,    // E.164 format
      name?: string,     // First and/or last name
    }
  },
  {
    name: "check_availability",
    description: "Check available appointment slots for a given date range and provider",
    parameters: {
      date: string,           // ISO date or natural language ("next Tuesday")
      provider_name?: string, // Specific dentist
      procedure_type?: string // "cleaning", "filling", etc.
    }
  },
  {
    name: "book_appointment",
    description: "Book an appointment for the caller",
    parameters: {
      patient_name: string,
      date: string,
      time: string,
      procedure_type: string,
      provider_name?: string,
      is_new_patient: boolean
    }
  },
  {
    name: "send_confirmation_email",
    description: "Send a confirmation email to the patient",
    parameters: {
      email: string,
      subject: string,
      body: string
    }
  },
  {
    name: "send_sms",
    description: "Send an SMS to the patient",
    parameters: {
      phone: string,
      message: string
    }
  },
  {
    name: "transfer_to_staff",
    description: "Transfer the call to a human staff member",
    parameters: {
      reason: string,
      department?: string  // "front_desk", "billing", "clinical"
    }
  },
  {
    name: "collect_patient_info",
    description: "Store collected patient information for post-call processing",
    parameters: {
      field: string,   // "first_name", "last_name", "email", "insurance", etc.
      value: string
    }
  }
];
```

Each tool calls the Omnira platform API:
```
POST https://omnira-app.vercel.app/api/voice-engine/actions
Authorization: Bearer <ENGINE_API_KEY>
{
  "action": "book_appointment",
  "practice_id": "uuid",
  "call_session_id": "uuid",
  "params": { ... }
}
```

### 5. Omnira Integration API

The voice engine communicates with Omnira via two channels:

**A. Omnira → Voice Engine (REST API)**
Omnira calls the voice engine to:
- Provision a practice (assign phone number, configure voice/prompt)
- Initiate an outbound call
- Get call status
- List active calls

```
POST /api/v1/practices          # Register a practice with its config
POST /api/v1/calls/outbound     # Initiate an outbound call
GET  /api/v1/calls/:callSid     # Get call status
GET  /api/v1/calls/active       # List active calls
DELETE /api/v1/calls/:callSid   # End a call
```

**B. Voice Engine → Omnira (Webhooks)**
The voice engine pushes events to Omnira:

```typescript
// Events sent to Omnira's webhook endpoint
type VoiceEngineEvent =
  | { event: "call.started"; call_sid: string; practice_id: string; caller_number: string; started_at: string }
  | { event: "call.ended"; call_sid: string; practice_id: string; duration_seconds: number; summary: string; transcript: TranscriptEntry[]; collected_info: Record<string, unknown>; recording_url?: string; sentiment: string; tags: string[] }
  | { event: "call.action"; call_sid: string; practice_id: string; action: string; details: Record<string, unknown> }  // e.g., "sent_email", "booked_appointment"
  | { event: "call.transferred"; call_sid: string; practice_id: string; reason: string; transferred_to: string }
  | { event: "call.error"; call_sid: string; practice_id: string; error: string }
```

### 6. Practice Configuration

When a practice is registered, the engine fetches/stores its configuration:

```typescript
interface PracticeConfig {
  id: string;
  name: string;                    // "Great Smiles of La Mesa"
  phone_numbers: string[];         // Twilio numbers assigned to this practice
  timezone: string;                // "America/Los_Angeles"
  greeting: string;                // "Thanks for calling Great Smiles, this is Sharon. How can I help you today?"
  voice_id: string;                // ElevenLabs voice ID
  voice_name: string;              // "Sharon" — the persona name used in conversation
  knowledge_base: string;          // Practice info, services, providers, insurance, hours
  operating_hours: { day: string; open: string; close: string }[];
  providers: { name: string; title: string; specialties: string[] }[];
  services: { name: string; description: string; price_range?: string }[];
  transfer_number?: string;        // Phone number to transfer to for human staff
  omnira_api_url: string;          // Where to call for tool actions
  omnira_api_key: string;          // API key for this practice's Omnira instance
  max_call_duration_seconds: number; // Default 600 (10 minutes)
  language: string;                // "en-US"
  new_patient_special?: string;    // Promotion text for new patients
}
```

### 7. System Prompt Template

The LLM receives a system prompt built from the practice config. Here is the template:

```
You are {voice_name}, the AI receptionist at {practice_name}. You are answering a phone call.

## Your Role
You handle incoming calls for the dental practice. You can:
- Answer questions about services, providers, hours, insurance, and pricing
- Schedule, confirm, and reschedule appointments
- Collect new patient information
- Send confirmation emails and text messages
- Transfer calls to staff when needed

## Practice Information
{knowledge_base}

## Conversation Rules
1. Be warm, professional, and empathetic. You represent the practice.
2. Keep responses concise — this is a phone call, not a chat. 1-3 sentences per turn.
3. Never say "um", "uh", or filler words. Speak naturally but efficiently.
4. If you don't know something, say so honestly and offer to transfer to staff.
5. Always confirm details before booking: date, time, patient name, procedure.
6. For new patients, collect: full name, phone, email, insurance (if any), reason for visit.
7. Proactively mention the new patient special if applicable: {new_patient_special}
8. If the caller asks to speak to a person, transfer immediately — don't argue.
9. At the end of the call, summarize what was done and what happens next.
10. Never reveal you are AI unless directly asked. If asked, say "I'm {voice_name}, the AI assistant for {practice_name}."

## Operating Hours
{formatted_hours}

## Providers
{formatted_providers}

## Services
{formatted_services}

## Current Date/Time
{current_datetime} ({timezone})

## Important
- You are on a PHONE CALL. Responses must be spoken aloud — no markdown, no bullet points, no links, no emojis.
- Keep responses SHORT. The caller is listening, not reading.
- Use natural spoken English. Say "one hundred fifty dollars" not "$150".
- Spell out abbreviations. Say "doctor" not "Dr."
- When giving phone numbers, say each digit with pauses.
- If the call is about an emergency, advise them to call 911 or go to the nearest ER immediately.
```

### 8. Twilio Webhook Setup

When Twilio receives an incoming call to a practice's number, it hits:

```
POST https://your-voice-engine.railway.app/api/v1/twilio/incoming
```

The handler responds with TwiML that starts a Media Stream:

```xml
<Response>
  <Connect>
    <Stream url="wss://your-voice-engine.railway.app/api/v1/twilio/media-stream">
      <Parameter name="practiceId" value="{practice_id}" />
      <Parameter name="callerNumber" value="{caller_number}" />
    </Stream>
  </Connect>
</Response>
```

### 9. Deployment

**Railway (recommended):**
- Persistent server (not serverless)
- WebSocket support
- Auto-scaling
- $5/month base + usage

**Dockerfile:**
```dockerfile
FROM node:20-slim
WORKDIR /app
COPY package.json pnpm-lock.yaml ./
RUN corepack enable && pnpm install --frozen-lockfile --prod
COPY dist/ ./dist/
EXPOSE 3001
CMD ["node", "dist/server.js"]
```

### 10. Key Performance Requirements

| Metric | Target |
|--------|--------|
| Time to first audio (greeting) | < 500ms after call connects |
| STT latency (speech → text) | < 200ms (Deepgram Nova-2 streaming) |
| LLM latency (text → first token) | < 300ms (Claude 3.5 Sonnet streaming) |
| TTS latency (text → first audio) | < 200ms (ElevenLabs streaming) |
| Total round-trip (caller stops → AI starts) | < 800ms |
| Interruption response time | < 200ms (stop TTS playback) |
| Max concurrent calls per instance | 50+ |
| Call recording | 100% of calls, stored in S3/R2 |

### 11. Development Phases

**Phase 1: Basic Call Handling**
- Set up Fastify server with Twilio webhook
- Handle incoming calls with TwiML Media Stream
- Parse Twilio Media Stream WebSocket messages
- Play a static greeting (hardcoded TTS audio)
- Log call events

**Phase 2: STT Integration**
- Connect Deepgram streaming WebSocket
- Convert Twilio mulaw audio to PCM for Deepgram
- Receive real-time transcripts
- Log transcripts to console

**Phase 3: LLM Integration**
- Send transcripts to Claude with system prompt
- Stream LLM response tokens
- Handle tool calls (mock implementations first)

**Phase 4: TTS Integration**
- Stream LLM text to ElevenLabs WebSocket
- Convert ElevenLabs audio to mulaw for Twilio
- Send audio back through Twilio Media Stream
- End-to-end voice conversation working

**Phase 5: Tool Implementation**
- Implement Omnira API client
- Wire up real tool calls (patient lookup, booking, email, SMS)
- Push webhook events to Omnira

**Phase 6: Production Hardening**
- Interruption handling
- Silence detection and prompting
- Call recording to S3
- Post-call summary generation
- Error recovery and fallback
- Sentry monitoring
- Health checks and metrics

**Phase 7: Multi-Practice Support**
- Practice registration API
- Per-practice phone number assignment
- Per-practice voice/prompt configuration
- Practice config caching

## Code Style and Conventions

- TypeScript strict mode
- Explicit return types on all functions
- Use `interface` over `type` for object shapes
- Prefer `async/await` over callbacks
- Use `zod` for runtime validation of external inputs (Twilio payloads, API requests)
- Structured logging with `pino` (JSON logs)
- No classes unless managing stateful resources (use plain functions and modules)
- Error handling: never swallow errors silently — log and propagate
- All external API calls must have timeouts and retry logic
- Audio processing must be zero-copy where possible (Buffer, not arrays)

## Important Constraints

1. This server must handle LONG-LIVED WebSocket connections (2-10 minutes per call). It CANNOT run on serverless platforms (Vercel, Netlify, AWS Lambda). It must run on a persistent server.

2. Audio processing is CPU-intensive. Use Node.js worker threads for audio format conversion if needed.

3. All Twilio Media Stream audio is mulaw 8kHz mono. Deepgram expects PCM 16-bit 16kHz. ElevenLabs outputs PCM/opus. You must handle all format conversions.

4. The LLM context window grows with each turn. Implement conversation summarization for calls longer than 5 minutes to prevent context overflow.

5. Tool calls happen mid-conversation. The caller is WAITING while tools execute. Keep tool execution under 2 seconds. If a tool takes longer, say "Let me check that for you, one moment please" before executing.

6. This engine will serve multiple dental practices. Each practice has its own phone number(s), voice, greeting, knowledge base, and tools. The engine must be multi-tenant.

7. Security: All API endpoints must be authenticated. Twilio webhooks validated via signature. Omnira API calls authenticated via shared secret.

## Getting Started

1. `pnpm create` — Initialize the project
2. Install core dependencies: `pnpm add fastify @fastify/websocket @deepgram/sdk @anthropic-ai/sdk elevenlabs twilio zod pino dotenv`
3. Set up `.env` from the template above
4. Start with Phase 1 — get a Twilio number answering calls
5. Progress through phases sequentially — each builds on the previous

## Reference Links

- Twilio Media Streams: https://www.twilio.com/docs/voice/media-streams
- Deepgram Streaming: https://developers.deepgram.com/docs/getting-started-with-live-streaming-audio
- Anthropic API: https://docs.anthropic.com/en/docs/build-with-claude/tool-use
- ElevenLabs WebSocket API: https://elevenlabs.io/docs/api-reference/websockets
- Pipecat (reference architecture): https://docs.pipecat.ai/
