"""Entry point — LiveKit Agent worker."""
import asyncio
import json
import logging
import os
import uuid

from dotenv import load_dotenv
from livekit import rtc, api
from livekit.agents import WorkerOptions, cli, ConversationItemAddedEvent, FunctionToolsExecutedEvent

from agent.voice_agent import OmniraReceptionist, create_agent_session
from agent.logger import CallLogger
from agent.config import Config, PracticeConfig

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("omnira")
logger.info(f"Worker started | Default practice: {Config.PRACTICE_NAME} | Agent: {Config.AGENT_NAME}")


async def _resolve_practice_config(participant) -> PracticeConfig:
    """Resolve practice config from SIP participant attributes or room metadata."""
    attrs = participant.attributes or {}

    # LiveKit dispatch rules can pass practice_id via room metadata or participant attributes
    practice_id = (
        attrs.get("practice_id")
        or attrs.get("sip.practice_id")
        or ""
    )

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


async def entrypoint(ctx):
    """Handle a new call/room connection."""
    logger.info(f"New connection: room={ctx.room.name}")

    await ctx.connect()

    participant = await ctx.wait_for_participant()
    logger.info(f"Participant joined: {participant.identity}")

    # Resolve practice config dynamically
    practice_config = await _resolve_practice_config(participant)
    logger.info(f"Practice resolved: {practice_config.practice_name} (id={practice_config.practice_id})")

    sip_attrs = participant.attributes or {}
    from_number = sip_attrs.get("sip.callingNumber", sip_attrs.get("sip.from", ""))
    to_number = sip_attrs.get("sip.calledNumber", sip_attrs.get("sip.to", ""))

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

    agent = OmniraReceptionist(call_logger=call_logger, practice_config=practice_config)

    await session.start(
        agent=agent,
        room=ctx.room,
    )

    logger.info(f"Agent started in room {ctx.room.name}")

    # Start call recording via LiveKit Egress (audio-only S3 upload)
    egress_id = None
    try:
        lk_url = os.getenv("LIVEKIT_URL", "").replace("wss://", "https://")
        lk_api = api.LiveKitAPI(
            url=lk_url,
            api_key=os.getenv("LIVEKIT_API_KEY", ""),
            api_secret=os.getenv("LIVEKIT_API_SECRET", ""),
        )

        recording_key = f"recordings/{practice_config.practice_id}/{call_id}.ogg"
        s3_bucket = os.getenv("RECORDING_S3_BUCKET", "")
        s3_region = os.getenv("RECORDING_S3_REGION", "us-east-1")

        if s3_bucket:
            from livekit.api import RoomCompositeEgressRequest, EncodedFileOutput, EncodedFileType, S3Upload

            egress_req = RoomCompositeEgressRequest(
                room_name=ctx.room.name,
                audio_only=True,
                file_outputs=[
                    EncodedFileOutput(
                        file_type=EncodedFileType.OGG,
                        filepath=recording_key,
                        s3=S3Upload(
                            bucket=s3_bucket,
                            region=s3_region,
                            access_key=os.getenv("RECORDING_S3_ACCESS_KEY", ""),
                            secret=os.getenv("RECORDING_S3_SECRET_KEY", ""),
                        ),
                    ),
                ],
            )
            egress_resp = await lk_api.egress.start_room_composite_egress(egress_req)
            egress_id = egress_resp.egress_id
            recording_url = f"https://{s3_bucket}.s3.{s3_region}.amazonaws.com/{recording_key}"
            call_logger.set_recording_url(recording_url)
            logger.info(f"[{call_id}] Recording started: egress_id={egress_id}")
        else:
            logger.info(f"[{call_id}] No RECORDING_S3_BUCKET configured — skipping recording")
    except Exception as e:
        logger.warning(f"[{call_id}] Recording start failed (non-fatal): {e}")

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

    # Stop recording if active
    if egress_id:
        try:
            await lk_api.egress.stop_egress(egress_id)
            logger.info(f"[{call_id}] Recording stopped")
        except Exception as e:
            logger.warning(f"[{call_id}] Recording stop failed: {e}")

    call_logger.log_call_end(reason="caller_disconnected")
    logger.info(f"Call {call_id} ended — sending data to Omnira")
    await call_logger.send_to_omnira()
    logger.info(f"Call {call_id} — post-call data sent")


if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
        ),
    )
