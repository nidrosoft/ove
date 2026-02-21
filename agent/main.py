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

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("omnira")

from agent.config import Config
logger.info(f"Practice: {Config.PRACTICE_NAME} | Agent: {Config.AGENT_NAME}")


async def entrypoint(ctx):
    """Handle a new call/room connection."""
    logger.info(f"New connection: room={ctx.room.name}")

    await ctx.connect()

    participant = await ctx.wait_for_participant()
    logger.info(f"Participant joined: {participant.identity}")

    sip_attrs = participant.attributes or {}
    from_number = sip_attrs.get("sip.callingNumber", sip_attrs.get("sip.from", ""))
    to_number = sip_attrs.get("sip.calledNumber", sip_attrs.get("sip.to", ""))

    call_id = str(uuid.uuid4())
    call_logger = CallLogger(call_id=call_id, from_number=from_number, to_number=to_number)
    logger.info(f"Call {call_id}: from={from_number} to={to_number}")

    session = create_agent_session()

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
            logger.info(f"[{call_id}] Tool executed: {tool_name}({json.dumps(args)[:100]}) → {result_str[:100]}")

    agent = OmniraReceptionist(call_logger=call_logger)

    await session.start(
        agent=agent,
        room=ctx.room,
    )

    logger.info(f"Agent started in room {ctx.room.name}")

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
    logger.info(f"Call {call_id} ended — sending data to Omnira")
    await call_logger.send_to_omnira()
    logger.info(f"Call {call_id} — post-call data sent")


if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
        ),
    )
