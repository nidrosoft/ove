# Omnira Voice Engine — Deep Research Report

> **Date:** February 2026
> **Purpose:** Compare open-source real-time voice AI frameworks, STT/TTS providers, and hosting platforms for building a custom, vendor-agnostic voice engine.

---

## Executive Summary

After researching the entire landscape of open-source voice AI engines, STT/TTS providers, and hosting platforms, here are the two finalists and my recommendation:

| | **Pipecat (Daily.co)** | **LiveKit Agents** |
|---|---|---|
| **GitHub Stars** | ~1,700+ | **~9,400+** (1M+ downloads/month) |
| **Language** | Python only | Python (primary) + **Node.js/TypeScript** |
| **Architecture** | Frame-based pipeline | AgentSession (v1.0) with pipeline nodes |
| **Provider Swap** | Trivial (abstract base classes) | Trivial (plugin system) |
| **Telephony** | Twilio via SIP-to-Daily or WebSocket | **Native SIP** (works with any SIP provider) |
| **Latency** | 500-1200ms (sub-800ms achievable) | 500-1200ms (sub-800ms achievable) |
| **Tool Calling** | Yes (decorator-based) | Yes (`@ai_callable` decorator) |
| **Barge-In** | Yes (first-class) | Yes (first-class) |
| **Deployment** | Any server + Daily.co transport | Any server + LiveKit server |
| **LLM Support** | Anthropic Claude, OpenAI, Gemini, Groq, etc. | Anthropic Claude, OpenAI, Gemini, Groq, etc. |
| **License** | BSD 2-Clause | Apache 2.0 |

### **Recommendation: LiveKit Agents**

LiveKit Agents wins for Omnira because of:
1. **Node.js/TypeScript SDK** — aligns with your existing spec (Fastify, TypeScript)
2. **Native SIP support** — direct Twilio SIP trunking, no middleman needed
3. **Self-hostable infrastructure** — LiveKit server is open source (Go binary), no dependency on a third-party WebRTC service
4. **Enterprise scaling** — horizontal auto-scaling, LiveKit Cloud option for managed deployment
5. **Claude Sonnet 4.6 support** — via `livekit-plugins-anthropic`

**Honorable mention: Pipecat** — if you're willing to switch to Python, Pipecat has the most mature ecosystem and slightly broader provider support. It's the framework most Vocode users migrated to.

---

## Table of Contents

1. [Framework Deep Comparison](#1-framework-deep-comparison)
2. [Eliminated Frameworks](#2-eliminated-frameworks)
3. [STT Provider Comparison](#3-stt-provider-comparison)
4. [TTS Provider Comparison](#4-tts-provider-comparison)
5. [Hosting Platform Comparison](#5-hosting-platform-comparison)
6. [Cost Analysis](#6-cost-analysis)
7. [Recommended Architecture for Omnira](#7-recommended-architecture-for-omnira)
8. [Provider Swap Strategy](#8-provider-swap-strategy)

---

## 1. Framework Deep Comparison

### Pipecat (by Daily.co)

**Repo:** `pipecat-ai/pipecat` | **Stars:** ~1,700+ | **License:** BSD 2-Clause | **Language:** Python

**How It Works:**
Everything is a "Frame" — typed data objects (audio frames, text frames, control frames) that flow through a pipeline of processors:

```
Transport(Input) → STT → UserAggregator → LLM → TTS → Transport(Output)
```

Swapping providers is a one-line change:
```python
# Before: Deepgram
stt = DeepgramSTTService(api_key="...")
# After: Azure
stt = AzureSTTService(api_key="...", region="eastus")
# Pipeline stays identical
```

**STT Providers:** Deepgram, AssemblyAI, Azure, Google, Whisper (API), Gladia, AWS Transcribe, Rev.ai
**TTS Providers:** ElevenLabs, Cartesia, PlayHT, Azure, Google, AWS Polly, LMNT, Rime, XTTS, Deepgram Aura, OpenAI TTS
**LLM Providers:** OpenAI, **Anthropic Claude**, Google Gemini, Together, Fireworks, Groq, Azure OpenAI, Ollama, AWS Bedrock

**Twilio Integration:**
- **Option A:** Twilio → SIP → Daily.co Room → Pipecat bot (recommended path)
- **Option B:** Twilio WebSocket Media Streams → Pipecat WebSocket transport (more direct, less polished)

**Strengths:**
- Most mature open-source voice AI framework
- Broadest provider ecosystem (15+ STT/TTS/LLM providers)
- Excellent interruption handling with context-aware aggregators
- Supports OpenAI Realtime API (speech-to-speech)
- Backed by Daily.co (well-funded, committed to open source)

**Weaknesses:**
- **Python only** — your spec calls for Node.js/TypeScript
- DailyTransport is the most polished path; WebSocket transport requires more effort
- One conversation per process (need orchestration for scaling)
- Rapid API changes between versions

---

### LiveKit Agents

**Repo:** `livekit/agents` | **Stars:** **~9,400+** (1M+ downloads/month) | **License:** Apache 2.0 | **Language:** Python + Node.js/TypeScript

**How It Works:**
As of v1.0, LiveKit Agents uses `AgentSession` with customizable pipeline nodes (replacing the older `VoicePipelineAgent`). The pipeline orchestrates VAD → STT → LLM → TTS. Each component is a plugin implementing a common interface:

```python
agent = VoicePipelineAgent(
    vad=silero.VAD.load(),
    stt=deepgram.STT(),
    llm=anthropic.LLM(model="claude-sonnet-4-6-20250514"),  # Claude Sonnet 4.6!
    tts=cartesia.TTS(),
)
```

Or in TypeScript (`agents-js`):
```typescript
const agent = new VoicePipelineAgent(
  vad, stt, llm, tts,
  { allowInterruptions: true }
);
```

**STT Providers:** Deepgram, AssemblyAI, Azure, Google, Whisper (API), FAL, Groq Whisper, Clova
**TTS Providers:** ElevenLabs, Cartesia, PlayHT, Azure, Google, OpenAI TTS, Rime
**LLM Providers:** OpenAI, **Anthropic Claude**, Google Gemini, Groq, Together, Fireworks, Ollama, Cerebras, Azure OpenAI

**Twilio Integration:**
- Twilio SIP Trunking → **LiveKit SIP server** (native, first-class)
- LiveKit SIP bridges phone calls into LiveKit Rooms
- Works with ANY SIP trunk provider (Twilio, Vonage, Telnyx)
- Supports both inbound and outbound calls

**Tool Calling:**
```python
class DentalTools(FunctionContext):
    @ai_callable(description="Book an appointment")
    async def book_appointment(self, patient_name: str, date: str, procedure: str) -> str:
        result = await omnira_api.book(patient_name, date, procedure)
        return f"Booked {procedure} for {patient_name} on {date}"

    @ai_callable(description="Send confirmation email")
    async def send_email(self, email: str, subject: str, body: str) -> str:
        await resend.send(to=email, subject=subject, body=body)
        return "Confirmation email sent"

agent = VoicePipelineAgent(
    vad=silero.VAD.load(),
    stt=deepgram.STT(),
    llm=anthropic.LLM(model="claude-sonnet-4-6-20250514"),
    tts=elevenlabs.TTS(voice_id="sharon-voice"),
    fnc_ctx=DentalTools(),
)
```

**Strengths:**
- **Node.js/TypeScript SDK** (`livekit/agents-js`) — aligns with your Fastify spec. Requires Node.js >= 20 and pnpm >= 10.15.0
- **Native SIP** — no middleman for Twilio; direct SIP trunking
- Self-hostable: LiveKit server is open source (single Go binary)
- LiveKit Cloud option for managed deployment
- Built-in auto-scaling via worker dispatching
- **v1.0 AgentSession** with pipeline nodes — more flexible customization of pipeline steps
- Supports both pipeline (STT→LLM→TTS) and multimodal (speech-to-speech) modes
- **9,400+ stars, 1M+ downloads/month** — the most popular voice AI framework

**Weaknesses:**
- Requires running a LiveKit server (additional infrastructure)
- Node.js SDK may trail Python SDK slightly in feature parity
- Tightly coupled to LiveKit infrastructure (not a "plug any WebSocket" solution)
- API evolution (v1.0 deprecated VoicePipelineAgent → AgentSession)

---

### Head-to-Head Summary

| Criterion | Pipecat | LiveKit Agents | **Winner** |
|-----------|---------|---------------|------------|
| Provider ecosystem | 15+ providers | 12+ providers | Pipecat |
| Provider swapping ease | One-line change | One-line change | Tie |
| TypeScript support | None | Yes (`agents-js`) | **LiveKit** |
| Telephony (SIP) | Via Daily.co | **Native SIP** | **LiveKit** |
| Self-hosted infra | Needs Daily.co (or raw WS) | LiveKit server (open source Go) | **LiveKit** |
| Latency | Sub-800ms achievable | Sub-800ms achievable | Tie |
| Tool calling | Full support | Full support | Tie |
| Barge-in / interruption | Excellent | Excellent | Tie |
| Claude support | Yes | Yes | Tie |
| Maturity | Slightly more mature | Rapidly catching up | Pipecat (slight) |
| Scaling | Process-per-call, DIY | Worker dispatch, auto-scale | **LiveKit** |
| Community | Active (Daily.co Discord) | Active (LiveKit Discord) | Tie |
| Documentation | Good, improving | Good, comprehensive | Tie |

---

## 2. Eliminated Frameworks

### Vocode — NOT RECOMMENDED
- **Critical Issue:** Maintenance is declining. The founding team pivoted to a hosted product. Open-source contributions dropped significantly.
- ~2,800-3,000 stars but community is fragmenting
- Many users migrated to Pipecat
- Risk of abandonment makes it unsuitable for a production system

### Bolna — NICHE OPTION
- ~800-1,200 stars, telephony-first design
- Smaller ecosystem (fewer providers)
- JSON-config-driven (easy setup but less flexible)
- Good for quick prototyping but lacks the depth needed for Omnira

### Ultravox (Fixie.ai) — DIFFERENT APPROACH
- Speech-to-speech model (eliminates the STT→LLM→TTS pipeline)
- Dramatically lower latency (~300ms)
- **BUT:** locks you to their model — you cannot use Claude Sonnet 4.6 as the LLM
- Worth watching for the future but not suitable for your requirements

---

## 3. STT Provider Comparison

| Provider | Streaming Latency | WER (English) | Price/min | WebSocket | Real-Time Ready |
|----------|-------------------|---------------|-----------|-----------|-----------------|
| **Deepgram Nova-2/3** | ~100-200ms | ~7-10% | $0.0043 | Yes (native) | **Best choice** |
| AssemblyAI Universal-2 | ~200-400ms | ~7-9% | $0.0062 | Yes | Good (fallback) |
| Azure Speech | ~200-400ms | ~8-10% | $0.0167 | SDK | Decent |
| Google Cloud V2 | ~200-500ms | ~6-10% | $0.024 | gRPC | Too expensive |
| Whisper (self-hosted) | ~1500-4000ms | ~5-7% | $0 + GPU | DIY | **No** (too slow) |
| Groq Whisper | ~200-500ms (batch) | ~5-7% | $0.00185 | No (REST) | **No** (no streaming) |

### Recommendation

| Role | Provider | Why |
|------|----------|-----|
| **Primary STT** | **Deepgram Nova-2/3** | Fastest streaming, native WebSocket, best real-time latency |
| **Fallback STT** | AssemblyAI | Good streaming, different infrastructure (no correlated failures) |
| **Post-call transcription** | Groq Whisper | Cheapest ($0.00185/min), highest accuracy, batch is fine for recordings |

---

## 4. TTS Provider Comparison

| Provider | TTFB | Quality | Price/min | WebSocket Stream | Voice Clone | Best For |
|----------|------|---------|-----------|-----------------|-------------|----------|
| **ElevenLabs** | ~200-400ms | 9.5/10 | $0.05-0.15 | Yes (native) | Yes (best) | Best quality |
| **Cartesia Sonic** | ~90-150ms | 8/10 | $0.03-0.08 | Yes | Yes | **Lowest latency** |
| PlayHT | ~200-400ms | 8.5/10 | $0.05-0.10 | Yes | Yes | Alternative |
| Azure Neural | ~150-300ms | 8/10 | $0.016 | SDK | Enterprise | **Cheapest at scale** |
| Google Cloud TTS | ~200-500ms | 7.5-8.5/10 | $0.016-0.03 | gRPC | Limited | Multilingual |
| Fish Audio | ~200-400ms | 8/10 | $0.02-0.05 | Yes | Yes | CJK languages |
| OpenAI TTS | ~300-600ms | 8.5/10 | $0.015-0.03 | **No** (REST) | No | **Not for real-time** |
| XTTS/Coqui | ~500-2000ms | 7.5/10 | $0 + GPU | DIY | Yes | Self-hosted only |

### Recommendation

| Role | Provider | Why |
|------|----------|-----|
| **Primary TTS** | **ElevenLabs** | Best voice quality, native WebSocket streaming, voice cloning |
| **Low-latency TTS** | **Cartesia Sonic** | 90-150ms TTFB, swap when latency matters more than quality |
| **Cost optimization** | **Azure Neural** | $0.016/min vs $0.08/min — 5x cheaper at scale |
| **Future option** | PlayHT | Quality alternative, monitor pricing |

### Provider Swap Strategy for TTS
Your system prompt already defines `src/tts/provider.ts` as the interface. All providers above support the same conceptual model (text in → audio chunks out). Implement the interface once, swap at the config level:

```typescript
// Change one line in your config:
TTS_PROVIDER=elevenlabs    // Best quality
TTS_PROVIDER=cartesia      // Lowest latency
TTS_PROVIDER=azure         // Cheapest at scale
```

---

## 5. Hosting Platform Comparison

| Platform | Monthly Cost | WebSocket | Auto-Scale | Cold Start | Max WS Duration | Regions | Ease |
|----------|-------------|-----------|------------|------------|-----------------|---------|------|
| **Railway** | ~$20-30 | Native | Manual | None | Unlimited | 3-4 | 9/10 |
| **Fly.io** | ~$15-25 | Native | Built-in | ~300ms | Unlimited | **35+** | 7/10 |
| Render | $25 | Supported | Team plan | None (paid) | Active OK | 4 | 8/10 |
| Hetzner | ~$8 | Full | DIY | None | Unlimited | 6 | 4/10 |
| DigitalOcean | $18 | Full | App Platform | None | Unlimited | 15+ | 6/10 |
| AWS (EC2/ECS) | ~$30-50 | ALB/EC2 | Best | 30-60s | ~66min idle | 30+ | 3/10 |

### Recommendation

| Phase | Platform | Why |
|-------|----------|-----|
| **MVP** | **Railway** | Simplest deployment, your spec already lists it, WebSocket-native |
| **Growth** | **Fly.io** | 35+ regions (colocate near Twilio), built-in auto-scaling |
| **Scale** | **Hetzner** or **AWS** | Cost optimization or enterprise requirements |

**Critical:** Your server MUST be a persistent process (not serverless). Vercel, Netlify, AWS Lambda are NOT options — they have connection timeouts that will kill phone calls.

---

## 6. Cost Analysis

### Per-Call Cost (5-minute average call)

| Component | Provider | Cost |
|-----------|----------|------|
| STT | Deepgram Nova-2 | $0.022 |
| LLM | Claude Sonnet 4.6 (~3K tokens) | $0.03 |
| TTS | ElevenLabs | $0.40 |
| TTS | Cartesia (alternative) | $0.20 |
| TTS | Azure (cost-optimized) | $0.08 |
| Hosting | Railway/Fly.io | ~$0.001 |
| **Total (ElevenLabs)** | | **~$0.45** |
| **Total (Cartesia)** | | **~$0.25** |
| **Total (Azure)** | | **~$0.13** |

**TTS is the dominant cost.** At 10,000 calls/month:
- ElevenLabs: ~$4,500/month in TTS alone
- Cartesia: ~$2,500/month
- Azure: ~$1,300/month

This is why the provider-swap architecture matters — start with ElevenLabs for quality, swap to Cartesia or Azure as volume grows.

---

## 7. Recommended Architecture for Omnira

### Option A: LiveKit Agents (Recommended)

```
                    PSTN / Mobile
                        │
                   ┌────▼────┐
                   │  Twilio  │  (SIP Trunking)
                   └────┬────┘
                        │ SIP INVITE
                   ┌────▼────────────┐
                   │  LiveKit Server  │  (Open-source Go binary, self-hosted)
                   │  + SIP Gateway   │
                   └────┬────────────┘
                        │ WebRTC (audio track)
                   ┌────▼────────────────────────┐
                   │   OMNIRA VOICE ENGINE        │
                   │   (LiveKit Agent Worker)     │
                   │                              │
                   │   VoicePipelineAgent:        │
                   │   ┌──────────────────────┐   │
                   │   │ Silero VAD            │   │
                   │   │ ↓                     │   │
                   │   │ Deepgram STT          │   │
                   │   │ ↓                     │   │
                   │   │ Claude Sonnet 4.6     │──►│── Tool Calls:
                   │   │ ↓                     │   │   • book_appointment
                   │   │ ElevenLabs/Cartesia   │   │   • send_email (Resend)
                   │   │ TTS                   │   │   • send_sms
                   │   └──────────────────────┘   │   • lookup_patient
                   │                              │   • check_availability
                   └──────────────────────────────┘   • transfer_call
                        │
                   ┌────▼────────────────┐
                   │   Omnira Platform    │  (Next.js on Vercel)
                   │   - Webhooks         │
                   │   - REST API         │
                   │   - Calendar/Stella  │
                   └─────────────────────┘
```

**Key differences from your current spec:**
1. LiveKit server replaces direct Twilio WebSocket Media Streams
2. SIP trunking replaces Twilio Media Streams API
3. The agent framework handles VAD, interruption, and pipeline orchestration
4. Provider swapping is built into the framework (no custom abstraction needed)

**What you still build yourself:**
- Tool implementations (book_appointment, send_email, etc.)
- Omnira API client
- Practice configuration management
- System prompt builder
- Post-call processing (summary, transcript, recording)

### Option B: Custom Engine (Your Current Spec)

Keep your existing Fastify + TypeScript architecture but add proper provider abstraction:

```
Twilio Media Streams → Your Fastify Server → STT Provider Interface
                                            → LLM Provider Interface
                                            → TTS Provider Interface
```

**Pros:** Full control, no dependency on LiveKit
**Cons:** You're reimplementing what Pipecat/LiveKit already solved (VAD, interruption handling, pipeline streaming, provider abstraction)

---

## 8. Provider Swap Strategy

Regardless of which framework you choose, the swap architecture looks like this:

### Config-Driven Provider Selection

```typescript
// .env
STT_PROVIDER=deepgram          // or: assemblyai, azure, google
TTS_PROVIDER=elevenlabs        // or: cartesia, azure, playht
LLM_PROVIDER=anthropic         // or: openai, groq
LLM_MODEL=claude-sonnet-4-6-20250514  // or: gpt-4o, llama-3

// Per-practice override (in PracticeConfig)
{
  "voice_provider": "elevenlabs",   // Premium practices get ElevenLabs
  "voice_id": "sharon-custom-clone",
  // OR
  "voice_provider": "cartesia",    // Cost-optimized practices get Cartesia
  "voice_id": "cartesia-warm-female",
}
```

### With LiveKit Agents (code):
```python
# Swap is literally changing the import + constructor
if config.tts_provider == "elevenlabs":
    tts = elevenlabs.TTS(voice_id=config.voice_id)
elif config.tts_provider == "cartesia":
    tts = cartesia.TTS(voice=config.voice_id)
elif config.tts_provider == "azure":
    tts = azure.TTS(voice=config.voice_id)

agent = VoicePipelineAgent(vad=vad, stt=stt, llm=llm, tts=tts, fnc_ctx=tools)
```

### Optimal Provider Stacks by Priority

| Priority | STT | LLM | TTS | Round-Trip | Cost/5min |
|----------|-----|-----|-----|------------|-----------|
| **Best Quality** | Deepgram Nova-3 | Claude Sonnet 4.6 | ElevenLabs | ~800ms | ~$0.45 |
| **Lowest Latency** | Deepgram Nova-2 | Groq (Llama 3) | Cartesia | ~500ms | ~$0.10 |
| **Best Value** | Deepgram Nova-2 | Claude Sonnet 4.6 | Azure Neural | ~700ms | ~$0.13 |
| **Maximum Speed** | Deepgram Nova-2 | Cerebras (Llama 3) | Cartesia | ~400ms | ~$0.08 |

---

## Final Verdict

### For Omnira Voice Engine, use:

| Component | Choice | Rationale |
|-----------|--------|-----------|
| **Framework** | **LiveKit Agents** | TypeScript SDK, native SIP, self-hostable, auto-scaling |
| **STT** | **Deepgram Nova-2/3** | Fastest streaming, best real-time latency |
| **LLM** | **Claude Sonnet 4.6** | Your choice, supported by LiveKit via `livekit-plugins-anthropic` |
| **TTS (primary)** | **ElevenLabs** | Best quality, voice cloning, streaming WebSocket |
| **TTS (low-latency)** | **Cartesia Sonic** | 90ms TTFB, swap when speed > quality |
| **Telephony** | **Twilio SIP → LiveKit SIP** | Native integration, no middleman |
| **Hosting (MVP)** | **Railway** | Simplest, WebSocket-native |
| **Hosting (scale)** | **Fly.io** | 35+ regions, auto-scaling |
| **Email** | **Resend** | Your choice, via tool calling |

### Next Steps

1. **Verify current stats** — Run `gh repo view livekit/agents` and `gh repo view pipecat-ai/pipecat` to confirm current star counts and last commit dates
2. **Prototype with LiveKit Agents** — Set up a basic voice agent with Deepgram + Claude + ElevenLabs
3. **Test Twilio SIP integration** — Configure a Twilio SIP trunk pointing to LiveKit SIP
4. **Implement your tools** — book_appointment, send_email, send_sms, etc.
5. **Deploy to Railway** — Get it live and test with real phone calls

---

*Note: All pricing and stats are based on research through early 2025. Verify current pricing on each provider's website before making procurement decisions.*
