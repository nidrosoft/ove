"""Entry point — LiveKit Agent worker."""
import asyncio
import json
import logging
import uuid

from dotenv import load_dotenv
from livekit import rtc
from livekit.agents import WorkerOptions, cli, ConversationItemAddedEvent, FunctionToolsExecutedEvent

from agent.voice_agent import OmniraReceptionist, create_agent_session
from agent.logger import CallLogger
from agent.config import Config, PracticeConfig
from agent.recording import start_room_recording, get_recording_url, wait_for_egress

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("omnira")
logger.info(f"Worker started | Default practice: {Config.PRACTICE_NAME} | Agent: {Config.AGENT_NAME}")


async def _resolve_practice_config(participant, room_name: str = "") -> PracticeConfig:
    """Resolve practice config from SIP participant attributes, room name, or env."""
    attrs = participant.attributes or {}

    practice_id = (
        attrs.get("practice_id")
        or attrs.get("sip.practice_id")
        or ""
    )

    # Extract practice_id from room name (format: "call-{practice_id}_+1XXXXXXXXXX_random")
    if not practice_id and room_name and room_name.startswith("call-"):
        parts = room_name.replace("call-", "", 1).split("_")
        if parts and len(parts[0]) > 8:
            practice_id = parts[0]
            logger.info(f"Extracted practice_id from room name: {practice_id}")

    # Use env PRACTICE_ID as ultimate fallback for single-tenant setup
    if not practice_id:
        practice_id = Config.PRACTICE_ID

    if practice_id:
        logger.info(f"Fetching config for practice_id={practice_id}")
        return await PracticeConfig.fetch(practice_id)

    # Fallback: try to resolve from the called number
    to_number = attrs.get("sip.calledNumber", attrs.get("sip.to", ""))
    if to_number:
        logger.info(f"Resolving practice by phone number: {to_number}")
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                resp = await client.get(
                    f"{Config.OMNIRA_API_URL}/voice-engine/practice-config",
                    params={"phone_number": to_number},
                    headers={"Authorization": f"Bearer {Config.OMNIRA_API_KEY}"},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return PracticeConfig(
                        practice_id=data.get("practice_id", ""),
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
        except Exception as e:
            logger.error(f"Failed to resolve practice by phone: {e}")

    logger.info("No practice_id found — using env fallback config")
    return PracticeConfig.from_env()


async def _disconnect_room(ctx, call_id: str):
    """Disconnect from the room to end the call."""
    try:
        logger.info(f"[{call_id}] Disconnecting room to end call")
        await ctx.room.disconnect()
    except Exception as e:
        logger.warning(f"[{call_id}] Room disconnect error: {e}")


async def entrypoint(ctx):
    """Handle a new call/room connection."""
    logger.info(f"New connection: room={ctx.room.name}")

    await ctx.connect()

    participant = await ctx.wait_for_participant()
    logger.info(f"Participant joined: {participant.identity}")

    # Resolve practice config dynamically
    practice_config = await _resolve_practice_config(participant, room_name=ctx.room.name)
    logger.info(f"Practice resolved: {practice_config.practice_name} (id={practice_config.practice_id})")

    # Update global Config so tool calls use the resolved practice_id
    if practice_config.practice_id:
        Config.PRACTICE_ID = practice_config.practice_id

    sip_attrs = participant.attributes or {}
    logger.info(f"SIP participant attributes: {sip_attrs}")
    logger.info(f"Participant identity: {participant.identity}, kind: {participant.kind}")

    # Extract caller number from SIP attributes or participant identity
    from_number = (
        sip_attrs.get("sip.callingNumber", "")
        or sip_attrs.get("sip.phoneNumber", "")
        or sip_attrs.get("sip.from", "")
    )

    # Fallback: parse phone number from participant identity (e.g. "sip_+16197717069")
    if not from_number and participant.identity and participant.identity.startswith("sip_"):
        from_number = participant.identity.replace("sip_", "")

    # Extract called number from SIP attributes or use practice phone
    to_number = (
        sip_attrs.get("sip.calledNumber", "")
        or sip_attrs.get("sip.to", "")
        or practice_config.practice_phone
    )

    call_id = str(uuid.uuid4())
    call_logger = CallLogger(
        call_id=call_id,
        from_number=from_number,
        to_number=to_number,
        practice_id=practice_config.practice_id,
    )
    logger.info(f"Call {call_id}: from={from_number} to={to_number} practice={practice_config.practice_id}")

    session = create_agent_session(practice_config)

    @session.on("conversation_item_added")
    def on_conversation_item_added(event: ConversationItemAddedEvent):
        text = event.item.text_content
        if not text or not text.strip():
            return
        role = event.item.role
        if role == "user":
            call_logger.log_caller_speech(text)
        elif role == "assistant":
            call_logger.log_agent_speech(text)

    @session.on("function_tools_executed")
    def on_function_tools_executed(event: FunctionToolsExecutedEvent):
        for fnc_call, fnc_output in event.zipped():
            tool_name = fnc_call.name
            try:
                args = fnc_call.arguments if isinstance(fnc_call.arguments, dict) else json.loads(fnc_call.raw_arguments or "{}")
            except Exception:
                args = {}
            result_str = str(fnc_output.output or fnc_output.content or "")[:500]
            call_logger.log_tool_call(tool_name, args, result_str)
            logger.info(f"[{call_id}] Tool: {tool_name}({json.dumps(args)[:100]}) → {result_str[:100]}")

            if tool_name == "end_call" and "__END_CALL__" in result_str:
                logger.info(f"[{call_id}] Agent requested call end — disconnecting in 2s")
                asyncio.get_event_loop().call_later(2.0, lambda: asyncio.ensure_future(_disconnect_room(ctx, call_id)))

    agent = OmniraReceptionist(call_logger=call_logger, practice_config=practice_config)

    await session.start(
        agent=agent,
        room=ctx.room,
    )

    logger.info(f"Agent started in room {ctx.room.name}")

    # Start recording via LiveKit Egress
    egress_id = await start_room_recording(ctx.room.name, call_id)
    if egress_id:
        logger.info(f"[{call_id}] Recording egress started: {egress_id}")
    else:
        logger.info(f"[{call_id}] Recording not available (S3 creds not configured)")

    disconnect_event = asyncio.Event()

    def on_participant_disconnected(p: rtc.RemoteParticipant):
        logger.info(f"Participant disconnected: {p.identity}")
        disconnect_event.set()

    ctx.room.on("participant_disconnected", on_participant_disconnected)

    def on_room_disconnected():
        logger.info("Room disconnected")
        disconnect_event.set()

    ctx.room.on("disconnected", on_room_disconnected)

    await disconnect_event.wait()

    call_logger.log_call_end(reason="caller_disconnected")

    # Send post-call data FIRST (before waiting for recording — process may exit)
    # If recording is available, we'll set a preliminary URL optimistically
    if egress_id:
        recording_url = get_recording_url(call_id)
        call_logger.set_recording_url(recording_url)
        logger.info(f"[{call_id}] Recording URL (optimistic): {recording_url}")

    logger.info(f"Call {call_id} ended — sending data to Omnira")
    await call_logger.send_to_omnira()
    logger.info(f"Call {call_id} — post-call data sent")


if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
        ),
    )
